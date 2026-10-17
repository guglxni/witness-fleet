# System One in a graph-grounded robot fleet: prior-work review and design recommendation

**Snapshot:** 15 October 2026. **Purpose:** deepen the project’s existing System One calibration audit and robot-method review. This is research/design, not implementation. I read the full primary HTML/PDF methods for the direct System One works and selected method papers noted below; retrieved public paper text over HTTP because the configured `web_extract` backend is search-only. Nothing here reports a new Jev/model/API call, robot run, software install, benchmark, or safety validation. Local primary-text snapshots are in `evidence/systemone-snapshots/`; the URL-keyed ledger is `evidence/sources.json` (from repository root).

## Executive decision

Integrate System One only as an **advisory decision primitive over a graph-computed, versioned, bounded state**. Highest-value first experiment: (1) FalkorDB returns the eligible policy/source/revision/evidence witnesses plus unresolved/contradictory evidence; (2) deterministic code filters by tenant, authority, status, temporal validity, scope, and exact ID; (3) a typed decision model ranks evidence relevance/support/contradiction or selects among explicitly permissible *investigation* branches; (4) a deterministic verifier checks all mandatory current restrictions and preconditions; (5) the action remains blocked unless independent policy and physical gates pass. The model may order what a person/agent inspects first. It must not prune away authoritative restrictions, create a release, establish physical clearance, or authorize dispatch.

This fits closest to (a) newly surfaced Jev-specific empirical evidence and JevOut red-team work, (b) SENTLI’s entailment-aware retrieval/reranking, (c) SayCan’s separation of task usefulness from world feasibility, and (d) KnowNo’s prediction-set clarification. REFLEX directly tests a Jev control/escalation role but also finds that authorization-sensitive “is any action warranted?” cases are harder than selecting a function. AnyJev is a relevant reproducible alternative/benchmark baseline, but its restricted next-token probabilities are not native trained decision-model outputs. FrugalGPT and RouteLLM motivate economic evaluation, not importing a router blindly. Simplex informs the hard runtime-assurance boundary; neither typed-model confidence nor a data graph substitutes for an independently enforced motion/policy safety kernel.

**Recommendation:** start with one typed-decision backend already configured in the workspace; Microsoft and Jev are distinct providers (Microsoft-Decision-1 is the existing deployment candidate in the preceding audit; no inference or service check occurred here), pin the exact model/API version, and keep a provider-neutral adapter. The papers do not establish this deployment’s latency, quality, quota, or reliability. Compare to deterministic ranking and an open-model probability baseline on the *same graph witnesses and prompts*. Do not add model routing unless a measured validation result shows that its expected benefit exceeds extra cost and failure surface.

## Why the new Jev evidence changes the implementation stance

### S01 — Jev benchmark: useful calibration nuance, not a fleet prior

Deußer, Sparrenberg, and Sifa evaluate Jev `jev-1.13.0` zero-shot on 37 public datasets and 346,009 requests, with frozen per-dataset templates, bootstrap intervals, reliability/calibration measures, selective prediction, and open-weight next-token-probability comparators.[84] Their main Choice result is positive but bounded: pooled ECE across 22 Choice datasets is 0.028, but the unweighted mean per-dataset ECE is 0.061; miscalibration is concentrated in weaker datasets, with Emotion and low-resource AfriXNLI among the extremes. Their binary `noul` probabilities behave differently: single-label yes probabilities are slightly under-confident overall, while multi-label one-question-per-class requests substantially over-predict “yes.”[84]

This directly deepens the earlier report’s correct warning that confidence is not automatically a per-item correctness guarantee. **A particularly actionable finding:** default `0.5` thresholds are not universally appropriate. For the evaluated prompt-injection dataset, the paper reports perfect precision but only 50% recall at the fixed threshold despite AUROC 0.982. On multi-label GoEmotions, scores rank reasonably while thresholded macro-F1 is poor; tuned application thresholds improve some tasks. The authors tune thresholds using 1,000 training/validation examples and apply them unchanged to the evaluation split, and explicitly note thresholds are task-specific. Threshold tuning does not fix weak separability, as their AGB-DE legal-task discussion illustrates.[84]

**Adaptation:** retain full option/yes distributions; calibrate and set each acceptance/escalation rule per *decision family* using a dedicated held-out calibration set. For Choice, evaluate top-option probability and top-two margin as distinct signals. For binary evidence support, select thresholds against asymmetric false-support costs rather than 0.5; preserve `neutral/insufficient`. For multi-label alias candidates, do not treat independent binary outputs as a mutually exclusive distribution. Use explicit `none_of_these` and no auto-merge.

