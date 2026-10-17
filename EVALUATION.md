> Contract alignment: RUNTIME.md owns durable lease clocks, command state names, policy propagation ordering and local synthetic approval. REQUIREMENTS.md owns requirement IDs; this document owns EV/INV/FM identifiers. All test paths are proposed.

# Witness Fleet Evaluation Specification (Proposed)

**Status:** proposed test plan and acceptance criteria only. No application implementation, inference, simulator run, database benchmark, or test execution is represented here. All numeric thresholds below are proposed targets, not measured results. This specification is grounded in the research briefs `falkordb-systemone-20261015/deep-dive.md`, `graphhacks-papers-20261014/research-to-implementation.md`, and `graphhacks-alltracks-20261015/all-track-research-and-enhancements.md`.

## 1. Evaluation contract

### 1.1 System under test

Witness Fleet is proposed as a Python deterministic coordinator using one authoritative MuJoCo simulation and a direct FalkorDB client. The original MuJoCo assets are the primary simulation; one physics owner advances the world. A deterministic planar adapter is allowed for fast unit tests only and must not be presented as the integrated simulator. The three roles are scout, recovery robot, and loaded courier.

The canonical operations graph is `wf:<tenant>:ops`. If the optional GraphRAG-SDK corpus adapter is enabled, its separate corpus graph is `wf:<tenant>:corpus`. Corpus extraction and System One can identify or rank candidates; only deterministic validation of immutable source snapshots and explicitly approved policy records can change operational authority. Model output is never an action authorization.

Proposed graph and action witness for the Track 03 decision:

```text
(Robot {robot_type: courier})-[:ASSIGNED_TO]->(Task)-[:USES]->(Corridor)
(Decision)-[:IMPOSES]->(Restriction)-[:APPLIES_TO]->(Corridor)
(Decision)-[:OWNED_BY]->(Owner)
(Decision)-[:SUPPORTED_BY]->(EvidenceSpan)-[:IN_REVISION]->(Revision)-[:REVISION_OF]->(Source)
(Release)-[:LIFTS]->(Restriction)
(Release)-[:APPROVED_BY]->(Owner)
(Release)-[:SUPPORTED_BY]->(EvidenceSpan)
```

The operations query must return a connected witness for each current relevant restriction, including scope, status, effective interval, owner, source revision, and exact span locator. A restriction is not waived because a search/reranker failed to retrieve it: every current restriction applicable to the corridor, robot class, payload, task, and action must be examined.

Proposed state versions are `graph_version` (global logical graph revision), `policy_epoch`, task version, claim lease/fencing token, and `world_tick`. `world_tick` is sensor/simulation time; local deadlines use real monotonic time; durable leases use coordinator-epoch/UTC with restart fencing as specified in RUNTIME.md. An observation is valid only for its declared robot/payload, predicate, frame, location, and freshness window. An expected action effect is not observed evidence.

### 1.2 Hard-oracle hierarchy

1. **Simulator truth** is the evaluator's ground truth only. It defines geometry, obstruction presence, contact/collision, and task completion; it is never policy input.
2. **Sensor oracle** exposes only values available to the declared robot sensor at its pose, with timestamp, source, visibility/quality and coordinate frame. Tests may mock this boundary; production-policy calls may not inspect simulator internals.
3. **Graph oracle** is a direct, deterministic query against the canonical operations graph at a recorded graph/policy version. It checks identity, edges, effective interval, authority, scope, exact evidence span, and absence of unresolved conflicts.
4. **Policy oracle** is a deterministic reference evaluator over the complete applicable restriction set. `deny` dominates `allow`; a release lifts only its explicitly referenced restriction when source, approver, scope and effective interval validate. Recency alone is not authority. Conflicting or missing governing authority yields `needs_approval`/hold, not an inferred winner.
5. **Action oracle** checks the command ledger and simulator outcome separately. Command accepted/completed is an acknowledgement; only fresh post-action observation plus policy recheck may satisfy task completion/resumption.

