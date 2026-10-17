# Witness Fleet — Product requirements document

**Status:** proposed implementation contract, 15 October 2026. No fleet, inference benchmark or integration has been built by this documentation task. Working title only.

## 1. Problem and product promise

A robot recovering an obstruction cannot infer that every other robot may resume. A scout can fit where a loaded courier cannot; a successful controller return may not mean the obstruction moved; a maintenance order can still prohibit entry after the floor is clear. Restarting a coordinator must not erase any of these distinctions.

**Product promise:** a small heterogeneous robot team investigates, recovers and resumes work only when its shared graph supports both physical feasibility and current operational permission, and shows exactly why it acted, paused or asked for help.

The user sees a simulated facility, not a chatbot dressed as robotics. The graph changes the ready-task frontier, responder assignment, evidence acquisition and permission to resume. A System One model interprets bounded ambiguous language; it does not authorize motion.

## 2. Intended users and jobs

- **Fleet operator:** inspect a blockage, see impacted orders, know what can continue and what needs approval.
- **Safety/maintenance owner:** inspect the exact restriction and scope; issue a synthetic authorized release only for the rule they own.
- **Engineer/reviewer:** reproduce incidents, fault injection and recovery; trace every command to evidence, versions and a current owner.
- **Hackathon judge:** see one coherent product prove all entered tracks without credentials, private company data or robot hardware.

These are simulated roles. No enterprise deployment, certified robot safety or actual customer validation is claimed.

## 3. One canonical end-to-end story

1. A courier task requires Corridor C; a scout reports an ambiguous obstruction from a limited viewpoint.
2. FalkorDB identifies dependent tasks, missing predicates and robots able to inspect or recover. Unaffected tasks remain eligible.
3. A model may classify a report or rank supporting passages; a deterministic planner selects only an eligible inspection/recovery action.
4. The recovery robot attempts a bounded manipulation. Expected effects are recorded separately from observations.
5. A fresh, scoped observation verifies clearance for the courier's footprint and load. The courier **still waits**: a current maintenance decision prohibits loaded couriers while explicitly permitting the scoped scout/recovery operation.
6. The UI traverses and displays the connected source/revision/span/decision/owner/restriction evidence in canonical FalkorDB.
7. An authorized synthetic owner approves a release. Old policy snapshots become stale. Fresh physical and policy checks run again before dispatch.
8. The courier resumes only after those checks. A second incident retrieves a verified episode but rejects its recipe if capability, map, hazard or policy differs.
9. Kill/restart the coordinator after a command is sent and before its result is recorded. It reconciles the existing command rather than repeating an uncertain recovery.
10. Concurrent claim and second-tenant tests show one winner and no cross-tenant access. These are tests, not inferred from three animated robots.

The blanket-ban variant must also exist: if all entry is forbidden, the recovery robot cannot enter either.

## 4. Track fit and organizer constraints

The official rules permit any/all of the three tracks, require naming each entered track, and require FalkorDB to perform a central product function.[39]

| Track | Product behavior | Judge-visible proof |
|---|---|---|
| 01 — Agents That Act on Connected Data | Dependency/capability/route/permission queries change assignments and actions | Query inputs/results, graph version and rejected alternatives alongside movement |
| 02 — Agent Memory and Coordination | Persistent evidence, verified episodes, claims and unknown-action reconciliation | Fresh-process recovery changes the next action; concurrent claim race and separate DB durability evidence |
| 03 — Company Brain | Current source-backed policy and ownership determine allowed actions | A canonical multi-hop witness, a genuine source/release update and changed courier behavior |

The retrieved event window is October 15, 12:01 AM IST through October 18, 11:59 PM IST. Rules require public code, setup/model/queries, a working demo, a deployment or complete local setup, permitted data, AI-assistant disclosure and meaningful participant understanding. Recheck before submission.[39]

## 5. Scope and priorities

### P0 — complete, demonstrable product

