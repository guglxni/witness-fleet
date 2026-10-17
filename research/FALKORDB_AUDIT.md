# Earlier FalkorDB / SDK / System One audit

> Historical read-only research appendix, 15 October 2026. The current implementation prescription is `../architecture.md`, `../INTEGRATIONS.md`, `../GRAPH_SCHEMA.md` and `../RUNTIME.md`. These take precedence over earlier sketches. No integration/inference/runtime test was performed in the research audit. Numeric source IDs share the package ledger `../evidence/sources.json`; local research paths mentioned below identify the original investigation and are not required application paths. No earlier Graphiti-first prescription is current.

# FalkorDB, GraphRAG-SDK and System One: project enhancement audit

**Research date: 15 October 2026. Status: research and design, not implementation.**

## Decision in brief

**Yes: use a fast typed-decision model, but put FalkorDB before it, not behind it.** The graph resolves relationships, current revisions, dependencies and evidence. A bounded classifier can then rank retrieved passages or select an investigation branch. Deterministic code still decides whether an action is authorized and executable.

**Revise the first-build recommendation:** canonical FalkorDB graph + direct verified-episode/task persistence + **one narrow GraphRAG-SDK company-document adapter** + one optional System One backend. Defer Graphiti, a second ingestion framework, learned memory-write gates, experimental vision and advanced routing indexes. This replaces the earlier Graphiti-first preference; it does not mean any component is now integrated.

The strongest demonstration remains: the scout confirms physical clearance, yet the loaded courier stays stopped because the current company restriction still applies. The graph identifies the responsible decision, owner and revision. A signed/approved synthetic release changes the graph, after which both physical and policy gates are rechecked. The classifier may help find or prioritize evidence, but cannot grant the release.

## 1. What was actually examined

The main audit captured **34 individual FalkorDB documentation pages**, excluding navigation/LLM indexes, covering Cypher compatibility, constraints, indexes, path algorithms, read-only queries, execution plans, concurrency, persistence, replication/cluster boundaries, access control, observability, UDFs, and GraphRAG architecture/schema/update/reliability. A separate SDK review inspected additional SDK documentation and source. This is a deep audit of project-relevant sections, **not a claim to have read every Cloud/Enterprise page**.

Release metadata and source were inspected at **FalkorDB v6.0.2, `7b7b4d1ed23fe78e69fa5da0c9e4f2ea2e73f3e9`**. GraphRAG-SDK source was inspected at **`35e67a0b27fdcc7f2c28508b09e86169851a8187`**, whose package manifest says **1.4.0**. A repository manifest is not proof that an identically named package from PyPI has been installed or tested.[56][61]

Read-only local inspection found `graphhacks-fdb` running module version `60002`; `GRAPH.LIST` returned an empty list. AOF was disabled, RDB snapshot rules existed, and Docker reported no mounted volumes. This is **not a verified durable fleet-memory installation**. Restarting a container and deleting/recreating it are different durability cases. Raw non-secret inspection output is retained in `runtime-readonly.txt`.

Read-only Azure inventory found deployment `ms-decision-1`, model `Microsoft-Decision-1`, version `1`, `GlobalStandard`, capacity `100`, provisioning state `Succeeded`. This establishes an existing configured deployment, not current inference latency, accuracy, quota headroom or service health. No inference call or benchmark was run for this task; metadata is in `azure-readonly.json`.

## 2. FalkorDB findings that materially change the design

