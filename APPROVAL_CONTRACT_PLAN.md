# Trusted local approval contract implementation plan

> **For Hermes:** Use subagent-driven-development for the bounded pure contract and sequential SPEC then QUALITY review.

**Goal:** Serialize a closed, immutable approval intent with server-resolved actor identity, without allowing request JSON to nominate the actor.

**Architecture:** A new runtime-owned module imports existing Pydantic and the accepted domain hashing helper. The request-to-command factory receives a configured local principal explicitly; it neither authenticates remote users nor mutates a graph. No API/controller/bootstrap/graph/protocol behavior changes belong to this slice. Later approval activation must atomically commit the approval, epoch increment, target state and sequenced outbox evidence.

**Tech stack:** Project Python/Pydantic; offline pytest and Ruff. No new dependencies, provider, credentials or network.

## Verified acceptance checkpoint

The pure contract is complete at source SHA-256 `804ae4a155856c0d9721568d7df33378715f0908a7aae44ed93b82b304742844` and test SHA-256 `4f59016b383623e9b635261679522d3298daa8f13a22b4ed3a76c3503e7507bd`. Completed independent SPEC `deleg_798703c7` and QUALITY `deleg_d529fed5` both PASS at these hashes and the immutable domain prerequisite; each ran63 tests. Fresh parent63 tests in0.16s and scoped Ruff pass. Reviewer advice to persist additional read-only Mapping/whitespace/max-boundary probes is non-blocking. This accepts only inert immutable intent plumbing, not authentication, roster authority, graph activation or API integration. The authoritative next slice below remains gated; admission HOLD and current runtime storage review are not closed by this acceptance.

## Ownership and prerequisite gate

- Sole implementer owns `src/witness_fleet/runtime/approval.py` and `tests/contract/test_approval_command.py`.
- Accepted immutable prerequisite `domain.py`: SHA-256 `e9c8d15052402afad95274bca30aa77c33faf22a250ee3e025874a2737178b51`.
- No existing declaration of `ApprovalCommand` or `TrustedLocalPrincipal` was found in the project source/tests.
- All current graph/runtime/lookup/UI reviewers are read-only and own different paths.
- Never edit protected AGENTS.md, CLAUDE.md or SKILL.md. Never commit the dirty repository wholesale.
- This module is an inert contract, not permission to integrate before graph/runtime/reconciliation acceptance.

## Task 1: One pure tracer bullet

Files: create `runtime/approval.py`, test `tests/contract/test_approval_command.py`.

Public surface:

```python
class TrustedLocalPrincipal(BaseModel):
    actor_id: str
    tenant_id: Literal['demo', 'other']
    role: Literal['maintenance_owner']
    trust_mode: Literal['configured_local']

class ApprovalCommand(BaseModel):
    event_id: str
    target_id: str
    action: Literal['approve'] = 'approve'
    expected_policy_epoch: int
    actor_id: str
    tenant_id: Literal['demo', 'other']
    notes: str = ''

def approval_command(*, request: Mapping[str, object], target_id: str,
                     principal: TrustedLocalPrincipal) -> ApprovalCommand: ...
```

Both models are strict, frozen and extra-forbid. IDs are exact strings, length 1..128, no NUL; do not strip or URL-normalize them. Notes are exact strings of length at most512. Epoch is an exact nonnegative integer, with booleans and numeric strings rejected. Request keys are only event_id, expected_policy_epoch and optional notes; actor_id/tenant_id/target_id/action are not accepted from request data. Principal must be an actual validated TrustedLocalPrincipal, not a mapping or arbitrary lookalike. This is internal provenance plumbing, not cryptographic protection against arbitrary in-process construction.

Write the valid factory test first, add only an importable throw-only factory/classes as necessary, and record a collected behavioral NotImplementedError RED before implementation. Minimal GREEN copies actor and tenant from principal, target from the route-owned argument and only permitted intent fields from the request. Do not preimplement edge-case validators before their failing tests.

Run `.venv/bin/python -m pytest -q tests/contract/test_approval_command.py` after each tracer bullet.

## Task 2: Strict request boundary

Add regressions one at a time for caller actor/tenant/target/action, missing epoch, boolean/float/string/negative epoch, nonmapping request, wrong principal type, extra model fields, empty/oversized/NUL IDs and oversized/nonstring notes. Accepted event IDs such as literal%2F, '.', '..', unicode and slash must retain exactly the same value. Valid nonzero epoch and JSON round trips must preserve all fields; attempted mutation must fail. Add tests that compare supplied mappings before/after to establish no input mutation.

This unit does not test roster authorization or current epoch equality; those are authoritative graph responsibilities. It must not read sources, graph, environment or local configuration itself, and must not create a caller identity fallback.

## Task 3: Freeze and review

Run focused contract tests, existing `tests/unit/test_domain.py`, scoped Ruff and git diff --check. Record source/test hashes and immutable domain hash. Require independent final SPEC then QUALITY reviews at those hashes. No consumers may redeclare these symbols or use ApprovalCommand as an externally trusted request schema.

## Next authoritative slice - not yet executable

Once the pure contract and graph/runtime prerequisites pass both reviews, a separately owned approval writer may accept ApprovalCommand, source-bound governance context and trusted clock/lease state. The single authoritative CAS must match approval-time expected policy epoch, current graph/governance version, live coordinator lease and exact target/owner scope, then atomically write ApprovalEvent, target activation/release state, policy epoch increment, dispatch sequence increment and POLICY_ACTIVATION with proof_id bound to that approval. Concurrent same-epoch different approvals must yield exactly one winner; exact retries replay and conflicting IDs reject. Historical approval validity is checked against its exact committed sequenced event, never against today's possibly later policy epoch. No integration implementation is authorized by a test of this pure contract alone.