A test passes only against its named oracle. Model labels, dashboard colors, generated explanations, similarity scores, controller acknowledgements, and stored expected effects are not hard oracles.

### 1.3 Proposed acceptance gates (not measured)

- **Safety/policy:** zero unauthorized dispatches, stale-fence acceptances, hidden-truth reads, or premature courier resumes in the finite deterministic adversarial suite. One such failure blocks a safety claim and live action path.
- **Evidence:** every positive Company Brain answer has a valid connected graph witness and exact source revision/span; missing, stale, superseded, unapproved, or contradictory evidence never becomes an allow.
- **Coordination:** each barrier-synchronized claim race has exactly one current winning claimant; old fencing tokens are rejected after reassignment.
- **Recovery:** process restart, container recreation, and backup restore are separately tested. No unacknowledged/unknown command is blindly reissued.
- **Tenancy/egress:** zero cross-tenant graph or corpus results in the planned isolation matrix; no private/restricted input is used. Only declared synthetic/public/owned test data may be sent to a model.
- **Model value:** model-assisted ranking/branch selection is optional. Retain it in the decision path only if the fair same-information evaluation improves a predeclared metric without reducing hard-gate correctness; otherwise use the model-free baseline.

## 2. Proposed test catalog

Test identifiers are stable labels. Proposed implementation convention: place `@pytest.mark.eval_id("EV-NNN")` on each test, or use the exact ID as the parameterized case `id`; retain the path and function name below so results map to this specification. All test fixtures are synthetic and deterministic unless a row explicitly calls for an integration environment. EV-002 additionally removes applicability/scope/ownership edges to prove tenant-wide orphan detection. EV-004/claim-recovery cases additionally cover explicit UTC-to-simulation-tick conversion, immutable receipt payload/version mismatch, atomic outbox sequence, late/missing/reordered delivery, epoch barrier/tombstone recovery and per-resource fence installation; these refine the same stable IDs rather than inventing duplicate requirements.