| Area | Verified documentation/source finding | Project enhancement and limit |
|---|---|---|
| Query language | FalkorDB uses Redis-protocol `GRAPH.QUERY` / `GRAPH.RO_QUERY`, with an OpenCypher subset and extensions; Neo4j syntax/procedures are not assumed.[4][5][15][16] | Use the official Python client, parameterized, allowlisted queries. Keep graph mutation tools separate from agent retrieval. |
| Evidence graph | Range, full-text and vector indexes serve different retrieval functions.[19][20][21] | Exact IDs/current-state lookup first; lexical search for policy codes/names; vector search for paraphrases; graph expansion for ownership, revisions and applicability. Similarity alone is not a decision proof. |
| Vector score semantics | The v6.0.2 vector scan binds **distance** to the yielded score variable and preserves ascending distance order.[59] | Do not interpret a variable named `score` as probability or sort it as descending relevance. Test self/near/far vectors and normalize only in a named adapter. |
| Constraints | `UNIQUE` and `MANDATORY` constraints are documented; UNIQUE relies on a supporting range index, and constraint creation has pending/operational/failed states.[10] | Provision schema before admitting traffic, wait for operational status, and verify uniqueness of tenant-scoped stable IDs. Do not assume a request to create a constraint makes it active immediately. |
| Concurrent writes | Docs describe per-graph parallel readers, serialized writes and single-query atomicity. Source includes read/write escalation and an explicit transient `WriteSlotBusy` condition.[6][57] | A claim protocol needs version/fencing checks, idempotency and bounded retry with a fresh read. “Writers serialize” does not make application read-then-write sequences race-free. Test the actual pinned build. |
| Multi-query transactions | FalkorDB docs suggest `MULTI/EXEC` for all-or-nothing groups, but Redis explicitly does **not** roll back already executed commands on an execution-time error.[6][31] | Prefer one conditional graph mutation for a claim/state transition. For multi-stage work, use a recoverable application state machine; never promise SQL-style rollback for `MULTI/EXEC`. |
| Read isolation | The documentation uses snapshot terminology; pinned code also contains reader/writer locks, escalation and MVCC machinery.[6][57][60] | Do not infer that all readers are nonblocking, every write is FIFO, or a multi-request workflow sees one snapshot. Measure simultaneous reader/writer behavior; revalidate graph/policy versions at dispatch. |
| Tenancy/security | ACLs scope commands and graph keys, rather than individual nodes/relationships. Persistent ACL configuration is a separate deployment task.[9][55] | Use tenant-scoped graph keys and separate credentials/roles for corpus ingestion, retrieval and control. Node `tenant_id` filters are defense in depth, not a database authorization boundary. |
| Durability | RDB and AOF are supported; durable Docker operation needs explicit storage configuration. `appendfsync everysec` has a documented loss window; replication is not a backup.[11][12][13] | Persist the data directory, select an explicit loss budget, back up, and test process restart, container recreation and restore. Keep command/result reconciliation separate from graph persistence. |
| Scale | Cluster distribution is graph-key-oriented; it is not automatic arbitrary traversal across graph keys.[14] | One canonical fleet graph per tenant for the decisive traversal. Do not split one policy proof across databases and call an application-side join a single Cypher traversal. |
| Observability | `EXPLAIN`, `PROFILE` and OpenTelemetry support inspecting query behavior; `PROFILE` executes the query.[25][26][27] | Record query template, graph version, latency and plan. Do not profile unapproved mutating queries merely to inspect them. |
| Routing algorithms | Docs describe `algo.SPpaths`, A* and CCH, but the inspected v6.0.2 procedure registry does not expose A*/CCH.[17][18][22][58] | Use only contract-tested features. For the small demo, retrieve eligible adjacency/capabilities from FalkorDB and run a deterministic shortest-path solver, or test `algo.SPpaths` explicitly. No A*/CCH requirement. |
| Custom logic | UDFs exist in dedicated docs and v6.0.2 release notes despite conflicting statements in compatibility documentation.[4][29][56] | Avoid UDFs on the first slice; use tested parameterized queries plus application code. More extension machinery does not improve the demo. |

### Canonical model and decision proof — proposed

Keep stable business identifiers rather than relying on recycled internal node IDs. Separate these kinds explicitly:

- `Observation`: timestamped, source-linked measurement; quality and expiry.
- `Hypothesis`: proposed explanation, never a verified fact.
- `Task` / `Claim` / `Command`: state, dependency IDs, version, holder, lease and fencing token.
- `Episode`: incident, attempted action, observed outcome and verified resolution.
- `Source` → `Revision` → `EvidenceSpan`: immutable content identity, exact quote/offset convention, owner, approval and validity interval.
- `Decision` → `Restriction` / `Release`: operational authority and scope.
- `Assessment`: model/version/question version, input-state identity, probabilities and outcome status. This is an opinion record, not authority.

The required Track 03 proof is a **connected canonical subgraph**, not one linear chain. Proposed directed relationships are:

```text
(Courier)-[:ASSIGNED_TO]->(Task)-[:USES]->(Corridor)
(Decision)-[:IMPOSES]->(Restriction)-[:APPLIES_TO]->(Corridor)
(Decision)-[:OWNED_BY]->(Owner)
(Decision)-[:SUPPORTED_BY]->(EvidenceSpan)-[:IN_REVISION]->(Revision)
(Revision)-[:REVISION_OF]->(Source)
```

Queries can traverse these relationships in either direction, but their stored directions and types must stay consistent. “Source/revision/owner/decision/restriction proof” below means this branched evidence subgraph, not a separate edge chain through every entity.

A release must be linked to the applicable restriction, approved under the local policy, temporally current and in scope for the courier/load. A source filename, high similarity or model confidence cannot substitute for those edges.

### Task claims and physical execution — proposed acceptance rules

1. The dispatcher uses a tested compare-and-set transition containing expected task and policy versions; one winner receives the fencing token.
2. A loser or transient write-slot failure reads current state before retrying; a network timeout has an **unknown commit outcome**, not permission to issue a duplicate command.
3. Commands have idempotency keys; the simulator rejects stale fencing tokens and reconciles started/completed/observed states after interruption.
4. A policy change invalidates stale plans. Authorization is checked again immediately before command dispatch.
5. Competing workers, simultaneous reads/writes and a second tenant are actual test scenarios. “Three robots exist” is not a concurrency measurement.

