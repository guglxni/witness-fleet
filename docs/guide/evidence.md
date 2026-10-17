# Evidence, provenance, and verification language

## Provenance chain

The mission retains synthetic source bytes/text with revision hashes and exact span locators; the canonical ops graph links `Source`, `Revision` and `EvidenceSpan`, and validated decisions/release records reference those spans. Source validation checks retained identity, normalized content and quote offsets ([`ingestion/source_store.py`](../../src/witness_fleet/ingestion/source_store.py), [`graph/governance.py`](../../src/witness_fleet/graph/governance.py)). This demonstrates traceability of the stored claim to retained bytes. It does not prove a source is true, complete or sufficient authority by itself.

Sensor observations carry observer, episode, frame pose, tick, visibility, expiry, configuration identity and scope. Recovery effect proof links command receipt, contact and measured displacement to a separate fresh visible observation ([`runtime/effects.py`](../../src/witness_fleet/runtime/effects.py), [`runtime/sensing.py`](../../src/witness_fleet/runtime/sensing.py)). Observations are not permissions; controller acknowledgment is not outcome proof.

## Evidence states to preserve

| State/evidence | Supports | Does not support |
|---|---|---|
| Retained source/span with valid hash and offsets | Exact byte/text locator and identity | Truth or authorization without governance review |
| Visible fresh observation with matching scope | The particular observed predicate within its TTL | A different robot, payload, route or later time |
| Graph `ALLOW`/authorization receipt | Deterministic proposal admission for exact versions, payload, claim and horizon | Execution, delivery or unchanged-current-state admission |
| Simulator `ACCEPTED`/`RUNNING`/`CONTROLLER_DONE` | Recorded controller lifecycle state | Physical success, safe-to-repeat after lost ack, or graph task completion |
| Ordered event application receipt | Simulator applied that event identity in order | Physical effects or successful postcondition |
| `OUTCOME_VERIFIED` task/command | Required current observed postconditions were retained and accepted | Generalization outside the verified episode or physical safety certification |
| `UNKNOWN` / HOLD | Outcome or authority is unresolved; new motion must not be assumed safe | Failure, completion, no effect, or permission to retry |

The command state definitions and simulator journal contract are in [`RUNTIME.md`](../../RUNTIME.md) and [`services/simulator/journal.py`](../../services/simulator/journal.py). Current SC-001 e2e assertions are visible in [`tests/e2e/test_integrated_fleet.py`](../../tests/e2e/test_integrated_fleet.py).

## Reading test and report claims

Use precise levels:

- A source file exists: implementation is present.
- A test asserts a behavior: a defined test contract exists.
- A test executed and passed: that exact command/environment generated passing evidence.
- A native artifact exists: the specified native component executed and emitted that artifact.
- Full mission succeeded: only a fresh end-to-end run with real graph integration, native execution and retained postconditions justifies that statement.
- Deployment works/physical safe: requires separate deployment/commissioning evidence; local tests do not establish it.

Historical reports under `report-artifacts/`, `artifacts/` and `evidence/` have provenance and scope. Read the report itself and its exact source hashes/command; do not infer a current test total from a filename, old handoff or proposed requirement. This documentation change did not execute application, graph, model, or native fleet tests.

## Reproducing verification

Existing repository helpers include `python3 scripts/verify_docs.py`, `python3 scripts/verify_math_examples.py`, project pytest commands in [`BUILD.md`](../../BUILD.md), the [`scripts/test_all.py`](../../scripts/test_all.py) runner, native capture instructions in [`RUNBOOK.md`](../../RUNBOOK.md), and web tests in root [`README.md`](../../README.md). The scopes are not interchangeable. The diagrams have their own render workflow at [`docs/diagrams/README.md`](../diagrams/README.md).

Never turn an unknown metric into zero, a skipped suite into a pass, an offline contract fixture into live provider evidence, or a planned deployment into a hosted service claim.
