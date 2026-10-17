# Witness Fleet implementation plan

> **For Hermes:** Use the subagent-driven-development skill when execution is authorized, with disjoint tasks and spec-compliance review before code-quality review. For other coding agents, follow the same dependency gates and test-first discipline.

**Goal:** build one working, evidence/authority-aware three-robot incident product with demonstrable FalkorDB causality, durable coordination and a measured optional semantic assessor.

**Architecture:** original MuJoCo simulator and bounded skills; canonical per-tenant FalkorDB operational graph; deterministic authorization and command reconciliation; one isolated GraphRAG-SDK corpus lane; optional typed-decision adapter; API/dashboard projections.

**Tech stack:** Python, FalkorDB official client/server, MuJoCo, isolated GraphRAG-SDK, FastAPI, React/TypeScript/Vite. Exact package locks/digests are selected through compatibility tests, not guessed here.

**Current status:** documentation only. Every code path and command below is a **future target**. Do not report expected outcomes as real output. No application code is included to falsely imply progress. Each numbered step is a small test/edit/run/review action; stop at a failed gate instead of building atop it.

## Common task pattern (all gates)

1. Write the named failing test for the precise contract.
2. Run the targeted test; record actual failure proving absent behavior.
3. Implement the smallest typed production path (never weaken the assertion).
4. Run targeted tests, then related negative paths; record actual results.
5. Review spec compliance then code quality, especially trust boundaries.
6. Commit only changed files after diff review; update requirement evidence. No remote push without approval.

Use `uv run pytest <path> -q`, `uv run ruff check .`, `uv run mypy src`, and frontend `npm --prefix web run test` only after G00 defines these tools/scripts. Missing commands/modules are blockers. Target tests in REQUIREMENTS and EV catalog can share helpers but must retain their independent assertions.

## Gate dependency graph

`G00 -> G01 -> G02 -> G03 -> G04 -> G05 -> G06 -> G07 -> G08 -> G09 -> G10`

Small independent UI components/source annotation fixtures can run in parallel only after API/schema contracts are frozen. G08 research preparation can occur earlier, but no activation before P0 gates. Avoid allocating parallel agents to mutually dependent graph/schema/policy code.

## G00 — reproducible repository and test harness

**Files:** create `pyproject.toml`, `uv.lock`, `.gitignore`, `.github/workflows/ci.yml`, `web/package.json`, `web/package-lock.json`, `tests/test_smoke.py`, `docs/status.json`.

1. Inventory target directory and actual tools/ports; preserve existing services. Record initial documentation state and protected instruction-file blockers.
2. Create only the application scaffold needed to run a failing smoke test. Lock dependencies; run resolver before claiming package compatibility.
3. Define lint/type/test commands and CI markers (`unit`, `contract`, `integration`, `simulation`, `live_model`). Live-model tests default off and require explicit budget/access.
4. Add a failing test that expected application entrypoint starts in model-disabled simulation-only mode.
5. Implement minimal entrypoint/config validation, pass smoke test, no business behavior claims.
6. Ensure `.research/vendor`, `.venv*`, runtime secrets, simulator recordings and raw non-public data cannot be accidentally committed.
7. Commit scaffold and logs; G00 exits only when local commands actually run.

## G01 — domain types, sources, graph readiness and isolation

**Files:** `src/witness_fleet/domain/*.py`, `graph/client.py`, `graph/migrations.py`, `queries/migrations/001.cypher`, `tests/unit/test_observations.py`, `tests/integration/test_tenant_acl.py`.

1. Write enum/DTO tests separating observation, prediction, hypothesis, receipt and verified fact.
2. Implement immutable IDs/time domains/provenance validation and reject malformed or future/stale input as specified.
3. Verify image tag/digest/data path; write compose for a **new** isolated graph service/volume. Do not replace pre-existing graphhacks-fdb.
4. Define exact graph-key ACL roles, including separate corpus/companion keys. Test wrong-key denial using direct DB clients.
5. Write operational readiness tests for pinned version, parameterized reads, indexes/constraint status and uniqueness.
6. Implement migrations and graph repository; do not serve traffic while required constraints are pending/failed.
7. Add error tests distinguishing empty/unavailable/invalid; retain read-only query enforcement.
8. Commit with R-004/R-023 and readiness evidence. No fleet claim yet.

## G02 — one physical world, truthful sensor boundary

**Files:** `services/simulator/{pyproject.toml,server.py,world.py,sensors.py,skills.py,journal.py}`, `services/simulator/assets/{facility.xml,robots.xml}`, `src/witness_fleet/simulation/{protocol,client}.py`.