## 3. GraphRAG-SDK: useful, but not an authority engine

### What is more useful than the earlier brief captured

The SDK supplies a modular pipeline for loaders, chunking, extraction, entity resolution, embedding, storage, retrieval and generation. Its graph schema links documents/chunks/entities and relationship facts; provenance includes `source_chunk_ids` and span-related fields, with the precise output depending on the extraction path.[32][33][69]

**Correction to the earlier audit:** saying the SDK simply “lacks exact spans” was too broad. The pinned source has span propagation paths.[79]

Character-window chunking supplies `start_char`/`end_char`; the default sentence-token chunker does not.[80][81]

Extractor spans are optional and chunk-local, with some inferred by string matching; they need validation against the retained source.[79]

These locators are not a complete immutable revision/approval/authority ledger.

**Highest-value SDK reuse for the synthetic fixture:** typed `TableMapping` ingestion for the owner roster, tickets and policy metadata. Its structured pipeline maps declared keys/columns/links without calling a model.[78] This is safer than re-extracting known IDs from prose. Use immutable source revision IDs in the application model, and use SDK `update()`/re-sync rather than assuming an omitted row disappears on an upsert.[62]

This does not make the whole facade model-free: it requires generation/embedding provider contracts, and `finalize()` can invoke cross-document resolution/judging.[62][82] Disable unwanted fuzzy/model merging, inspect even exact-name dedup scope, and never allow canonical policy/owner identities to be silently merged. Source-signature-prefixed properties are provenance namespaces, **not cryptographic signatures**.

The SDK also has document `update()` / deletion and a pending-document cutover/recovery design. This is more substantial than a one-shot chunk loader, but replacement of a corpus document is not preservation of every historical approved revision.[34][62]

Retrieval combines relationship-vector search, entity lookup, graph expansion and source passages. `retrieve()` can return context **without generation**, making it a good seam for a typed reranker. `MultiPathRetrieval` returns section-level items; unlike `LocalRetrieval`, it does not consistently expose per-passage `chunk_id` metadata. The source prefix alone is insufficient for exact citation verification.[35]

### Integration pitfalls from actual source

- **No drop-in Jev “LLM” provider:** extracting arbitrary entities or writing explanations requires generation, while System One returns bounded decisions. Introduce a separate decision/reranking interface, not a fake `generate()` implementation.[32][41][48]
- **Routing is not already learned:** the inspected `SemanticRouter` is first-match rule-based, with a default strategy; its comments defer a trained classifier/LLM router to later work.[64]
- **No automatic row-level ACL:** `retrieve()` / `completion()` have no general metadata `filter=` parameter. Scope graphs and use explicit Cypher filtering; authorization must happen before external model egress.[35]
- **Not enforced grounding:** the completion prompt asks the generator to use context and abstain, but that is not a proof or a programmatic abstention gate. A custom prompt template can disable the default delimiting/escaping safeguards.[35]
- **Raw query is write-capable:** `GraphRAG.query()` explicitly has no read-only enforcement; its connection calls the underlying graph's `.query()`. Do not expose it as an unrestricted agent tool.[62][63]
- **Destructive scope:** `delete_all()` removes the managed graph and paired ontology graph. Letting a corpus SDK own the control graph would create an unnecessary deletion/migration risk.[62]
- **Dependency mismatch to resolve:** the inspected SDK OpenAI extra pins `openai>=1.0,<3.0`; OpenAI Decisions examples require Python SDK `3.26.0+`. Do not put both requirements into one environment and assume the resolver can satisfy them. A small HTTP decision adapter or isolated worker avoids that conflict.[41][61]
- **Azure generation mode still matters:** a current Foundry deployment may require Responses rather than Chat Completions. Verify the SDK provider's actual request path; do not assume OpenAI-compatible means every API is interchangeable.

### Selected integration — proposed, not built

Use **one SDK-managed corpus graph per tenant**, separate from the canonical control graph. The SDK can discover candidate entities/passages in synthetic SOPs, incident reports and revision documents. A narrow adapter validates their IDs/quotes and materializes the necessary `Source`, immutable `Revision`, `EvidenceSpan`, `Owner`, `Decision` and restriction relationships in the canonical graph.

The decisive query connecting source, revision, owner, decision and current restriction runs **entirely in the canonical graph**, using the branched relationship model above. The SDK corpus is a discovery aid, not a second source of authority. There is no claimed cross-graph transaction or magical cross-graph Cypher join.

For a tiny fixture corpus, direct text/JSON ingestion remains the fallback; the demonstration must work even if SDK extraction is inaccurate or unavailable. Graphiti is deferred: verified episodes and task state can initially be persisted directly in the canonical model. Add temporal-memory framework retrieval only if an ablation shows it improves an actual decision.