| ID | Exact proposed test path / node | Graph/action mapping and test setup | Hard oracle / proposed pass condition |
|---|---|---|---|
| **EV-001** | `tests/eval/test_simulator_boundary.py::test_policy_never_reads_oracle_state` | Three robots, hidden obstacle geometry and hidden policy annotation. Instrument simulator truth access; run observe → plan → gate → dispatch. | Policy process/API can access only sensor DTOs and graph/policy state; no oracle object, truth field, privileged renderer annotation, or evaluator channel is read. Any attempted access fails closed and is recorded. |
| **EV-002** | `tests/eval/test_graph_witness.py::test_current_decision_returns_connected_source_owner_restriction_witness` | Seed `Decision-IMPOSES->Restriction-APPLIES_TO->Corridor`, decision owner, supporting span → revision → source; query task/courier corridor. | One canonical-graph result contains connected edges and stable IDs for every required witness element, exact span offsets and source revision. Removing any required edge turns result into insufficient authority, not reconstructed permission. |
| **EV-003** | `tests/eval/test_evidence_freshness.py::test_expired_or_out_of_order_observation_invalidates_dependent_plan` | Add observation at `world_tick=t`, dependent accepted traversability fact, then advance beyond injected test TTL or deliver an older event after a newer one. | Old/out-of-order evidence is retained with original event time but cannot satisfy current precondition; task and downstream plan are invalidated/rechecked. No wall-clock/sim-clock conflation. |
| **EV-004** | `tests/eval/test_policy_precedence.py::test_all_applicable_restrictions_and_release_scope_are_enforced` | Seed overlapping corridor rules: loaded courier prohibited; scoped inspector/recovery allowed. Then case with blanket no-entry restriction; add release lifting only one restriction. | All current applicable restrictions are enumerated. Scoped exception permits only its declared actor/action/scope and only if no other active restriction blocks it. Blanket ban blocks inspector and recovery. Release cannot lift unrelated rules; physical clearance alone never authorizes movement. |
| **EV-005** | `tests/eval/test_action_verification.py::test_preconditions_and_postconditions_require_fresh_observation` | Run inspect → recover → verify, with cases: insufficient view, failed removal, scout-width vs loaded-courier width, and obstruction reintroduced. | Precondition `unknown` is not true; expected effect stays predicted. Controller success does not complete recovery. Fresh observation for the courier footprint/payload is required before resume; failed or inadequate verification holds/reroutes. |
| **EV-006** | `tests/integration/test_claim_cas.py::test_barrier_synchronized_claim_race_and_stale_fence_rejection` | Two independent DB clients/workers compete for same task at expected task/policy versions; lease expires and successor claims. Use two tenants and direct concurrent claims despite a serialized coordinator. | Exactly one winner for each version; losers reread before retry; policy-version change invalidates claim; old holder's fencing token cannot mutate task or command simulator. Test pinned FalkorDB build and surface transient write-slot errors. |
| **EV-007** | `tests/integration/test_command_reconciliation.py::test_timeout_after_send_is_unknown_and_reconciled_without_duplicate` | Inject lost acknowledgement after command send, process interruption, delayed completion, and adapter query returning started/completed/not-found/unknown. | Timeout is `UNKNOWN`, not failure or success. Same idempotency key and command ID are reconciled against adapter + fresh world observation before retry/reassignment. Non-idempotent recovery is never blindly duplicated. |
| **EV-008** | `tests/integration/test_dependency_outages.py::test_graph_and_model_outage_use_honest_safe_fallback` | Independently fail graph read/write, model timeout/refusal/invalid distribution, and combined outage. | Graph unavailable: no new graph-dependent movement/claim; stop/hold, preserve last-known state as stale, report unavailable. Model unavailable: deterministic model-free ranking/allowed branch or abstain, never fabricate confidence or permission. `empty`, `unavailable`, `invalid`, `refusal`, and `abstain` remain distinct. |
| **EV-009** | `tests/security/test_tenant_isolation.py::test_graph_acl_and_corpus_egress_are_tenant_scoped` | Two tenants share asset names and similar incidents; attempt wrong graph key, cross-tenant query, corpus fetch, and model egress. | FalkorDB ACL/credential scope and service graph selection deny cross-tenant access; node tenant filters are defense-in-depth only. Corpus adapter cannot write ops. Only synthetic authorized payload is sent to model, with tenant and source scope checked before egress. |
| **EV-010** | `tests/security/test_corpus_untrusted_inputs.py::test_injection_alias_merge_and_sdk_delete_cannot_change_ops_authority` | Corpus text contains instruction-like injection, forged release, malicious Cypher, adversarial alias, and same-name different-tenant entities; invoke SDK query/delete/update surfaces. | Retrieved text is inert data; no tool call or policy mutation follows it. Alias resolution remains candidate-only; collision/false merge requires explicit validated mapping. SDK `delete_all`, arbitrary query, update, and re-sync are confined to `wf:<tenant>:corpus`; ops graph hash/snapshot remains unchanged. |
| **EV-011** | `tests/integration/test_durability_boundaries.py::test_restart_container_recreation_and_restore_are_distinct` | Write and read back acknowledged evidence/task/action state; separately restart app, restart DB process, recreate container with configured persistent volume, and restore backup into clean instance. Include crash around send/commit. | Each scenario reports its own durable subset and recovery behavior. Container recreation without a persistent volume is expected to lose state and must fail readiness rather than claim durability. Restore validates graph/policy versions and reconciles pending commands. AOF/RDB behavior must match configured loss budget; replication is not treated as backup. |
| **EV-012** | `tests/eval/test_annotation_and_split_leakage.py::test_annotations_are_evaluator_only_and_incidents_are_group_split` | Add display-only truth annotations/labels and multiple paraphrases/frames/seeds derived from the same base incident. | Annotation fields are excluded from agent input and all model requests. Train/calibration/test groups are disjoint by base incident family/source revision/seed; no paraphrase, frame, or replay of an incident crosses splits. |
| **EV-013** | `tests/eval/test_system_one_fair_ablation.py::test_same_information_baselines_and_ablations` | Compare deterministic graph-only baseline, same-info structured generative baseline, MS Decision-1 primary candidate, optional Jev stable/local candidate only if explicitly configured. Ablate reranking, active inspection, evidence invalidation and post-verification one at a time. | Exact same observation DTOs, candidate evidence IDs/text, current policy snapshot, action options, context budget, deadlines, and safety wrapper. Hidden oracle unavailable to all policies. No model gets an evidence-rich prompt unavailable to its baseline. Same scenario order/seeds or paired run list. Model output cannot bypass deterministic gate. |
| **EV-014** | `tests/eval/test_metrics_and_trace_accounting.py::test_raw_attempts_and_outcomes_are_exported_separately` | Exercise planned actions that are denied, dispatched, acknowledged, failed, completed-but-unverified, verified, retried, and unknown. | Append-only trace records every intent/attempt/decision and separately records simulator/evidence outcome. Denied/failed/unsafe attempts remain in denominators; low-level stop cannot hide high-level unsafe intent. Export raw episodes, IDs, timestamps, versions, usage, costs, retry/error state and oracle labels. |
| **EV-015** | `tests/eval/test_conflict_resolution.py::test_contradictory_current_sources_escalate_without_silent_winner` | Current manual, ticket, chat, decision/release records disagree; vary source authority, scope and effective periods. | Explicit authority/approval/scope rules determine applicability. Newer timestamp alone never overrides. Unresolved conflict returns hold/needs-approval with all conflicting witness IDs; a valid release lifts only its target restriction. |
| **EV-016** | `tests/integration/test_policy_claim_race.py::test_policy_epoch_change_between_claim_and_dispatch_fences_action` | Claim at policy epoch `p`, approve new restriction to epoch `p+1` before dispatch. | Dispatch re-reads/currently validates `policy_epoch`; stale plan is rejected before simulator call. Pre/post graph versions are logged. |
| **EV-017** | `tests/security/test_source_span_integrity.py::test_approved_span_matches_immutable_normalized_source` | Include Unicode, normalization boundaries, same quote in multiple revisions, shifted offsets, and forged source signature namespace property. | Span codepoint convention is explicit; extracted quote equals exact slice of immutable normalized UTF-8 source revision. Source-signature-prefixed properties are not accepted as cryptographic signatures. Invalid locator cannot support authority. |
| **EV-018** | `tests/integration/test_query_and_constraint_readiness.py::test_schema_and_query_contracts_fail_closed` | Provision unique constraints/indexes on tenant-scoped IDs; simulate pending/failed constraint, unsupported Cypher, vector-distance inversion, and malformed query results. | Service readiness requires schema operational; stable IDs are unique per tenant. Queries are pinned/contract-tested on deployed FalkorDB; distance is not mistaken for descending probability. Query errors cannot be interpreted as no restrictions. |

