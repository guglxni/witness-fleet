# Runtime, clocks, approval and recovery contracts

**Normative proposed design.** This document resolves details that must not be guessed during implementation. No runtime exists yet. It refines architecture/graph/simulator documents; update all owners when changing it.

## 1. Clock domains and lease recovery

- `world_tick`: integer simulator step; observation expiry and **all first-build operational policy validity** use explicit `effective_clock_domain=simulation_tick_v1` with `[effective_from_tick, effective_to_tick)` (null end means unbounded).
- `occurred_at` / `recorded_at` / `source_effective_from_utc` / `source_effective_to_utc`: timezone-aware UTC source/audit metadata, not the first-build dispatch-validity clock. A scenario declares `policy_epoch_utc` and fixed `step_duration`; any source UTC interval is converted once at promotion to tick bounds using the documented mapping below, never compared directly with ticks or the live host wall clock.
- Monotonic deadlines: local-process timeout/watchdog only. Persisted monotonic values from a dead process/other host are **not reusable**.
- Persist each claim with `lease_expires_at_utc`, `coordinator_epoch`, and a monotonic local deadline derived when issued. The single trusted coordinator owns the clock. Clock rollback/large jump beyond configured tolerance causes a hold and reconciliation, not opportunistic lease stealing.
- On coordinator restart, increment durable `coordinator_epoch` through a tested transition. Old-epoch ownership cannot dispatch. Reconcile outstanding commands before creating replacement claims; expiry alone never proves an old effect absent.
- Concurrent claim tests use independent database clients with the same injected authoritative clock and epoch. They test CAS behavior, not distributed clock synchronization. A future multi-coordinator deployment needs its own leader/clock protocol and ADR.

Policy mapping: `policy_time(k) = policy_epoch_utc + k * step_duration`. The scenario epoch is fixed and persisted; pausing real-time execution does not advance this policy clock. For UTC interval `[a,b)`, use `from_tick = ceil((a-policy_epoch_utc)/step_duration)` and `to_tick = ceil((b-policy_epoch_utc)/step_duration)`; retain source values and converter version. At tick k, use `from_tick <= k < to_tick`. Validate finite ranges and `from_tick < to_tick`, with explicit unbounded-end handling. UI distinguishes simulated policy time from real recorded UTC. Restart restores the same episode clock/checkpoint; resetting time starts a new episode. Production wall-clock policy enforcement would require a separate ADR, not a silent mode switch.

`Claim.clock_domain` is `coordinator_epoch_utc_lease_v1`. Keep old fields only for migration; do not use a free-form `lease_until` without units/domain. Fence increments monotonically per resource/task across reassignment, independently of lease time. Each claim/command carries a task fence plus a map of `resource_id -> fence`; one scalar must not be compared across unrelated resources. Ingress learns current fences only through ordered `FENCE_INSTALL` events from the trusted sequencer, never by trusting a larger number supplied by an arbitrary worker. Before execution all required resource fences must exactly match installed values.

## 2. Policy-to-actuation ordering

There is no distributed transaction between FalkorDB and the simulator. Define an explicit command ordering rather than claiming an atomic cross-service dispatch.

1. All policy activations and command admissions enter a **single coordinator transition sequencer**. A separate worker cannot write governance directly.
2. Admission writes a durable command intent with relevant evidence/task/resource versions, current `policy_epoch`, stable command ID and dispatch sequence.
3. Simulator ingress processes command admissions and revocations in sequence and stores the highest applied epoch/sequence. It rejects stale fences/epochs and duplicate-ID mismatches before starting a skill.
4. A revocation or blanket restriction is also an ordered simulator event with an effective `world_tick`. The simulator must apply it before stepping that tick. New motion is blocked; active motion follows its bounded controlled-hold contract.
5. The operator UI distinguishes policy graph committed, simulator revocation acknowledged, and physical hold achieved. Until propagation is acknowledged, state is `REVOCATION_PENDING` and no new affected admissions occur.
6. Missing sequence, lost receipt, graph outage or ambiguous propagation means hold/reconcile. On reconnect, the simulator cannot accept new commands until epoch/sequence synchronization is complete.

### Durable sequencer/outbox contract

