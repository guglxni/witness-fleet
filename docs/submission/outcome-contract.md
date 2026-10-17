# OutcomeStore contract

## Verification contract

A command can reach `OUTCOME_VERIFIED` only when all of these hold:

- The command is the retained, hash-verified command envelope and remains in an allowed live command state.
- The coordinator holder, epoch, UTC lease, graph version, active claim lease/fence, task version/fence, authorization, and required resource fences/versions still match at the single graph CAS.
- The Task and Corridor identify exactly one retained Episode (`Episode-CONTAINS->Task` and `Episode-OCCURRED_AT->Corridor`). Every supplied observation's payload episode ID must match that episode.
- Every proof observation is typed, immutable retained telemetry with matching canonical JSON hash and flattened approved properties, correct tenant/robot/corridor scope, true value, visible visibility, valid sensor configuration, not future-dated, and unexpired at the requested world tick.
- The expected-effect set is nonempty and the distinct set of proof predicates is exactly that set. No undeclared extra predicate is accepted.
- Each proof's Observation node is connected to the exact selected Episode by `CONTAINS` within the same CAS that marks the Command/Task terminal, releases the Claim, increments graph/task versions, commits hashes, and creates `VERIFIED_BY` edges.

`VERIFIED_BY` is canonical schema `(Command)-[:VERIFIED_BY]->(Observation)`. Exact idempotent replay is read-only only while its serialized outcome/hash, terminal Task/Claim states, actual `VERIFIED_BY` target set and canonical payload hashes, and exact Episode-to-Observation edges all match the committed evidence refs. Missing, changed, or additional evidence relations fail closed.

## Resource release semantics

A successful outcome makes the Claim `RELEASED`; this is the release mechanism, not a Resource lifecycle transition. Reservation edges remain immutable historical relationships, but claim eligibility excludes reservations whose Claim is no longer ACTIVE/UNKNOWN/REASSESS. The regression verifies that a competing task can subsequently reserve a shared resource through the normal `claim_task` API. Resource node fields remain unchanged by outcome completion.

## Failure outcome

A `failed` outcome is not sensor verification. It may commit with no observations and transitions the Command and Task to `FAILED`, Claim to `REASSESS`, and the graph version by one. Any supplied observations must still satisfy retained identity and exact episode association checks; failed outcomes do not require success-value/visibility gates.