1. Install tested MuJoCo wheel in simulator environment; import/load/step minimal original XML and record actual version/platform.
2. Add original scout body, then recovery/courier with namespaced bodies and different capabilities; assert one clock advances all.
3. Write boundary test with hidden truth sentinel; policy DTO cannot access oracle fields or evaluator endpoint.
4. Implement S0 pose-limited sensor features with unknown/visibility/noise/expiry. Label S0 simulated feature sensing, not vision.
5. Add bounded inspect/travel/hold skills, controller watchdog and explicit command receipt states.
6. Implement simulator journal acceptance/replay contract and UNKNOWN handling; no contact success yet.
7. Test stop/hold without graph/model and headless stepping. Passive macOS viewer requires documented launcher; rendering failure cannot justify oracle leakage.
8. Commit R-002/R-003/R-035 proofs.

## G03 — first complete graph-driven incident slice

**Files:** `graph/{queries,transitions,evidence}.py`, `planning/frontier.py`, `runtime/coordinator.py`, `tests/integration/test_graph_causality.py`, `tests/unit/test_hypotheses.py`.

1. Write test: missing clearance fact selects inspection instead of travel; adding supported current fact changes selected proposal.
2. Implement observation append → typed planning fact → task dependency query.
3. Write DAG-cycle rejection and transitive invalidation tests; implement bounded graph traversal with truncation errors.
4. Persist hypotheses and refutation history; predictions cannot satisfy task prerequisites.
5. Run one robot observe→graph→proposal→inspect→new evidence→trace. No hardcoded expected answer card.
6. Kill graph access and show safe hold; no full-world in-memory fallback.
7. Commit R-001/R-005/R-009 with real query and trace evidence.

## G04 — recover and verify, with first visible UI

**Files:** `policy/authorizer.py`, `planning/routes.py`, `services/simulator/skills.py`, `api/{app,reads,stream}.py`, `web/src/components/{Scene,Timeline,GateStatus}.tsx`.

1. Write failing test: controller completion leaves courier held until fresh postcondition evidence.
2. Implement bounded original recovery action; distinguish failed removal, partial movement and success.
3. Test gap fits scout/not courier and reintroduced obstacle after clearance; implement footprint/load-aware conservative check.
4. Test bounded occluded inspection returning unresolved; no infinite retries.
5. Add API event projection and simple live dashboard from actual backend events. Show ack versus observed effect distinctly.
6. Export first full episode trace with query/witness/command/evidence IDs.
7. Commit R-006/R-007/R-008/R-031/R-033. This is the first coherent demo slice, not all-track completion.

## G05 — three-robot assignment, resources and fenced claims

**Files:** `planning/assignment.py`, `runtime/{leases,dispatcher}.py`, `queries/write/claim.cypher`, `tests/integration/test_claim_race.py`, `tests/contract/test_command_protocol.py`.

1. Write a ready-frontier assignment test with ineligible robot/task pairs and an all-wait case.
2. Implement deterministic weighted matching over explicit eligible pairs; route adjacency remains graph-derived.
3. Add corridor/robot/workspace resource reservations, reject simultaneous incompatible occupancy.
4. Write barrier-synchronized independent-client CAS race, then implement tested conditional mutation. Single coordinator alone is insufficient proof.
5. Test increasing fences across reassignment, stale holder resumption and duplicate command payload mismatch.
6. Persist command intent before send; simulate transport timeout and retain UNKNOWN.
7. Commit R-010/R-011/R-012 with actual winner/conflict/fence results and denominators.

## G06 — company authority and source-backed resumption

**Files:** `ingestion/{source_store,normalization,staging,promotion}.py`, `policy/{scope,precedence,approvals}.py`, `queries/read/policy_witness.cypher`, `fixtures/sources/*`, `web/src/components/{Witness,SourceReader,ApprovalPanel}.tsx`.

1. Write exact Unicode/newline/revision/span tests; implement retained original bytes + normalized immutable text + locator validation.
2. Create original synthetic manual, owner roster, maintenance ticket, scoped restriction, unsigned chat and approved release fixtures; no real personal/company data.
3. Write tests enumerating restrictions even when support/owner edges are missing. Implement complete witness + integrity query, not complete-path-only MATCH that hides orphan rules.
4. Implement deterministic base permission/restriction/release evaluation; newer chat does not override authority.
5. Test scoped scout/recovery permission plus courier prohibition; blanket ban stops all; overlapping restriction remains after one release.
6. Implement local synthetic owner approval handler with server-derived principal, expected epoch and idempotent event ID; no request-body `approved=true` authority.
7. Implement RUNTIME explicit policy tick conversion, immutable AuthorizationReceipt, atomically sequenced graph outbox, idempotent ingress acknowledgments and restart barrier/tombstones. Test policy change between claim and dispatch/during motion, sequence gap/late revocation and crash before/after each delivery boundary.
8. Run source ingestion→canonical witness→blocked courier→approved release→fresh verification→resume, changing actual graph/source state.
9. Commit R-016 through R-022 with UI/backend evidence. This proves the central all-track authority story.

## G07 — persistent memory, handoff and crash reconciliation

**Files:** `graph/episodes.py`, `planning/procedures.py`, `runtime/reconciliation.py`, `tests/integration/{test_restart_reconcile,test_durability,test_episode_reuse}.py`.

