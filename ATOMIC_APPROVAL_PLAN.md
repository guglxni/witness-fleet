# Next atomic approval writer - dependency-gated design

Status: **proposal only; no writer or activation implementation exists**.

Program-design review `deleg_e0c8961b` ended in a Broken pipe API failure after source inspection, without a final design/verdict or executed acceptance tests. It is not approval to implement this writer. The modification warning is cross-worker metadata: the reviewed transcript contains no source write/patch. Pure approval source/test/domain hashes remain unchanged; storage has separate coordinator-lease work and is not attributed to this read-only reviewer. No replacement review or integration was started from this delayed completion notice.

## Measurable acceptance

A configured local maintenance-owner approves a single exact staged Release against its approval-time policy epoch. One authoritative graph transaction writes the approval and its exact activation evidence while advancing policy and outbox versions. Competing same-epoch approvals have one winner, retries are exact-ID idempotent, stale or corrupted inputs mutate nothing, and historical approvals remain valid after later policy epochs only through their own exact sequenced proof.

## Ownership and prerequisites

1. Pure principal/ApprovalCommand contract: two-file serialized unit in APPROVAL_CONTRACT_PLAN.md; final exact-hash SPEC and QUALITY required before any consumer.
2. Current GraphStore snapshot closure/claims: current claim-time fractional-second repair must pass both gates. Original32 green tests missed it; old graph review does not close it.
3. TransitionStore cached-counter slice: narrow acceptance does not cover coordinator lease comparisons. Related proposed/retained lease semantics require a separate repair/review.
4. Governance `validate_governance`: strict retained source/scope/roster validity exists but approval-time atomic CAS and exact activation provenance do not.
5. Journal admission test-strengthening review currently has an unanswered approval timeout. No retry or substitute review for that outcome until consent.
6. Reconciliation hold/cancel transport is still absent. Do not claim restart/controller acceptance from an approval writer.

Potential ownership: new runtime/approval_writer.py and one new integration test module, one owner. Do not modify storage.py while its coordinator lease unit is owned elsewhere. Do not add shadow ApprovalCommand definitions, new raw HTTP authority fields, or a second outbox sequencer.

## Explicit seam to review before implementation

The writer receives `ApprovalCommand`, an exact retained-source governance snapshot validated at a captured graph version, current authoritative coordinator lease/holder state, and a world tick. Actor comes only from the configured local principal, with tenant and owner/roster scope validated server-side. Request JSON cannot supply actor, owner role, approval state, proof_id, an arbitrary graph payload or a policy increment.

Proposed method `approve_release(command, *, effective_world_tick)` internally collects and validates the entire source/owner/restriction/release chain. It must fail closed on ambiguous multiple edges, detached roots, stale post-inspection facts, foreign tenant/source, expired observations or invalid coordinator lease. No arbitrary callback runs within the transaction.

The one graph CAS query must match at least:

- Exact tenant and release ID, staged state, target restriction edge and named owner.
- Captured graph_version and governance_integrity_version from the validated complete snapshot.
- Current approval-time expected_policy_epoch supplied by the command.
- Exact live coordinator epoch/holder/lease identity, with true datetime comparisons rather than variable-precision ISO lexical ordering.
- Unique command/event identity; existing identity must be checked as exact retry or conflict, not duplicate CREATE.

The same transaction creates ApprovalEvent with expected_policy_epoch and exact actor/target/intent identity, activates the Release, increments policy_epoch, graph_version and dispatch_sequence, and creates POLICY_ACTIVATION whose payload contains the new epoch, expected previous epoch and proof_id bound to this ApprovalEvent. Source revision/span and exact restriction/release bindings must be durable and auditable. Parent/worker must verify real FalkorDB transaction rollback and uniqueness behavior rather than assume syntax is atomic.

## Provenance validation amendment - serialized separately

Existing `validate_governance` must not newly compare a historical ApprovalEvent.expected_policy_epoch with today's FleetState.policy_epoch. Instead a later accepted provenance seam binds that approval's exact ID/tenant/target/actor/hash and approval-time expected epoch to the durable sequenced POLICY_ACTIVATION which advances that epoch. Duplicate/conflicting/missing activation evidence invalidates approval. A mere nonempty proof_id is not authenticity.

This amendment will invalidate legacy fixtures that pretend approval via a detached trusted dict; adjust only explicitly declared added provenance, preserving every existing source/owner/scope negative test. Fixture-only bypass is not acceptable.

## Regression-first sequence

1. Collected inert writer stub test yields behavioral NotImplementedError. Missing import/DB auth is diagnostic, not RED.
2. Valid staged exact approval creates exactly one ApprovalEvent, one activation, one sequence/epoch increment; read back exact targets and validate updated canonical witness.
3. Two independent database connections submit different IDs with same expected epoch through the production writer; deterministic start barrier; one winner, no second activation or epoch change.
4. Exact replay returns the original receipt after the policy epoch has advanced, without a new graph version; conflicting same event ID/intent is rejected.
5. Stale expected epoch, graph revision, owner scope or lease yields no mutation. Boundary cases include whole-second/fractional-second lease representations and lease equality.
6. Crash/checkpoint replay before and after graph commit is verified via outbox reads, not by inventing simulator effects.
7. Historical witness remains valid after unrelated later epoch only through its bound activation. Forged activation, bool/float counters, orphan proof, target/actor mismatch or reused proof reject.

Only after this writer and provenance seam pass final SPEC then QUALITY may canonical bootstrap/controller consume them. An inert contract, healthy API, policy test, scripted controller or direct MuJoCo skill is never the integrated graph-authorized three-robot incident result.