- A tenant's `FleetState.dispatch_sequence` is a **global monotonically increasing** integer across coordinator epochs. The ordering key is `(tenant_id, dispatch_sequence)`; epoch is a fence recorded on each event, not permission to reuse/reset sequence numbers.
- Single sequencer writer assigns the next value and stores an immutable `DispatchEvent` **in the same tested conditional graph mutation** as the associated `CommandIntent`, `AuthorizationReceipt` or governance activation and version/epoch update. Event fields: ID, sequence, coordinator epoch, kind (`COMMAND`, `POLICY_ACTIVATION`, `REVOCATION`, `FENCE_INSTALL`, `EPOCH_BARRIER`), payload hash, subject IDs, intended effective tick. Mutable delivery receipts are separate graph records. The mutation must satisfy actual pinned-engine contract tests; do not emulate atomicity with MULTI/EXEC. A missing/partial event makes readiness fail.
- The dispatcher reads this canonical graph outbox in order. Simulator journal records event ID/hash/sequence before its acknowledgment and retains `last_contiguous_applied_sequence`. Same event/bytes returns existing receipt; same ID or sequence with different bytes rejects. A gap blocks new execution; no timeout skips it.
- Before an event's intended effective tick, ingress must know it durably. A late revocation applies an immediate controlled hold at current tick and records late delivery plus intended/actual ticks; it is never backdated. Event lateness/unknown propagation blocks affected admissions. A bounded heartbeat ensures disconnected simulation cannot keep accepting fresh skills; stopping of already-running skills obeys the local controller contract.
- Restart: hold admissions; atomically bump coordinator epoch and append an EPOCH_BARRIER event; read simulator last-contiguous receipt and reconcile every unacknowledged outbox identity. Resend policy/fence/barrier events only as the identical durable event, which is idempotent. **Do not blindly resend old COMMAND events**: query their identity/state first. Already accepted commands reconcile under original identity; known-unadmitted stale intents become cancelled through the separately journaled CancellationDisposition protocol below, allowing sequence progress without replacing the immutable original event. If acceptance cannot be determined, remain held. The ingress must apply or durably reject each event in order (including a separately verified cancellation disposition where applicable) before advancing its contiguous cursor.
- To avoid a gap/barrier deadlock, define a separate **hold/reconciliation control operation**, available only to the trusted sequencer. It can persist a higher accepted coordinator epoch, hold ingress and record a cancellation disposition for an exact earlier `(event_id, sequence, payload_hash)`; it cannot issue a motion command, lower an epoch or reinterpret an old payload. A cancellation disposition is a separate immutable record referencing the original event, **not replacement bytes under its sequence**. First journal the hold/higher-epoch fence, then inspect old command receipt: only an explicit durable `NEVER_ADMITTED`/rejected status permits a cancel disposition. `NOT_FOUND` after uncertain recovery does not. An admitted/running/unknown command must reconcile or stay held. Persist acknowledged disposition in graph, then the ordered cursor may consume the old event as cancelled and reach the later barrier. Test crash after every handshake/disposition step; incomplete proof remains held.
- New commands begin only after barrier acknowledgment, unresolved effects reconciled/held and source/policy/fence versions resynchronized. Old graph restore versus newer simulator journal fails readiness. No cross-store transaction or exactly-once physical effect is claimed.
- Required tests: crash after graph mutation/before send; send applied/ack lost; partial write/query failure; out-of-order delivery/gap; duplicate hash mismatch; late revocation; old command after epoch barrier; and stale graph restore. Each must either preserve exact ordering or hold explicitly.

A restriction cannot undo already executed motion. Report admission, effective tick, cancellation, stopping distance/time and any violation separately. The default simulator can use instantaneous planar velocity hold only if its dynamics genuinely support that behavior; otherwise model braking and conservatively reserve the stopping envelope. This is a testable simulation contract, not real-robot emergency-stop certification.

## 3. Canonical command state machine

Use the following names across code/API/UI; receipt states and verification are distinct:

```text
PREPARED -> SENT -> ACCEPTED -> RUNNING -> CONTROLLER_DONE -> OUTCOME_VERIFIED
             |         |          |              |
             +-------> UNKNOWN <---+--------------+
                       |                           
                       +-> reconcile -> known receipt/state or HOLD
FAILED / CANCELLED are explicit terminal controller outcomes.
```