1. Write tests that only outcome-verified episodes seed candidate procedures; reject incompatible robot/map/hazard/policy.
2. Implement graph-based related episode retrieval and typed plan re-grounding; preserve failed attempts and proposed lessons separately.
3. Kill coordinator after send/before recorded ack. New epoch queries exact command; controller-done still needs observation.
4. Test durable lease UTC/epoch versus local monotonic deadline; process restart must not reuse stale monotonic values.
5. Test app restart, DB restart, authorized disposable container recreation and backup restore independently. Preserve graph+sources+sim receipts/checkpoint manifest.
6. Test old graph restore against newer simulator fence/epoch; hold until reconciled.
7. Demonstrate scout handoff to capable replacement and a memory-informed different next action.
8. Commit R-013/R-014/R-015 with separate recovery artifacts, not one restart screenshot.

## G08 — isolated SDK lane and System One evaluation

**Files:** `services/corpus/{pyproject.toml,worker.py,sdk_adapter.py}`, `decisions/{contracts,projection,calibration,policy,cache}.py`, provider modules, `eval/{split,run,metrics,report}.py`.

1. Resolve SDK environment at verified package subdirectory; inspect actual typed TableMapping example and provider contracts.
2. Test corpus-only ACL and deletion/merge/update cannot touch ops. Implement deterministic rows plus source-locator validated candidates.
3. Test source cutover/retry with retained canonical revision history; report SDK blocked if provider/dependency path fails.
4. Write DecisionRequest/Result schema tests for every status and malformed distribution; implement provider-neutral adapter and disabled/shadow modes.
5. Implement atomic F-001 relation prompts using fixed claim/span IDs; exact policy enumeration bypasses semantic top-k.
6. Create labeled synthetic evidence set split by incident/template/revision; record annotation rubric and reviewer adjudication. No test-label leakage.
7. Unit-test Brier/ECE/risk/coverage/nDCG and zero-denominator handling with synthetic arithmetic. Test original code mutation fails assertions.
8. With user-authorized access/budget only, run minimal live smoke then shadow comparison: deterministic, structured generator, System One; optional AnyJev actual-logit baseline separately.
9. Freeze per-family thresholds and evaluate untouched test plus plausible-context/option-order perturbations. Include fallback failures/costs and repeat variance.
10. Enable advisory only if predeclared benefit and all hard invariants hold. Otherwise keep disabled and publish truthful negative/inconclusive result.
11. Commit R-024–R-030/R-037 evidence. Adapter tests alone do not satisfy a measured-model claim.

## G09 — hardening, evaluation and complete operator experience

**Files:** all EVALUATION EV test paths, `web/tests/*.spec.ts`, `eval/report.py`, `docs/status.json`.

1. Map each requirement to exact tests/artifacts; include eval/contract cases even when unit tests overlap.
2. Run the outage, tenant, injection, source-integrity, missing-witness, policy-race and simulator-oracle matrices.
3. Run same-information matched scenarios and ablations for active inspection, freshness, post-verification, memory and optional model.
4. Run keyboard/focus/reduced-motion/non-color UI checks; verify no fake model badges or false verified statuses.
5. Produce machine-readable traces/metrics with raw attempts and outcomes; separate paper/vendor numbers from local measurements.
6. Independent review: security/authority/clock/unknown-outcome contracts, then code quality and dependency/license scope.
7. Fix findings with regression tests; no weakened assertions. Commit R-023/R-031–R-037 final evidence.

## G10 — clean setup, participant understanding and submission package

**Files:** `README.md`, `THIRD_PARTY.md`, `AI_DISCLOSURE.md`, demo recording, graph/query exports, clean setup report.

1. Extract/clone a clean checkout in a new directory and follow only documented setup, using isolated test services.
2. Verify all P0 evidence present; mark P1/P2 honestly. No unresolved critical invariants or hidden manual steps.
3. Record the DEMO sequence with actual graph/policy/source changes, restart and real metrics, clearly labeled simulation/model mode.
4. Recheck official rules and exact entered tracks. Participant explains architecture, queries, math adaptations and original contribution in their own words.
5. Audit licenses/assets, secrets and all remote publication contents. Public repository/PR/upload only after user authorization; verify exact remote target afterward.
6. Deliver source/setup, Cypher/model, video, evidence and disclosures. A README-only artifact is not the hackathon submission.

## Session handoff template

```text
Gate / requirements:
Actual files changed:
Tests executed (command -> real result -> artifact):
Current branch/commit:
Unverified or blocked contracts:
Decisions changed and ADR:
Next dependency-ready test:
```

## Stop rules

Stop the affected path if hidden truth leaks, policies disappear via ranking/incomplete witness query, a stale fence executes, UNKNOWN becomes success, SDK touches ops, or a restored graph silently authorizes a newer world. Keep useful completed slices but do not call the project complete. Scope changes require explicit visible decisions rather than quiet feature removal.