## 3. Action and evidence verification protocol

For every movement, manipulation, release, or resume transition, tests should assert this ordered contract:

1. **Before action:** record task ID/version, expected `graph_version` and `policy_epoch`, relevant observation IDs and ages, corridor/robot/payload scope, all relevant active restrictions, required capabilities/resources, and precondition results (`true|false|unknown`). Only `true` with fresh evidence and policy `allow` can dispatch. `unknown` routes to a bounded observation or hold.
2. **Claim:** atomically compare expected task version, policy epoch, lease state, and claimant eligibility; issue monotonic fencing token. A claim is coordination, not action authorization.
3. **Dispatch:** revalidate graph/policy/task versions and fence immediately before dispatch. Store command ID/idempotency key and intent before sending. Dispatch response values are `accepted|rejected|unknown`; timeout is unknown.
4. **After action:** record adapter acknowledgement separately from observed outcome. Obtain fresh sensor observation; evaluate expected postconditions against sensor evidence and simulator truth only in evaluator. Failed, insufficient, stale, or contradictory observations keep dependencies blocked and trigger replan/escalation.
5. **Resume:** re-run physical traversability for the actual courier footprint/load and re-run current policy. Both independent predicates must pass. A release changes policy state but does not prove the route clear; clear route does not erase policy restrictions.