**Not established by the paper:** that Jev 1.13.0 generalizes to fleet policies, other Jev versions, Microsoft Decision, graph evidence, adversarial document context, temporal restrictions, or safety. The authors note one template per dataset, limited memorization probes, no run-to-run variance, version-specific findings, and no relevance-judgment dataset. Their data are not a project benchmark.[84]

**Runnable code status:** author code is verifiably at `AppliedMachineLearning-Lab/jev-benchmarking`, commit `87562114d23597f610754f057e5e0da8659dbcfb`, MIT. README describes a Python 3.10+ harness, frozen templates, analyses, and raw responses on Zenodo. It can support a reproducibility/extension baseline; it requires dependencies/data and a Jev API for new calls. I did not install or run it.[158]

### S02 — JevOut: high-priority context robustness test

“JevOut: Natural Context Can Flip Decision Models” studies whether a fluent context addition that preserves the gold answer can redirect an initially correct bounded decision toward a wrong target fixed in advance. Across four systems, seven datasets, and at most 64 accepted target evaluations per decision, the authors report targeted flips for 61.4–73.2% of initially correct decisions. A majority judgment of three annotators classified 91.6% of 250 sampled successful contexts as natural, answer-preserving, and lacking decisive answer-changing evidence.[85]

Interpret this narrowly and seriously: the work demonstrates **searchable attackability under a finite, probability-guided optimization budget** on its evaluated English finite-choice tasks. It does *not* estimate how often ordinary naturally occurring inputs cause errors, nor does it establish closed-loop robot impact. The paper explicitly identifies extending to multilingual inputs/open-ended actions and measuring propagation in an interactive closed-loop environment as future limitations.[85] Still, it makes a retrieval-state injection/irrelevant-detail test mandatory: high initial confidence and “natural-sounding” text are not enough.

**Adaptation:** preserve a canonical `DecisionInput` snapshot (graph version, evidence IDs, exact source spans, model/options schema, and normalized evidence order); never append untrusted raw documents into a privileged decision prompt without segmentation/quoting; include the same evidence provenance and rubric every time. Add a red-team suite with irrelevant but plausible context, negation, quoted instructions, stale-but-plausible release language, and context-order changes. Test whether support/branch choices change when irrelevant text is appended or irrelevant graph neighbors are included. A change should trigger a conservative path, not an automatic act.

**Runnable code status:** paper authors’ `xzx34/JevOut`, commit `c8ab231728abb54bd61cf3c8812cb48811aae36b`, Apache-2.0. Repository README announces v0.2.0 with offline demo, independent-generation baseline, repeatability tools, and experiment documentation. It is a useful adversarial test-design reference, not a calibrated production defense. Not executed.[159]

### REFLEX with Jev — directly relevant selective control, with a sharp authorization caveat

Wu and Lim’s REFLEX paper uses Jev for bounded agent choices and delegates low-confidence decisions or generation-required steps to a stronger generative model. Their frozen 100-task controlled benchmark reports 95% task success and 72.7% fewer strong-model calls at its primary setting compared with a strong-only agent, with results across three fallback families. But external BFCL/τ-style evaluations give limited gains over a cheap generative cascade when ordinary routing is already accurate. More importantly for this fleet, the authors report 98.4% function-selection accuracy but 52.0% relevance accuracy on an external BFCL slice, and controlled interventions show larger action sets and structurally near-valid alternatives can degrade authorization-boundary decisions.[156]

**Adaptation:** if used, ask “which of these already graph-eligible investigation steps should be prioritized?” not “is the restriction valid/does permission exist?” Make an escalation `abstain | request_operator_review` a first-class outcome. Apply the deterministic gate after the model regardless of its score. The REFLEX paper is the strongest empirical argument for testing a typed model as an *efficiency* layer and against promising it as an authorization mechanism.

**Evidence/code status:** primary full text and arXiv metadata inspected; authors are Tiantong Wu and Wei Yang Bryan Lim, `arXiv:2609.26532v1`. No author repository was established in this review. Its claimed 100-task results are paper reports, not independently reproduced here.[156]

### S12 — AnyJev: fair baseline warning and promising local comparison lead