## 4. Jev versus OpenAI Decisions versus Microsoft Decision

The user's overall description is directionally right, but these are **distinct provider APIs**, not one universal “Open Decisions API” standard. Output shape, modality, model lifecycle and failure behavior need adapters.[41][42][48]

| | TypeSafe Jev | OpenAI Decisions | Microsoft-Decision-1 |
|---|---|---|---|
| Current documented model | `jev-1.13.0` stable; `jev-1.14.0` newly available preview. `jev-latest` still targets 1.13 and `jev-preview` targets 1.14.[36] | `gpt-6-luna`; public beta at audit time.[41] | `Microsoft-Decision-1` v1 through a Foundry deployment alias.[42] |
| API | `/v1/systemone`; `state` + named `questions`.[48] | `/v1/decisions`; `input` + a questions array.[41] | `/providers/microsoft/v1/systemone` on the resource host.[42] |
| Core output types | `noul`, `choice`, `score`.[48] | `predicate`, `choice`, `score`, with typed refusal handling.[41] | `noul`, `choice`, `score`.[42] |
| Inputs | Text is the normal model-table contract; separate docs expose experimental images for 1.13/1.14 and preview Box for 1.14.[36][46][47] | Text and images.[41] | Text/structured state; do not assume a vision path.[42] |
| Advertised input rate | $0.042 / million tokens; free output.[36] | $0.10 / million input tokens, no output/cache charges; regional and long-context multipliers apply.[41] | Microsoft announcement quotes $0.042 / million tokens. Confirm the applicable Azure region/SKU billing meter; this audit is not an invoice estimate.[52] |
| Speed evidence | TypeSafe advertises 70–500 ms and large speedups for suitable tasks. Not an independently measured fleet p95 or SLA.[44] | OpenAI says about 10× faster than Responses. That is not a Jev comparison.[41] | Microsoft advertises about 10× versus lightweight reasoning models and workload-dependent latency. No project measurement.[52] |
| Practical role here | Hosted comparison candidate; pin stable ID first. | Interesting future image-triage candidate if account beta access exists. | **First integration candidate**, because the user's existing deployment was found by live read-only inventory. |

**The original “three question types” description now needs a preview footnote:** Jev Box is experimental, has no “object absent” output, and is explicitly not production-ready. It must not become the obstacle detector or clearance proof.[47]

**Do not treat confidence as P(correct).** Jev's Choice confidence is derived from the probability peak and label count; Score confidence describes distribution concentration. TypeSafe explicitly says calibration concerns groups of predictions, not certainty about one answer.[45]

Jev's own 1.13 failure documentation flags irrelevant/long context, numeric/date/count reasoning, multi-hop reasoning, wording/choice-order sensitivity and adversarial state. Those limits argue strongly for **graph-computed facts + small state + atomic questions**, not giving Jev the entire graph and asking it to reason out permission.[37]

The existence of a Foundry `gpt-6-luna` deployment does not establish availability of OpenAI's Decisions endpoint there. Microsoft documents its own System One path; use the backend's actual endpoint rather than replacing a model string inside an incompatible request.[41][42]

## 5. The strongest System One enhancements, ranked

These are proposed uses, not measured gains.

### A. Evidence reranking — best initial fit

The graph retrieves a bounded candidate set with immutable document/revision/span IDs. A typed model judges whether each passage supports or contradicts a **specific atomic statement**. It returns only probabilities over predefined labels such as `supports`, `contradicts`, `irrelevant`, `insufficient`.

This is close to TypeSafe's own re-ranking and entity-alignment examples, while preserving FalkorDB's job of finding connected candidates.[49][50]

**Boundary:** a model can rank which candidate to inspect first; it cannot delete conflicting current restrictions or decide an unsigned release is authorized. Deterministic graph checks inspect every applicable authoritative restriction irrespective of semantic ranking.

### B. Investigation branch selection — visible agent contribution

Given a graph-resolved state with current observations and permissible investigation actions, select `inspect_corridor`, `check_source_revision`, `request_operator_review`, or `abstain`. The graph supplies eligibility; the model interprets ambiguous natural-language incident reports. Never ask it to re-derive battery arithmetic, temporal validity, geometry or task readiness.

Log the full probabilities and the evidence snapshot used. A low-confidence result, refusal, missing answer, timeout, malformed distribution or graph-version mismatch routes to a conservative review path. Choice labels must not include a direct `override_safety` or unconditional `resume_courier` action.

### C. Entity-alignment suggestions — useful, but ingestion-only

Offer candidate aliases such as “loading bay A” versus a canonical corridor ID, with a `none_of_these` option. Evaluate false merges explicitly. A mistaken merge can attach a real policy to the wrong location; suggestions require validation and must not silently alter the authority graph.

