# Program design — types, module ownership and call stack

**Specification only.** Signatures below are intended interfaces, not implemented functions. This fills the step between architecture and PLAN: coding agents should not improvise a second state model. `GRAPH_SCHEMA.md` owns stored names; `RUNTIME.md` owns clocks/command states; `DECISION_CONTRACTS.md` owns model family labels. Implement typed DTOs first, with no executable placeholders that return fabricated success.

## 1. Domain value objects

Prefer frozen dataclasses or strict validation models; reject unknown fields at external boundaries. IDs are opaque typed wrappers, not aliases of display names. No live database handles in a DTO.

```python
# Proposed signatures, not importable code in this bundle.
class VersionVector:
    graph_version: int
    policy_epoch: int
    coordinator_epoch: int
    task_version: int
    dependency_versions: tuple[tuple[str, int], ...]

class Observation:
    id: str
    tenant_id: str
    episode_id: str
    robot_id: str
    occurred_at: datetime
    recorded_at: datetime
    world_tick: int
    expires_tick: int
    predicate: str
    value: bool | float | str | None
    pose: Pose
    frame: str
    visibility: str
    scope: ObservationScope
    quality: ObservationQuality
    sensor_config_hash: str

class ActionProposal:
    id: str
    robot_id: str
    task_id: str
    kind: SkillKind
    parameters: SkillParameters
    expected_versions: VersionVector
    required_predicates: tuple[PredicateRequirement, ...]
    required_resource_ids: tuple[str, ...]
    expected_effects: tuple[ExpectedEffect, ...]  # never Observations

class EvidenceBundle:
    observations: tuple[Observation, ...]
    planning_facts: tuple[PlanningFact, ...]
    governance_candidates: tuple[GovernanceWitness, ...]
    base_permissions: tuple[PermissionWitness, ...]
    integrity_errors: tuple[IntegrityError, ...]
    versions: VersionVector
    completeness: Literal['complete', 'truncated', 'unavailable', 'invalid']

class AuthorizationResult:
    authorization_id: str
    status: Literal['ALLOW','DENY','NEEDS_EVIDENCE','NEEDS_APPROVAL','STALE']
    reason_codes: tuple[str, ...]
    witness_ids: tuple[str, ...]
    versions: VersionVector
    action_payload_hash: str
    valid_until_tick: int

class CommandIntent:
    command_id: str
    proposal: ActionProposal
    payload_hash: str
    claim_id: str
    fence: int
    resource_fences: tuple[tuple[str, int], ...]
    authorization_id: str
    policy_epoch: int
    coordinator_epoch: int
    dispatch_sequence: int
    effective_world_tick: int
```

`datetime` is timezone-aware; ticks are explicit integers. Input `None`/unknown is not false/clear. Structured physical uncertainty is not a model-confidence float. Serialization includes schema version and rejects NaN/infinities, overflow and unit ambiguity.

## 2. Boundary interfaces

| Owner / planned file | Signature | Required failure semantics |
|---|---|---|
| `graph/client.py` | `read_evidence(proposal, tenant_context) -> EvidenceBundle` | Unavailable/truncated/invalid distinct from empty; version-stable bundle |
| `graph/transitions.py` | `append_event(event, expected_hash) -> EventReceipt` | Same ID/different payload is conflict |
| `graph/transitions.py` | `claim_task(request, authoritative_clock) -> ClaimWon | ClaimConflict` | Conditional task+resource mutation, explicit fences, no best-effort winner |
| `graph/transitions.py` | `prepare_command(intent, expected_versions) -> Prepared | Stale | Conflict` | Intent recorded before transport; governance/claims current |
| `policy/authorizer.py` | `authorize(proposal, evidence, claim, now) -> AuthorizationResult` | Pure deterministic rule evaluation; no network/model/side effects |
| `planning/frontier.py` | `ready_tasks(snapshot) -> FrontierResult` | Cycle/truncation explicit; no unmet-prerequisite task |
| `planning/assignment.py` | `assign(eligible_pairs, resource_conflicts) -> Assignment` | Empty is valid; never force infeasible fallback |
| `planning/investigation.py` | `choose_investigation(eligible, assessments, budget) -> Proposal | Hold` | Optional advice cannot add eligible actions |
| `ingestion/source_store.py` | `retain(original_bytes, source_id) -> RevisionLocator` | Immutable content; exact decode/normalization/hash rules |
| `ingestion/promotion.py` | `promote(staged_record, approval_context, expected_epoch) -> PromotionReceipt` | Missing source/identity/authority rejects; corpus output inert |
| `decisions/contracts.py` | `assess(request) -> DecisionResult` | Validated full probabilities + explicit status; deadline/model/version checks |
| `simulation/client.py` | `submit(intent) -> Receipt | UnknownTransport` | Stable command identity; timeout not failed effect |
| `simulation/client.py` | `query_receipt(command_id) -> Receipt | UnknownReceipt` | Not-found differs from reliable proof never admitted |
| `runtime/reconciliation.py` | `reconcile(command_id, current_context) -> ReconciliationResult` | May need sensor reinspection; cannot infer success from workflow cursor |
| `api/reads.py` | `get_witness(decision_id, tenant_context) -> WitnessProjection` | Reconstructed canonical edges, exact source locators |