- `PREPARED`: graph intent, matching immutable AuthorizationReceipt and sequenced outbox event durable, nothing implied about delivery.
- `SENT`: transport attempted, receipt may be unknown.
- `ACCEPTED`: simulator ingress acknowledged/durably recorded per selected profile.
- `RUNNING`: bounded controller started.
- `CONTROLLER_DONE`: controller claims completion, not world success.
- `OUTCOME_VERIFIED`: fresh scoped sensor evidence satisfies postconditions and current task policy.
- `UNKNOWN`: overlay on last known state with reason/time, never a false success or safe-to-repeat flag.
- `FAILED`/`CANCELLED`: retain partial effects; inspect if effects could remain.

The immutable authorization receipt binds proposal/action payload hash, task/robot/claim IDs, complete task/resource fence set, graph/policy/dependency versions, governance-integrity scan version, witness IDs and validity tick. Admission matches all fields against current state and payload in the tested transition; receipt existence alone is insufficient. Treat it as trusted internal structured data, not a cryptographic signature unless separately implemented.

Store `last_known_state` plus `reconciliation_state` to avoid losing history when marking unknown. Command IDs never recycle; identical replay returns known receipt, mismatched payload rejects. A new command after failure requires fresh proposal/authorization and explicit relation to the previous attempt.

## 4. Simulator receipt durability

A simulator-owned SQLite journal is justified as an external-effect receipt system, not a second planner database. Its schema contains command ID/payload hash/fence/epoch/sequence/last receipt/checkpoint reference only. It cannot grant policy permission or generate task decisions.

Persist an accepted command before exposing its acceptance receipt. The checkpoint/journal pair must describe whether physics state is recoverable exactly. If physics progressed after the last checkpoint, a crash leaves its final effect UNKNOWN. Either replay deterministic recorded inputs from a validated checkpoint or restore to an explicitly new episode and label it. Never assert exactly-once physical effects from SQLite alone.

Back up ops graph + immutable sources + simulator journal/checkpoint manifest with a coherent quiescence point. A restored graph with older fences/policy epoch is not permitted to control a newer simulator without reconciliation.

## 5. Synthetic owner approval

First build uses a **local simulation operator principal**, not fabricated enterprise identity. Two explicit roles: operator/read-only and maintenance-owner/approve. The backend derives principal from the local controlled session; it ignores `actor_id`, `approved=true` or roles supplied by arbitrary request JSON. The approved source fixture roster maps this principal to Corridor C and allowed action scope.

Approval request: release target restriction ID, exact release source revision/span, expected policy epoch, intended scope/effective interval, idempotency event ID. Backend validates principal scope and evidence, commits the ApprovalEvent/Release and advances epoch. UI exposes the full diff before approval; replays with the same event ID are idempotent. This demonstrates authority flow, not production IAM or a cryptographic signature unless actual signing/verification is implemented and tested.

No remote browser access or public control endpoint by default. A future public demo needs separate authentication/CSRF/origin/authorization review. Terminal-seeded releases used by automated tests are labeled trusted synthetic test events, not human interaction.

## 6. Default bounded configuration proposal

Start with a fixed simulation step chosen after stability smoke tests; do not embed assumed real-time speed in policy. Configure per-predicate observation TTLs in ticks, robot footprints/margins, maximum inspection/recovery attempts, control/watchdog intervals, graph/query deadlines and policy propagation timeout in a versioned scenario config. Values are synthetic experiment parameters and must be present in the run manifest.

For initial inspection budgeting propose two additional viewpoints and two recovery attempts per incident, followed by unresolved hold/operator review. Compare with equal-budget baselines. These are scope controls, not literature-derived optimal values.

## 7. Recovery operator runbook (target behavior)

1. Stop new admissions; retain local hold/watchdog.
2. Inspect health/status, not secret values; verify graph key, schema/constraint status and expected durable manifest.
3. Read outstanding command/claim IDs and simulator receipts. Resolve known states; unknown stays held.
4. Validate source hashes/revisions, policy epoch and observation freshness. Reinspect when needed.
5. Synchronize coordinator epoch, simulator dispatch sequence and revocation state.
6. Only then issue new claims and proposals. A healthy socket or process is insufficient readiness.

Do not delete/recreate the pre-existing `graphhacks-fdb` container automatically. New disposable test instances/volumes are explicitly named; destructive lifecycle tests must be scoped and authorized.