### D. Memory retrieval priority — optional later

Rank verified prior episodes by relevance to this incident. Do not let an AI write gate discard mandatory observations, claims, command acknowledgements, policy changes or safety audit events. “Interesting enough to summarize” is separate from “required to retain.”

### What not to add

No cloud model in a high-rate control loop; no automatic physical clearance from Jev Box; no confidence-only authorization; no learned router for decisions already known from exact event types; no Graphiti + SDK + additional memory framework on the same first-build path.

## 6. Decision interface and audit trail — proposed program design

Define a provider-neutral interface around application semantics, **not raw vendor JSON**:

```text
DecisionRequest
  family_id, question_schema_version
  tenant-scoped evidence IDs, graph_snapshot_version
  sanitized_state, explicit allowed labels/rubric
  deadline

DecisionResult
  status: ok | abstain | refusal | unavailable | invalid
  provider, requested_model, resolved_model
  answer distributions (preserved, not reduced to one label)
  usage, elapsed time, retry count
  input identity, calibration-policy version
```

Adapters map `noul` ↔ `predicate`, named questions ↔ arrays and ordered criteria ↔ levels. Retain label order explicitly. Validate finite numbers, range, expected labels, distribution totals and response-model identity; do not silently repair malformed source data or normalize missing answers into certainty.

Independent questions over the **same evidence snapshot** can share one request. Questions that depend on an earlier answer require a later request or explicitly independent alternatives; batching does not let one answer reason from another hidden output.[36][41]

Keep cloud inputs limited to public/synthetic event data for this submission. The organizer permits public, synthetic or owned data but prohibits loading private, login-protected or otherwise restricted information into the graph; “Company Brain” does not authorize copying a real employer's confidential corpus.[39]

## 7. FOSS resources worth using, and their limits

| Resource | Verified scope | Recommendation |
|---|---|---|
| GraphRAG-SDK at `35e67a0…` | Apache-2.0 package metadata; actual ingestion/retrieval/source inspection.[61] | Selected narrow corpus adapter; not policy engine. |
| TypeSafe Python SDK at `f36e685…` | MIT code; typed client/async interface. Hosted Jev weights remain proprietary.[74] | Useful optional hosted client; not evidence Jev is FOSS. |
| `system-one-adapter-python` at `e1d4cc9…` | MIT; puts ordinary generative APIs behind System One-style calls.[75] | Fair structured-generation baseline. Generated/normalized probability text is not native calibrated inference. |
| Laya upstream at `432312b…`, model at `7b928d8…` | Apache-2.0 code/model-card declarations inspected; local typed-decision alternative.[76][77] | Best compact local comparison lead. Check exact checkpoint/serving-wrapper terms and measure Mac performance before relying on it. |
| Strands Decider at `6039cf8…`; model adapter at `216d1cc…` | Apache-2.0 code/model metadata; Qwen3.5-2B adapter, typed-decision serving path.[70][71] | Secondary local research lead, not an additional required integration. Model-card metrics are explicitly not independently verified. |
| H2O-Lightning-4B at `03b06b6…` | Apache-2.0 model metadata; Qwen3.5-4B-based decision model, distinct inference design.[72] | Further comparison lead; heavier than needed for this deadline, not tested on the Mac. |

FalkorDB server itself is **SSPL v1**, not an OSI-approved open-source stack. Keep code, server and model licenses separate; do not market proprietary cloud backends or every model trained-data right as “fully FOSS.”[30][73]

## 8. Research methods that improve the submission honestly

| Paper read | What to adapt | What not to claim |
|---|---|---|
| **Guo et al., On Calibration of Modern Neural Networks (2017)** | Held-out calibration evaluation; reliability diagrams, Brier/log loss, ECE. Temperature scaling is a post-hoc method requiring suitable outputs and a calibration set.[65] | A provider confidence field is already calibrated for this domain; temperature scaling guarantees safety under shift; we reproduced the paper. |
| **Geifman & El-Yaniv, Selective Classification for Deep Neural Networks (2017)** | A reject option and risk–coverage curve: how error among accepted predictions changes as more cases are deferred. The paper's risk-control result has sampling/statistical assumptions.[66] | A hand-chosen 0.9 threshold proves a 10% or smaller fleet error rate; guarantees transfer to novel/adversarial incidents. |
| **RouterBench (2024)** | Compare quality–cost tradeoffs to strong simple/random-mixture baselines, not only expensive-model-everywhere.[67] | Benchmark results establish Jev superiority, robot safety or a free speedup from adding a router. |

These complement the earlier VAP-TAMP-style observation/action verification, HUME-inspired hypothesis/refutation and LiP-LLM-inspired dependency/capability assignment. The new contribution would be a measured integration of graph-grounded evidence selection and selective decisions, not a new general theory of System One AI.