High-rate simulator stepping and controller loops do not await HTTP, database or model. Their command queue is bounded; heartbeat/watchdog guards handle the disconnected condition.

## 3. One successful call path, with ownership boundaries

```text
SensorServer emits Observation
  -> coordinator.receive_observation
    -> validate DTO and source clock/scope
    -> graph.append_event + derive/refute planning fact
    -> graph.read_ready_frontier and dependent evidence
    -> planner.build_eligible_pairs
    -> optional corpus.retrieve -> exact locator check -> decision.assess
    -> planner.propose (advice affects order only)
    -> graph.read_evidence / authorizer.authorize
    -> graph.claim_task using expected task/resource/policy versions
    -> re-read relevant evidence / authorizer.authorize with current claim
    -> sequencer.prepare_command (stable ID, fence, epoch, sequence)
    -> simulator.submit through ordered ingress
    -> receipt journal + bounded controller
    -> new sensor Observation
    -> verifier checks expected effects under fresh scoped evidence
    -> graph.complete_task or retain failure/unknown
    -> requery affected frontier
```

A pre-claim authorization is provisional: after claim and before admission, revalidate relevant versions. Every failed transition is traceable and bounded; no infinite retry if policies keep changing. Sequencer/revocation contract is RUNTIME, not a best-effort message broadcast.

## 4. Model placement precisely

F-001's text input contains a **single semantic proposition**, a supplied source span and bounded non-authoritative context. Local envelope contains tenant/cache identities and versions; omit raw graph key/internal path from remote payload. Candidates from mandatory governance enumeration cannot be filtered away by F-001. Rerank semantics affect the inspection/display queue, not the set the authorizer evaluates.

F-002 consumes graph-eligible investigation IDs with cost/budget context, not arbitrary language actions. Model `abstain` is a class label distinct from adapter `status=abstain` (selective acceptance rejected); trace both. Choice response must belong to exact offered IDs/version.

## 5. Original fixtures and no hidden ground truth

Use `FIXTURES.md`. Fixture generator may know hidden world state; policy does not receive it. UI uses operator projection; evaluation-only truth endpoint runs in a separate privilege boundary or separate report. Gold semantic labels are test/eval files, never packed into prompts. Source quotes and actor roles are synthetic and explicitly labeled.

## 6. Representative test specifications (future code)

These examples fix behavior, not a ready-made fake authorizer implementation. Proposed test helpers must create actual domain facts/claims, not mock the decision under test.

```python
# tests/unit/test_policy_precedence.py — after G01 domain fixtures exist.
def test_physical_clearance_does_not_lift_current_restriction(world):
    proposal = world.loaded_courier_proposal()
    evidence = world.current_clearance_with_active_restriction()
    claim = world.current_claim_for(proposal)
    result = authorize(proposal, evidence, claim, world.clock.now())
    assert result.status == 'DENY'
    assert 'ACTIVE_RESTRICTION' in result.reason_codes
    assert world.restriction_id in result.witness_ids

# tests/integration/test_policy_witness.py — needs real pinned database.
def test_orphaned_restriction_cannot_disappear_from_authorization(db, world):
    world.seed_policy(db)
    world.remove_support_edge_in_disposable_fixture(db)
    bundle = db.read_evidence(world.proposal, world.tenant_context)
    assert bundle.integrity_errors
    assert world.restriction_id in {w.restriction_id for w in bundle.governance_candidates}
    assert authorize(world.proposal, bundle, world.claim, world.clock.now()).status != 'ALLOW'

# tests/contract/test_command_protocol.py — simulator command ingress, not UI.
def test_same_command_id_with_new_payload_is_rejected(simulator, intent):
    first = simulator.submit(intent)
    assert first.command_id == intent.command_id
    altered = intent.with_different_goal_same_id()
    second = simulator.submit(altered)
    assert second.status == 'CONFLICT'
    assert simulator.accepted_count(intent.command_id) == 1
```

Run one test red before implementation, then green with the minimal real path. Deliberately mutate the gate or use prior code to show the test fails. Assertion examples are expected behavior only; no test above was run in this documentation task.

## 7. Definition of code review done

No unused duplicate truth store; no free-form model action execution; no hidden oracle import; no write-capable query in read agent; no inference-based authority; no incomplete governance set silently accepted; no stale fence/epoch admission; no controller completion as verified effect; no distributed exactly-once claim; no unrelated service/config mutation. Public dependencies have pin/license records. Every requirement has actual test artifacts or an explicit unresolved status.