AnyJev reads a finite choice from a pretrained instruction-tuned model’s next-token distribution restricted to option-label tokens; it corrects estimated label priors and averages log probabilities across cyclic permutations of the option list. The early report says full rotations reduce order flips and improve accuracy on two 20-option tasks, while rotation costs up to one prefill per option; an agreement stopping rule can reduce work under their stated selection/bounding procedure.[157] Their key methodological point: converting generated answer text into probabilities after the fact is not the same as reading a true option distribution. Even restricted next-token probability baselines may be affected by option-label and position biases and require their own calibration/evaluation.[157]

**Adaptation:** compare native Jev to (a) deterministic rules and (b) a clearly labeled restricted-logit baseline (e.g. AnyJev), with equal state, choice set, option order protocol, evidence, and latency budget. Do not call a generative API plus guessed/logprob-normalized output “calibrated System One.” Avoid using AnyJev on critical real-time actions without measuring prefills, calibration, and robustness.

**Code status:** `nokia-applied-research/AnyJev` verified at commit `b03158e9ba18e84c01054aaa393481925088db07`, Apache-2.0. Public README describes training-free and self-distilled variants, PyPI installation, and serving; vendor/org README performance claims remain author claims. No installation or execution here.[164]

## Useful adjacent methods and exact transfer boundary

### S04 — NLI entailment-aware evidence reranking (SENTLI)

Schuster et al. (“Stretching Sentence-pair NLI Models to Reason over Long Documents and Clusters”) use sentence-pair NLI scores not just to classify a claim but to retrieve relevant spans. For a hypothesis, candidate spans are separately ranked by entailment and contradiction; their retrieve-and-rerank step concatenates top support and contradiction spans in both orders and reruns NLI. They report this can improve zero-shot ContractNLI performance, while gains are small for a supervised model; the paper flags neutral-vs-relevant discrimination and multi-hop evidence as limitations.[150]

**Adaptation:** an evidence statement such as “this approved revision releases corridor C for loaded courier T during interval W” should be atomic. For each candidate exact span, use the current F-001 labels `supports | contradicts | irrelevant | insufficient` from DECISION_CONTRACTS.md; `neutral` is only the prior NLI literature's umbrella class, not the wire contract. Rank both supporting *and contradictory* candidates. Reranking changes review order only. Always return the graph witness IDs and original source offsets. A top-k cut cannot be used as an authority filter; an unranked restriction still gets checked by the deterministic current-policy query. No author implementation established in this review; no reproduction.

### S05 — SayCan: separate linguistic usefulness from embodiment feasibility

SayCan scores whether a language-labeled skill makes progress toward an instruction and combines this with a learned, state-dependent affordance value for whether the skill can succeed. The paper’s idealized selection multiplies those terms; it uses pre-trained low-level skills/value functions and real-world tasks. The authors also acknowledge that environmental feedback may be limited to current-step affordance scoring, so failure/change feedback may be unavailable.[151]

**Adaptation:** graph eligibility/capability/reachability and a classical geometry/policy evaluator play the “Can” role; a typed classifier may prioritize useful investigation branches (“Say”). Do not multiply model softmax scores with physics and call the product a calibrated safety probability. Model utility and physical feasibility have different labels, provenance, and calibration targets. Commands still need post-action sensor verification. Official Google Research contains a self-contained tabletop pick-place notebook, not a drop-in fleet implementation; repository license Apache-2.0. Not run.[160]

### S06 — KnowNo: clarification as a prediction-set decision

KnowNo generates candidate plans and obtains normalized option scores, then uses conformal prediction to produce a set of plausible options. A singleton can be executed under its setup; a non-singleton asks a human/supervisor to clarify. The method addresses multi-step planning through sequence-level calibration because feedback changes later contexts and breaks naive independent-step assumptions. Its statistical claims rely on exchangeability/sampling and correct-help assumptions; the paper describes i.i.d. calibration scenarios and explicitly treats human help as accurate in the task-completion argument.[152]

**Adaptation:** when a model proposes two plausible investigation branches, expose a short, evidence-grounded clarification question or defer to operator review; do not silently choose an arbitrary argmax. Conformal set size is an ambiguity signal, not policy authorization. If the route/action set omits the true safe action, the set cannot recover it. Recalibrate after changes to model/version, graph projection, option schema, evidence distribution, or task family. The paper’s author repository has Colab and simulation artifacts but GitHub API showed no root license; do not assume reusable licensed code. Not run.[161]

### S07 — RouteLLM and S08 — FrugalGPT: economic ideas, not a robot router to copy