## 9. Evaluation that earns its place in the demo

**Hypothesis:** a bounded decision layer can reduce expensive generative calls or improve evidence selection at fixed operational correctness. If it cannot, remove it from the live decision path.

Compare:

1. canonical graph + deterministic branch/ranking baseline;
2. same graph/state + structured generative baseline;
3. same graph/state + Microsoft-Decision-1;
4. optional Jev stable and local Laya comparisons, only after access/installation is explicitly approved.

Do not compare a graph-rich fast model to an evidence-starved baseline. Use identical candidate sets, policy versions, questions and timeout budgets. Split by incident family/seed/revision, rather than leaking paraphrases of the same scenario between calibration and test.

Measure per decision family:

- top-1/macro-F1, confusion matrix, Brier/log loss and reliability;
- risk versus accepted coverage, with thresholds chosen on calibration data only;
- cost-weighted false merges, false support judgments and unnecessary escalations;
- end-to-end p50/p95/p99, including graph query, state projection, network, queue, retry, fallback and controller overhead;
- actual usage/cost, generative-call reduction, and error/refusal/timeout rate;
- graph-query rows/plan/time, claim winner count, stale-token rejection, cross-tenant denial and recovery outcomes.

Required adversarial/failure cases: missing revision, expired or superseded policy, overlapping restrictions, negation, wrong entity alias, stale model input, option-order perturbation, irrelevant long text, prompt-injected document, provider refusal/outage, simultaneous claim attempts, and crash after command send but before acknowledgement.

**For the live simulation:** no unapproved action may be executed, regardless of classification errors. Report finite test outcomes and uncertainty; a zero count in a bounded test is not a universal safety proof.

## 10. Enhanced three-track demo and scope

| Track | What the graph visibly does | Where System One can add value |
|---|---|---|
| 01: agents act on connected data | Resolves corridor/task/capability dependencies and current restrictions; changes investigation/assignment/resumption. | Interprets an ambiguous report or prioritizes the next permissible investigation. |
| 02: memory and coordination | Retains verified incidents and task claims; competing agents reconcile after restart with tenant isolation. | Ranks relevant verified episodes, if this produces measured benefit. |
| 03: Company Brain | Traverses the connected source/revision/evidence/owner/decision/restriction subgraph in the canonical graph. | Reranks evidence or flags contradiction; cannot manufacture authority. |

Suggested demo sequence: ambiguous obstruction report → graph-grounded investigation → scoped recovery permitted → physical clearance verified → loaded courier remains barred → current source/revision/owner evidence displayed → authorized synthetic release arrives → stale assessment rejected/recomputed → courier resumes → competing claim/restart replay demonstrates retained state.

Keep the scene visually simple. The compelling moment is **“clear floor, still forbidden—and here is the exact graph evidence”**, followed by a legitimate release. A model badge without a measured decision improvement is not an enhancement.

The official rules currently give a **15 October 12:01 AM IST to 18 October 11:59 PM IST** window, allow entering any/all tracks and require naming each entered track. They allow third-party frameworks/APIs and require disclosing AI coding assistants. This recommendation therefore favors a finished core path rather than an integration showcase.[39]

## 11. Completion and evidence boundaries

**Done:** deep primary-document audit, release/source inspection, model/API comparison, read-only local database/Azure checks, FOSS/license reconnaissance, method reading, and a revised integration/evaluation design.

**Not done:** application implementation, GraphRAG package installation or test run, graph schema migrations, data-volume/ACL changes, paper reproduction, model inference, robot/fleet simulation, concurrency benchmark, durability recovery test or submission deployment.

The docs contain real contradictions; this report records them rather than quietly choosing the optimistic statement. All performance figures attributed to providers are published claims, not output fabricated from this project's nonexistent benchmark.

<!-- GENERATED CITATION REFERENCES -->

## Sources