- Original MuJoCo scene with scout, recovery and loaded courier; one physics owner; bounded controllers; honest sensor/evaluator separation.
- Canonical FalkorDB relationships, typed evidence, hypotheses, current-policy decisions, task DAG, capability eligibility and atomic claims.
- Synthetic company corpus ingested from retained sources through a real loading/validation path, not prewritten answer cards.
- Deterministic physical + policy authorizer on **every** action; local stop/hold independent of graph/cloud availability.
- Precondition/action/postcondition verification and meaningful `unknown`/`unresolved` outcomes.
- Verified episode retrieval and applicability checks; process restart, DB recovery, task handoff and command reconciliation.
- Operator dashboard: simulation, graph witness, event timeline, task/robot status and explicit approval interaction.
- Reproducible deterministic baseline, structured-generator comparison contract, System One shadow evaluation, failure tests and raw trace export.
- A narrow GraphRAG-SDK integration attempted and contract-tested in a separate corpus graph. If unavailable, typed direct ingestion is the explicitly labeled baseline; report the SDK acceptance criterion as unmet, not silently complete.

### P1 — measured System One enhancement

Evidence reranking is the first model family; permissible investigation selection is second. The adapter and offline contract tests are required deliverables. Enabling a hosted model in the demonstration requires authorized access, completed shadow tests and measured advantage. The model-free product is not allowed to display fabricated model scores.

### P2 — retained roadmap, not first-build requirements

Alias alignment suggestions; episode relevance ranking; calibrated clarification sets; larger scenes; renderer/VLM verification; Graphiti, Docling/PDF ingestion, LangGraph checkpoints, OPA, Hypothesis branch graphs, advanced path indexes, learned controllers and supervised hardware. Each requires its own evidence/ablation and an ADR. See `RESEARCH.md` and `REPOSITORIES.md`.

### Explicit non-goals

No fully decentralized swarm claim, arbitrary generated robot code, learned collision controller, new VLA/RL training, sim-to-real guarantee, live employer connectors, unreviewed policy extraction, automatic source authority from recency, or universal statistical safety claim. No broad claim that using graphs for fleet planning is novel.

## 6. Product acceptance

Use the requirement IDs in `REQUIREMENTS.md`; this PRD does not define duplicate IDs. Hard invariants are release blockers even when mission completion improves. P0 is complete only when all P0 requirements have a test artifact. P1 is complete only when the model comparison ran on held-out data with honest costs, uncertainty and failure rates. Documentation status must distinguish `planned`, `implemented`, `tested`, `measured` and `demo-recorded`.

Targets, not results:
- Every emitted action records its current authorization witness, robot/task version and command identity.
- Zero unauthorized executed actions in the declared finite regression suite; report attempted unsafe intents separately.
- All ambiguous actions after restart reconcile or remain on hold; no blind replay.
- All current applicable restrictions are examined, even when a reranker assigns them low relevance.
- One current owner in every completed synchronized claim-race trial, with stale-fence rejection.
- Every approved policy has exact source text/revision and explicit scope/owner; every displayed quotation matches its retained revision.
- No success-rate, latency or cost claim without machine-readable run evidence and denominators.

## 7. Demo and interaction principles

The hero moment is **“Clear floor. Courier still blocked. Here is why.”** Use a plain-English status and the exact graph witness, not a generic confidence badge. Distinguish `physically verified`, `policy permitted`, `claimed`, `controller acknowledged` and `outcome verified` as separate statuses. Human release is an explicit audited operation, not a model-generated Boolean.

## 8. Risks and product decisions

- Simulator overreach: use simple original robots/assets and bounded skills; do not import an entire warehouse stack.
- SDK dependency/provider mismatch: isolate its environment, use documented interfaces and retain a disclosed direct-ingestion baseline.
- Model benefit uncertain: ship shadow evidence and keep it advisory/off when no benefit is established.
- Event time: finish the entire narrow incident before extra frameworks. Record deferred features rather than dropping them from the plan.
- Licensing: external repo visibility is not reuse permission. Keep SSPL server, permissive clients, proprietary models and model/data licenses distinct.

## 9. Handoff and completion

`architecture.md` specifies component ownership, `PLAN.md` orders work, `EVALUATION.md` defines proof and `DEMO.md` specifies the recording. A coding agent must not mark this document satisfied because it created empty modules. User approval is needed before remote publication, paid services, destructive changes or hardware control.

<!-- GENERATED CITATION REFERENCES -->

## Sources

[39] https://www.wemakedevs.org/hackathons/falkordb/rules — Rules | Graph Hacks: Context for AI Agents | WeMakeDevs