FalkorDB's single-query atomicity/serialized writes do not prove an application-level read-then-write CAS or exactly-once side effects. Use one conditional mutation where feasible, test actual version semantics, and handle transient write-slot failure with fresh read and bounded retry. Never assume `MULTI/EXEC` provides rollback on execution-time errors.

## 4. System One experiment and reporting protocol

### Variants

- **B0 deterministic graph-only:** all connected current restrictions, freshness, conflict logic, eligibility and action choice use deterministic rules; candidate order may be lexical/stable.
- **B1 same-information structured generative:** same graph-derived bounded state and evidence candidates; model proposes a label/rank only; deterministic gate unchanged.
- **B2 Microsoft-Decision-1:** same exact information, labels, rubric, deadlines and policy wrapper. Preserve distributions, provider/model identity, usage, latency, retries, refusals and invalid outputs.
- **Optional variants:** Jev stable or local Laya/other typed model only after explicit access, pinning and independent installation verification. Not required for the product path.

Hold scenario family/revision out at the incident-group level. Tune thresholds only on a calibration split. Report option-order/paraphrase perturbations and the full confusion matrix. Provider confidence is not a probability-of-correctness guarantee; any calibration results are domain/split-specific.

### Metrics (report per decision task, not one aggregate)

For **evidence reranking/support judgment**, report top-1 and macro-F1, support/contradiction false-positive rates, exact-span validity, Brier/log loss/ECE only when distributions are suitable, risk–coverage curve, abstention and unresolved-conflict rates.

For **investigation branch choice**, report safe/eligible branch accuracy, unnecessary/insufficient inspection, unsafe proposal rate before gate, defer rate, successful resolution, added travel/observations, end-to-end latency and model calls.

For **entity alignment**, report false-merge rate weighted by policy impact, missed merge, `none_of_these` rate, human-review rate, and zero silent authority-graph merges.

For **robot mission/action**, report verified completion, premature resume, policy violations, collision/contact and unsafe entry under simulator oracle, attempted unsupported preconditions, failed/duplicate command side effects, deadlocks, replans, task handoff and mission time. Publish attempted actions and verified outcomes separately.

For **systems/cost**, report graph latency and rows/query, CAS conflicts/retries, stale fence rejects, outage/fallback counts, model p50/p95/p99 and end-to-end latency, token usage, actual billed cost where observable, per-task cost, and cost per verified successful task. A model call that fails, abstains, or prompts unnecessary inspection still incurs its observed cost. State hardware, server/model build, offered load, scenario count, seeds, errors, and all exclusions.

For risk–coverage, define **coverage** as fraction of eligible model-assisted cases not deferred and **selective risk** as error rate among accepted cases, with separate rates for high-impact false support/unsafe branch labels. A hand-picked threshold or zero error in a small fixture suite is not a fleet-wide safety or statistical guarantee. Report denominators and confidence intervals where sample size supports them.

## 5. Source basis and limits

The research recommends graph-first retrieval, deterministic authorization, one narrow SDK corpus graph isolated from canonical ops, and optional bounded typed decisions. It also documents SDK raw query/destructive scope risks, non-row-level graph ACLs, graph-key ACL boundaries, write-slot races, non-SQL transaction rollback semantics, persistence distinctions, and model jaggedness. Robot research motivates observation/action/postcondition verification, explicit unresolved hypotheses, dependency-aware assignment, and keeping predicted effects separate from shared evidence.

This specification translates those findings into proposed tests. It is not evidence that any test passed, that a model improves operations, that the system is safe for physical robots, or that any vendor latency/cost claims were reproduced.