[4] https://docs.falkordb.com/cypher/cypher-support.md — OpenCypher Standard Compatibility and Feature Coverage
[5] https://docs.falkordb.com/cypher/known-limitations.md — Cypher Query Limitations and Unsupported Features
[6] https://docs.falkordb.com/design/concurrency.md — Atomicity and Concurrency Control in FalkorDB
[9] https://docs.falkordb.com/commands/acl.md — ACL: FalkorDB Access Control List Command Reference
[10] https://docs.falkordb.com/commands/graph.constraint-create.md — GRAPH.CONSTRAINT CREATE: Creating Graph Constraints in FalkorDB
[11] https://docs.falkordb.com/operations/durability/index.md — FalkorDB Durability and Data Persistence Guide
[12] https://docs.falkordb.com/operations/durability/persistence.md — Configuring RDB & AOF Data Persistence in Docker
[13] https://docs.falkordb.com/operations/replication.md — FalkorDB Replication: High Availability and Read Replicas
[14] https://docs.falkordb.com/operations/cluster.md — FalkorDB Cluster Deployment: Horizontal Scaling & Sharding
[15] https://docs.falkordb.com/commands/graph.ro-query.md — GRAPH.RO_QUERY: Read-Only Cypher Queries in FalkorDB
[16] https://docs.falkordb.com/commands/graph.query.md — GRAPH.QUERY: Executing Cypher Queries in FalkorDB
[17] https://docs.falkordb.com/algorithms/astar.md — algo.AStar
[18] https://docs.falkordb.com/cypher/indexing/cch-index.md — CCH Indexing: Fast Point-to-Point Shortest Paths on Weighted Graphs
[19] https://docs.falkordb.com/cypher/indexing/range-index.md — Range Indexing: Fast Equality and Range Lookups
[20] https://docs.falkordb.com/cypher/indexing/fulltext-index.md — Full-Text Indexing: Fast Fuzzy and Text Search in FalkorDB
[21] https://docs.falkordb.com/cypher/indexing/vector-index.md — Vector Indexing: Fast Similarity Search for GraphRAG
[22] https://docs.falkordb.com/algorithms/sppath.md — Shortest Paths Between Nodes (algo.SPpaths) Graph Algorithm
[25] https://docs.falkordb.com/commands/graph.explain.md — GRAPH.EXPLAIN: Inspecting Cypher Query Execution Plans
[26] https://docs.falkordb.com/commands/graph.profile.md — GRAPH.PROFILE: Profiling Cypher Query Performance
[27] https://docs.falkordb.com/operations/opentelemetry.md — OpenTelemetry Integration: Distributed Tracing for FalkorDB
[29] https://docs.falkordb.com/udfs/index.md — User Defined Functions (UDFs) in FalkorDB: Custom Logic in Cypher
[30] https://docs.falkordb.com/references/license.md — FalkorDB License: Server Side Public License (SSPLv1)
[31] https://redis.io/docs/latest/develop/using-commands/transactions — Transactions | Docs
[32] https://docs.falkordb.com/graphrag/architecture.md — GraphRAG SDK Pipeline Architecture
[33] https://docs.falkordb.com/graphrag/graph-schema.md — Graph Schema
[34] https://docs.falkordb.com/graphrag/incremental-updates.md — Incremental Updates
[35] https://docs.falkordb.com/graphrag/reliability-and-grounding.md — Reliability and Grounding
[36] https://docs.typesafe.ai/models — Models - TypeSafe
[37] https://docs.typesafe.ai/model-jaggedness/jev-1.13 — Jev 1.13 jaggedness - TypeSafe
[39] https://www.wemakedevs.org/hackathons/falkordb/rules — Rules | Graph Hacks: Context for AI Agents | WeMakeDevs
[41] https://developers.openai.com/api/docs/guides/decisions — Decisions | OpenAI API
[42] https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-microsoft-decision — Deploy and use Microsoft-Decision-1 in Microsoft Foundry - Microsoft Foundry | Microsoft Learn
[44] https://typesafe.ai/blog/introducing-system-one-models-and-jev — Introducing System One Models & Jev - TypeSafe AI Blog
[45] https://docs.typesafe.ai/confidence.md — Confidence
[46] https://docs.typesafe.ai/images.md — Images
[47] https://docs.typesafe.ai/primitives/box.md — Box
[48] https://docs.typesafe.ai/api.md — API reference
[49] https://docs.typesafe.ai/cookbooks/entity_alignment.md — Knowledge graph entity alignment
[50] https://docs.typesafe.ai/cookbooks/rerank_typesafe.md — Re-ranking
[52] https://commandline.microsoft.com/microsoft-decision-1-model-foundry — Microsoft-Decision-1: Our model for fast decision-making
[55] https://docs.falkordb.com/operations/durability/acl-persistence.md — Managing Persistent ACL Users and Permissions on Docker
[56] https://github.com/FalkorDB/FalkorDB/releases/tag/v6.0.2 — FalkorDB v6.0.2 release
[57] https://github.com/FalkorDB/FalkorDB/blob/7b7b4d1ed23fe78e69fa5da0c9e4f2ea2e73f3e9/src/query_session.rs — FalkorDB v6.0.2: src/query_session.rs
[58] https://github.com/FalkorDB/FalkorDB/blob/7b7b4d1ed23fe78e69fa5da0c9e4f2ea2e73f3e9/graph/src/runtime/functions/procedures.rs — FalkorDB v6.0.2: graph/src/runtime/functions/procedures.rs
[59] https://github.com/FalkorDB/FalkorDB/blob/7b7b4d1ed23fe78e69fa5da0c9e4f2ea2e73f3e9/graph/src/runtime/ops/node_by_vector_scan.rs — FalkorDB v6.0.2: graph/src/runtime/ops/node_by_vector_scan.rs
[60] https://github.com/FalkorDB/FalkorDB/blob/7b7b4d1ed23fe78e69fa5da0c9e4f2ea2e73f3e9/src/graph_core.rs — FalkorDB v6.0.2: src/graph_core.rs
[61] https://github.com/FalkorDB/GraphRAG-SDK/blob/35e67a0b27fdcc7f2c28508b09e86169851a8187/graphrag_sdk/pyproject.toml — GraphRAG SDK pinned: graphrag_sdk/pyproject.toml
[62] https://github.com/FalkorDB/GraphRAG-SDK/blob/35e67a0b27fdcc7f2c28508b09e86169851a8187/graphrag_sdk/src/graphrag_sdk/api/main.py — GraphRAG SDK pinned: graphrag_sdk/src/graphrag_sdk/api/main.py
[63] https://github.com/FalkorDB/GraphRAG-SDK/blob/35e67a0b27fdcc7f2c28508b09e86169851a8187/graphrag_sdk/src/graphrag_sdk/core/connection.py — GraphRAG SDK pinned: graphrag_sdk/src/graphrag_sdk/core/connection.py
[64] https://github.com/FalkorDB/GraphRAG-SDK/blob/35e67a0b27fdcc7f2c28508b09e86169851a8187/graphrag_sdk/src/graphrag_sdk/retrieval/router.py — GraphRAG SDK pinned: graphrag_sdk/src/graphrag_sdk/retrieval/router.py
[65] https://arxiv.org/html/1706.04599v2 — On Calibration of Modern Neural Networks
[66] https://arxiv.org/html/1705.08500v2 — Selective Classification for Deep Neural Networks
[67] https://arxiv.org/html/2403.12031v1 — RouterBench: A Benchmark for Multi-LLM Routing System
[69] https://github.com/FalkorDB/GraphRAG-SDK/blob/35e67a0b27fdcc7f2c28508b09e86169851a8187/graphrag_sdk/src/graphrag_sdk/core/models.py — GraphRAG SDK: provenance and document models
[70] https://github.com/strands-labs/strands-decider/tree/6039cf8b64c6074e75804000c07ac3d4cce795f7 — Strands Decider pinned source
[71] https://huggingface.co/StrandsAgents/strands-decider-2B-qwen3.5-v1-2610/tree/216d1ccb46a9e9b036eb9187b248db98480f77d4 — Strands Decider model card and adapter
[72] https://huggingface.co/h2oai/h2o-lightning-4b/tree/03b06b677b071d762d19757ac84662ba05f90349 — H2O-Lightning-4B pinned model
[73] https://github.com/FalkorDB/FalkorDB/blob/7b7b4d1ed23fe78e69fa5da0c9e4f2ea2e73f3e9/LICENSE — FalkorDB v6.0.2 license
[74] https://github.com/typesafe-ai/typesafe-sdk-python/tree/f36e68549ceca3191e5791e5f99ea1baa1a258b5
[75] https://github.com/typesafe-ai/system-one-adapter-python/tree/e1d4cc938204b22fc5a3c3aca7044072fe3f712d
[76] https://github.com/NandhaKishorM/laya/tree/432312b36714d8889eba405507b37eda25257d9c
[77] https://huggingface.co/convaiinnovations/laya/tree/7b928d828b7b0e022f929d9bd2e44165aa270148
[78] https://github.com/FalkorDB/GraphRAG-SDK/blob/35e67a0b27fdcc7f2c28508b09e86169851a8187/graphrag_sdk/src/graphrag_sdk/ingestion/structured_pipeline.py — GraphRAG SDK: deterministic structured pipeline
[79] https://github.com/FalkorDB/GraphRAG-SDK/blob/35e67a0b27fdcc7f2c28508b09e86169851a8187/graphrag_sdk/src/graphrag_sdk/ingestion/extraction_strategies/graph_extraction.py — GraphRAG SDK: span extraction and propagation
[80] https://github.com/FalkorDB/GraphRAG-SDK/blob/35e67a0b27fdcc7f2c28508b09e86169851a8187/graphrag_sdk/src/graphrag_sdk/ingestion/chunking_strategies/fixed_size.py — GraphRAG SDK: fixed-size chunk offsets
[81] https://github.com/FalkorDB/GraphRAG-SDK/blob/35e67a0b27fdcc7f2c28508b09e86169851a8187/graphrag_sdk/src/graphrag_sdk/ingestion/chunking_strategies/sentence_token_cap.py — GraphRAG SDK: default chunk metadata
[82] https://github.com/FalkorDB/GraphRAG-SDK/blob/35e67a0b27fdcc7f2c28508b09e86169851a8187/graphrag_sdk/src/graphrag_sdk/core/providers/base.py — GraphRAG SDK: provider contracts