RouteLLM estimates whether a stronger model beats a weaker one from preference data, then uses a threshold to pick one model. The authors train on Chatbot Arena preference data and report cost-quality tradeoffs on language-model benchmarks.[153] FrugalGPT studies prompt adaptation, approximation, and sequential cascades: query the inexpensive model first, score reliability, and escalate when the score is below a threshold; their experiments were on 2023 APIs/datasets and optimize a budgeted performance objective.[154]

**Adaptation:** if comparing System One vs a generative fallback, estimate expected net benefit by task family using paired evaluations. A cheap confidence score alone is not enough; model-calibrated acceptance must be measured on the relevant data. A single more expensive model is not necessarily better for each input, and fallback can repeat the same context bias. Keep retry/escalation bounded and idempotent; record cost and time. Neither paper supports cost savings or safety benefit in this project. RouteLLM author code is Apache-2.0 and verified; FrugalGPT author repository is Apache-2.0. Neither was installed/run.[162][163]

### S15 — Value of computation: bounded metareasoning, not an assumed router win

Hansen and Zilberstein formalize monitoring and control of anytime algorithms as a sequential metalevel decision problem. Their dynamic-programming framework jointly considers solution quality, expected progress, delay cost, uncertain algorithm performance and domain state, and the cost/timing of monitoring; this is explicitly non-myopic relative to a one-step expected-value-of-computation rule.[165] It sharpens the economic question behind RouteLLM/FrugalGPT: do not route solely on a static confidence cutoff when an additional observation, graph query, or fallback may change future options and consume deadline.

**Adaptation:** treat each optional computation as a bounded action with a measured cost and outcome model: e.g., fetch a missing authoritative witness, ask for one independent evidence rerank, request one operator clarification, or invoke one generative fallback. Stop when deadline/budget is reached or the expected improvement in advisory decision utility is no greater than total compute, queue, review, and delay cost. This is not the original paper’s algorithm applied unchanged: its dynamic program assumes a modeled performance profile and utility/state transition; those must be learned/estimated and validated for this fleet. Initially use a small fixed cascade and report cost/quality curves; do not claim optimal metareasoning without a validated model. Full 2001 methods paper fetched and read; no runnable author code checked and no reproduction.[165]

### S09 — Simplex/runtime assurance: non-negotiable authority separation

Black-Box Simplex describes a runtime assurance architecture with an advanced controller, baseline controller, and decision module that runtime-checks candidate command sequences and switches to a stored sequence when safety cannot be ensured. Its guarantees are formal only under its stated system model, safe-sequence/reachability assumptions, and correctness of the decision module; it addresses CPS command-sequence safety, not semantic authority in business policy.[155]

**Adaptation:** keep the agent/model outside the trusted action gate. An adapter result can propose/reorder an *advisory plan*. A deterministic dispatch gate checks current graph/policy version, fresh physical evidence, scope, capabilities, collision/geometry constraints, task claim/fencing, and the live simulator/controller interlock. Any failed/unknown check stops, waits, or routes to the verified baseline/manual path. This project’s deterministic checks are an engineering pattern, not a Simplex implementation or formal proof.

## Proposed System One contract in the FalkorDB project

The existing audit proposes canonical FalkorDB operations graph, direct persistence of verified episodes/task state, and (optionally) a separate GraphRAG-SDK corpus graph; GraphRAG’s corpus is discovery, not authority. Preserve that split.[32][35]

### Bounded, versioned model request

Input only a compact projection with:
- `tenant_id`, stable `graph_snapshot_version`/policy version and an evidence snapshot hash;
- question family and schema version;
- one atomic claim or incident question, not a raw graph dump;
- at most a fixed small `K` candidate evidence IDs/spans, with a per-passage token cap and explicit source/revision/approval/currentness fields produced by deterministic code;
- a fixed allowlisted label set, including `insufficient`, `contradicts`, `none_of_these`, and/or `abstain` as appropriate;
- untrusted text delimited and quoted as data, not embedded as instructions; no tool invocation available to the model.

Preserve full distributions, raw provider/model identity, normalized outputs, latency, usage, retry count, input hash, and failure status. Validate labels, finite numbers, range, sum-to-one where applicable, schema/version, and response completeness. Do not coerce refusal, timeout, missing choice, NaN, or malformed values into a class. Invalidate the assessment if graph/evidence/policy versions changed before acting.

### Bounded branch selection

1. Query all deterministic prerequisites and candidate branches. The graph returns `eligible`, `ineligible(reason)`, or `unknown`, based on explicit policy/capability/temporal/physical data.
2. Ask the model to rank only the eligible advisory branches: e.g. `inspect_corridor`, `check_revision`, `ask_operator`, `abstain`. Label order is randomized/fixed in a testable manner and `resume_courier`/`override_safety` are not choices.
3. Accept only if the calibrated selective gate passes; otherwise defer to a deterministic baseline/operator. The result never mutates authority state.
4. Execute a selected inspection via normal task claim/CAS, idempotency key and simulator/controller checks. Observe after execution and persist result separately from expected effect.

### Evidence reranking and aliases

For one exact atomic proposition, sort candidate spans for review using a typed `supports | contradicts | neutral/insufficient` result and an evidence relevance score. Return both strongest supporting and contradictory span IDs. The deterministic applicable-policy query is exhaustive over active restrictions/releases and independent of model top-k. For entity resolution, present alias suggestions as `canonical candidate(s) | none`; only ingestion workflow may propose a merge and it requires independent validation. False alias merges are measured as high-cost errors; no model-suggested edge is committed as canonical by default.

### Why this cannot authorize action

- A language model estimates semantic relations over prompt text; it does not authenticate the approving actor, validate cryptographic signatures, establish temporal scope, or create a release record.
- Current restrictions are exact graph semantics and must be checked deterministically even if semantically low-ranked.
- Physical clearance requires fresh sensor/geometry/controller evidence scoped to the actual courier footprint and load. A model cannot turn a scout’s different footprint into courier clearance.
- Confidence and CP coverage are statistical properties, not permission. An adversarial or stale context can shift the model while retaining a plausible surface form.[85]
- Conformal coverage holds only under its exchangeability/calibration setup; multi-step feedback, new model versions, distribution shift and invalid human clarification can defeat the intended interpretation.[152]
- Runtime assurance is about a separately specified safe command set and trusted checker. This project has not established that formal apparatus.[155]

## Evaluation matrix: claims we can actually falsify

| Claim under test | Equal-information baseline | Required measured outcome | Kill/falsification condition |
|---|---|---|---|
| NLI reranking finds better evidence than lexical/vector ordering | Same canonical graph candidate set, same exact spans and question; lexical/vector and deterministic metadata ranking | nDCG/MRR or top-k support/contradiction recall by policy family; human-adjudicated evidence labels; p95 and tokens/cost | No statistically defensible improvement, missing contradictions, or lower exact-span traceability. Keep deterministic ranking. |
| Branch choice reduces expensive generation | Deterministic branch policy, generative-only policy, and System One + calibrated fallback, with identical graph and scenario | Accepted coverage, selective error, unnecessary fallback, strong-model calls/cost per valid resolution, full end-to-end p50/p95/p99 | No lower cost at non-inferior operational quality, or extra model latency exceeds saved latency. Remove router. |
| Clarification prevents bad action | Deterministic uncertainty/review baseline and argmax model; known gold alternatives; accurate vs noisy/missing operator replies | Risk-coverage, set size, task success, query count, wrong action and review burden by family | Omitted correct option, unreliable operator, sequence-level risk above bound, or no useful coverage. Never claim guarantee outside assumptions. |
| Graph-context guard resists context redirection | Same gold input with matched irrelevant, quoted-injection, stale-revision, negation, option-order, and paraphrased context variants | Decision-flip rate, high-confidence wrong rate, support/contradiction flips, abstention changes; paired cluster intervals | Material, high-confidence flips that pass the app gate; harden prompt/evidence isolation and re-test. |
| Alias suggestions improve ingestion | Current exact-ID resolution and human/manual adjudication | Precision/recall, false merge rate weighted by downstream policy consequence, none-of-these use | Any unapproved automatic canonical merge, or worse high-cost false-merge rate than exact/deterministic baseline. |

Required cases: missing/expired/superseded revision; overlapping/contradictory current restrictions; unsigned and explicitly owner-approved synthetic release (cryptographic signing only if separately implemented); wrong owner; stale assessment; scope mismatch; scout-vs-loaded-courier clearance; narrow corridor; negation; benign distractor; quoted malicious text; reordered options; provider refusal/timeout/malformed response; graph version race; refusal when an operator answer is absent; successful decision after uncertainty. Split by incident family/seed/revision, not near-duplicate paraphrase. Keep calibration, threshold selection, and untouched test data separate.

Report real counts/denominators and paired confidence intervals. Do not fabricate a benchmark or import any paper’s headline performance as a project expectation. The project research record states that no project inference, simulation, concurrency, runtime or application benchmark was run; external SDK documentation is not evidence of these local execution facts.

## Evidence levels and reuse hygiene

- **Paper-reported:** S01/S02/S11/S12 and the cited SENTLI, SayCan, KnowNo, RouteLLM, FrugalGPT, Simplex, and metalevel-control methods are the authors’ claims under their respective setups.
- **Proposed adaptation:** the typed interface, graph projection, branch labels, gates, evidence reranking protocol, risk/cost metrics, and failure criteria in this report.
- **Unverified for this project:** every candidate’s performance, calibration, cost, latency, API entitlement, local runtime, and benefit on the robot task.
- **Code:** selected author repositories were inspected, not installed or run. Jev benchmark and JevOut are separate evaluation-code releases.[158][159] SayCan is a partial author demonstrator; KnowNo root reuse permission was not established.[160][161] RouteLLM, FrugalGPT and AnyJev are comparison references, not selected fleet dependencies.[162][163][164] Hosted models, weights and data remain separately licensed.
- **No benchmark:** the 37-dataset Jev work, JevOut, REFLEX, AnyJev, and prior robotics results are not the FalkorDB project’s benchmark. The only project claims remain hypotheses until the harness runs.

## Focused source list

Source IDs use the package-wide ledger and have already been remapped. The direct System One works are Jev benchmark, JevOut and REFLEX.[84][85][156]

The evidence/robotics bridges are SENTLI, SayCan and KnowNo.[150][151][152]

Routing/economics references include RouteLLM, FrugalGPT and Hansen–Zilberstein anytime metalevel control.[153][154][165]

Black-Box Simplex motivates an independent runtime-assurance boundary.[155]

AnyJev is a supplementary actual-logit baseline, not evidence that every LLM readout equals native System One.[157]

Guo calibration and Geifman–El-Yaniv selective classification extend the prior probability audit.[65][66]

FalkorDB/GraphRAG architecture and grounding documentation inform the isolated corpus boundary.[32][35] Canonical URLs, identities, versions and code-status notes are in `evidence/sources.json`.

<!-- GENERATED CITATION REFERENCES -->

## Sources

[32] https://docs.falkordb.com/graphrag/architecture.md — GraphRAG SDK Pipeline Architecture
[35] https://docs.falkordb.com/graphrag/reliability-and-grounding.md — Reliability and Grounding
[65] https://arxiv.org/html/1706.04599v2 — On Calibration of Modern Neural Networks
[66] https://arxiv.org/html/1705.08500v2 — Selective Classification for Deep Neural Networks
[84] https://arxiv.org/html/2609.37647v1 — Evaluating and Benchmarking the System One Model Jev
[85] https://arxiv.org/html/2609.30243v2 — JevOut: Natural Context Can Flip Decision Models
[150] https://arxiv.org/html/2204.07447v2 — Stretching Sentence-pair NLI Models to Reason over Long Documents and Clusters (SENTLI)
[151] https://proceedings.mlr.press/v205/ichter23a/ichter23a.pdf — Do As I Can, Not As I Say: Grounding Language in Robotic Affordances (SayCan)
[152] https://proceedings.mlr.press/v229/ren23a.html — Robots That Ask For Help: Uncertainty Alignment for Large Language Model Planners (KnowNo)
[153] https://arxiv.org/html/2406.18665v4 — RouteLLM: Learning to Route LLMs from Preference Data
[154] https://arxiv.org/pdf/2305.05176 — FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance
[155] https://arxiv.org/pdf/2102.12981 — The Black-Box Simplex Architecture for Runtime Assurance of Autonomous CPS
[156] https://arxiv.org/html/2609.26532v1 — REFLEX with Jev for Efficient Selective Control in LLM Agents
[157] https://arxiv.org/html/2610.00831v1 — AnyJev Technical Report
[158] https://github.com/AppliedMachineLearning-Lab/jev-benchmarking — Jev benchmarking author code
[159] https://github.com/xzx34/JevOut — JevOut author code
[160] https://github.com/google-research/google-research/tree/master/saycan — SayCan official author code path
[161] https://github.com/patrickhaoy/KnowNo — KnowNo author repository
[162] https://github.com/lm-sys/RouteLLM — RouteLLM author framework
[163] https://github.com/stanford-futuredata/FrugalGPT — FrugalGPT author code
[164] https://github.com/nokia-applied-research/AnyJev — AnyJev author implementation
[165] https://www.sciencedirect.com/science/article/pii/0004370200000680 — Monitoring and control of anytime algorithms: A dynamic programming approach
