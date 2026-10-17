# System One math notes: calibration, evidence ranking, selective use, and bounded escalation

**Status:** design equations and evaluation recipe, not measured results. All probabilities, costs, thresholds, and examples below are symbols or proposed procedures unless explicitly attributed to a cited paper. Do not instantiate thresholds from these notes without task-specific labeled data. Numeric source IDs use the package-wide `../evidence/sources.json` ledger; S-labels in section titles are historical reading-note labels, not separate citation IDs.

## 1. Objects and non-overlapping probability meanings

Let a decision request be

\[
x=(g, v_g, v_p, q, E, \mathcal{Y}, s),
\]

where `g` is a local tenant namespace (never sent as a raw graph key), `v_g` the snapshot vector including graph version and policy epoch, `v_p` the question-schema version, `q` an atomic question, `E=(e_1,\ldots,e_m)` a **bounded** set of exact evidence spans with immutable IDs/provenance, `\mathcal{Y}` a fixed option set, and `s` the safe/eligible state projected by deterministic code. The model returns either a Choice distribution \(p(y\mid x)\), a binary predicate probability, an ordered-score distribution, or an explicit status (`ok`, `abstain`, `refusal`, `unavailable`, `invalid`). A returned probability concerns its labeled model question under its evaluated distribution. It is not automatically:

- the probability that an evidence span is the *legally/operationally authoritative* current policy;
- the probability that an alias is the same physical corridor;
- the probability that a robot can physically traverse after payload/footprint effects;
- a permission or signed authorization.

For multi-choice, store the whole distribution and its label mapping; never store only the argmax. For binary `noul`, preserve `P(yes)` and prompt/version. For score, preserve level probabilities, level ordering and the expected score separately. Provider confidence is not itself a calibrated correctness guarantee; the independent Jev study reports calibration differences by primitive, task, and label regime.[84]

### Fixed option semantics and boundedness

Every question must name the alternatives completely and include an escape/uncertainty option when semantically valid, such as `insufficient evidence`, `none of these`, `ask operator`, or `abstain`. `None of these` is not interchangeable with “the proposition is false”; `neutral` is not contradiction; an omitted option may include the true answer outside the model’s choice set. Bound candidate count \(m\le K\), span length \(|e_i|\le L\), branch fan-out \(|\mathcal{Y}|\le B\), and inference attempts \(\le R\) per decision family. These are implementation bounds to select and test, not paper constants.

## 2. Evidence reranking is a ranking problem, not a proof

The following three-class formulation explains SENTLI-style NLI, not the application wire schema. The application F-001 uses the four labels in DECISION_CONTRACTS.md: `supports`, `contradicts`, `irrelevant`, `insufficient`. Map entailment/contradiction to support/contradiction; retain the two neutral subtypes separately and only sum them for explicitly declared three-class comparison metrics. Never ask for three labels and claim the four-label contract was tested.

For a statement `h` and passage \(e_i\), obtain three NLI-style probabilities

\[
(p_i^E,p_i^C,p_i^N)=P(\text{entails},\text{contradicts},\text{neutral}\mid e_i,h),
\quad p_i^E+p_i^C+p_i^N=1.
\]

SENTLI’s method uses non-neutral entailment and contradiction signals to retrieve/rerank spans and balances top evidence from both sides before rerunning NLI.[150] A candidate ordering might be

\[
R_i = \max(p_i^E,p_i^C) \quad\text{(review relevance)},
\]

with two separate ranked lists `sort(p_i^E)` and `sort(p_i^C)`. Alternatively, choose an explicit weighted relevance score
\[
R_i = w_E p_i^E+w_C p_i^C,
\]

but **never** collapse support and contradiction into one polarity; weights should control inspection priority only. Return `(evidence_id, source_id, revision_id, span_id, source_offset, class probabilities, model+schema version)` for every selected item. A deterministic source-status filter is applied before model scoring, but conflicting applicable policies are retained and both support/contradiction candidates are surfaced.

**Critical invariant:** ranking may change the order a reviewer sees evidence. It cannot determine which restrictions get checked. The canonical graph query must enumerate all active applicable restrictions/releases under deterministic tenant, scope, owner, approval, revision, and time predicates. A top-k miss therefore affects search usefulness, not the policy gate’s completeness. The current-policy gate rejects if any applicable restriction remains unresolved or unreleased. Similarity and NLI scores are not signatures, authority, or temporal validity.[32][35]

### Alias suggestions

Given a source name `a` and candidate canonical entity IDs \(C\), ask for \(\mathcal{Y}=C\cup\{\texttt{none}\}\). The model can suggest a merge target; it cannot write the canonical alias/identity edge. Validate with explicit stable IDs, tenant match, relevant attributes and a human/adjudication step. Report false-merge loss separately because the error cost is asymmetric: merge-to-wrong-corridor may contaminate policy scope. Never turn an open-world missing candidate into forced best match.

## 3. Calibration metrics and what each says

Let \(y_i\) be the gold class, \(\hat p_i\) model distribution, and \(\hat y_i=\arg\max_k \hat p_{ik}\). On a labeled evaluation sample of size \(n\), multiclass Brier score is

\[
\operatorname{BS}=\frac1n\sum_{i=1}^n\sum_{k=1}^K(\hat p_{ik}-\mathbf{1}[y_i=k])^2,
\]

and log loss is

\[
\operatorname{LL}=-\frac1n\sum_i \log(\max(\epsilon,\hat p_{i,y_i})).
\]

For binary \(z_i\in\{0,1\}\), \(\operatorname{BS}_{bin}=n^{-1}\sum_i(p_i-z_i)^2\). Clip only for numerical log evaluation; retain and flag malformed probabilities rather than silently normalize invalid provider output. Report proper scores with prevalence and per-family confusion matrix; aggregate scores can hide rare classes and high-cost errors.

Expected calibration error (ECE) for a confidence value \(c_i\) and correctness indicator \(a_i=\mathbf1[\hat y_i=y_i]\), with fixed bins \(B_b\), is

\[
\operatorname{ECE}=\sum_b \frac{|B_b|}{n}\left|\frac{1}{|B_b|}\sum_{i\in B_b}a_i-\frac{1}{|B_b|}\sum_{i\in B_b}c_i\right|.
\]

For Choice, \(c_i=\max_k\hat p_{ik}\); for `noul`, compare predicted yes-probability against empirical yes frequency (and separately assess classification correctness at a threshold). Report reliability diagrams and ECE binning details; ECE depends on binning and class composition and does not imply individual certainty. Guo et al. study temperature scaling as a one-parameter post-hoc calibration method for neural classifiers on their tested datasets; adapting it requires accessible logits and an independent calibration sample, neither of which may exist for hosted System One.[65]

### Different primitives need different checks

- **Choice:** test correctness calibration of max option probability; top-two margin \(m_i=p_{(1)}-p_{(2)}\) is a separate ranking uncertainty feature. A large margin is not sufficient under context attack or out-of-scope options.
- **Binary support/refute:** evaluate each question’s class balance, precision/recall and expected operational cost at the chosen threshold. A single 0.5 threshold can have poor recall or precision under asymmetric prevalence/costs; this is documented in Jev’s benchmark for particular evaluated tasks, not universally.[84]
- **Independent one-vs-rest labels:** label probabilities do not imply exclusivity or a cardinality constraint. If the question is multi-label, evaluate per-class calibration and set-level metrics; do not sum them as if a single distribution.
- **Score:** expected level and confidence concentration are not correctness probabilities unless calibrated against a clearly defined target; report ordinal MAE/exact/adjacent accuracy and weighted kappa if appropriate.
- **Decision confidence field:** check its definition and behavior for each primitive. A vendor-reported confidence derived from peak probability and label count is not an empirical error rate on this fleet.[45]

### Temperature scaling (optional baseline only)

If a backend provides logits \(z_i\) over mutually exclusive options and held-out calibration examples, fit scalar \(T>0\) by minimizing calibration-set NLL:

\[
T^*=\arg\min_{T>0}-\sum_{i\in D_{cal}}\log\operatorname{softmax}(z_i/T)_{y_i}.
\]

Evaluate the frozen \(T^*\) on untouched test data. It preserves argmax for ordinary finite logits, so it may improve probabilistic calibration without changing top-1 class; it cannot fix a wrong class ranking, a missing correct option, data leakage, domain shift, or natural-context redirection. Do not fit and report on the same small held-out set. For independent binary outputs a scalar temperature is applied to binary logits, not the categorical formula; do not retrofit it onto an API that exposes only an opaque score.

## 4. Operational threshold selection under asymmetric costs

For binary predicate `supports` with calibrated \(p=P(z=1\mid x)\), choose `yes` at threshold \(\tau\). Let \(C_{FP}\) be cost of false support and \(C_{FN}\) cost of false non-support. Expected conditional costs are

\[
L(\text{yes}\mid p)=(1-p)C_{FP},\qquad
L(\text{no}\mid p)=p C_{FN}.
\]

If the only choices are yes/no and costs are known, choose yes iff

\[
p>\tau^*=\frac{C_{FP}}{C_{FP}+C_{FN}}.
\]

This is a decision-theoretic derivation, **not** a safety threshold. If false support can hide a valid restriction, set \(C_{FP}\) very high; operationally the deterministic policy verifier should still block unless the verified graph conditions hold. Add an `abstain/review` action with fixed review cost \(C_A\), then choose the minimum expected loss over yes/no/abstain, under the simplifying assumption that review resolves the label without residual error (otherwise include its expected residual loss); in a safety-critical release decision, the preferred mapping is not to ask the model this binary permission question at all.

For multi-class action proposals, a generic expected-risk rule is

\[
a^*(x)=\arg\min_{a\in\mathcal{A}}\sum_y C(a,y)\hat p(y\mid x),
\]

with a reject/review action included explicitly. This optimizes only a declared loss over model labels; it must not override hard eligibility constraints. Exclude unavailable/forbidden actions before the query, and repeat the deterministic checks after selection.

**Tune thresholds on calibration data only.** Choose threshold against predeclared target (e.g. minimum review rate subject to an upper confidence bound on false support), freeze, and report on a temporally/scenario-separated test set. The Jev benchmark’s 1,000-example threshold tuning shows a meaningful protocol pattern but does not validate a threshold for this app.[84]

## 5. Selective prediction: risk versus coverage, with nontrivial edge cases

Let \(s_i\) be a predeclared confidence score (e.g. max probability or a calibrated correctness estimate), and accept a model decision when \(s_i\ge t\). On test data,

\[
\operatorname{Coverage}(t)=\frac1n\sum_i\mathbf1[s_i\ge t],\qquad
\operatorname{Risk}(t)=\frac{\sum_i\mathbf1[s_i\ge t]\mathbf1[\hat y_i\ne y_i]}{\sum_i\mathbf1[s_i\ge t]}.
\]

Also report escalation/review fraction, accepted error by decision family, class, tenant, high-consequence slice, graph-version age, evidence count and language. Plot the risk–coverage curve, not only one threshold. Geifman and El-Yaniv formalize reject-option/risk–coverage selection and finite-sample risk control for a fixed classifier under their assumptions; those results do not transfer automatically to distribution shift or a dynamically changing fleet.[66]

**Edge cases to state explicitly:**
1. If no cases pass, coverage is zero and selective risk is undefined; report `NA, n_accept=0`, not zero risk.
2. If one or a few cases pass, risk estimate has wide uncertainty; always show numerator, denominator, and a binomial confidence interval.
3. Ties at threshold, equal confidence and threshold selection must have deterministic, predeclared rules.
4. Risk is conditional on accepted cases and may conceal an unsafe **rejected** case that the fallback mishandles. Report fallback and end-to-end episode risk separately.
5. Overall coverage can look high while rare authorization-sensitive categories have near-zero coverage or high risk; report family/class/slice metrics and worst-case observed slices.
6. Threshold search over many candidate cutoffs on the test set leaks labels. Use training/calibration/validation/test separation or a method with the corresponding multiple-selection guarantee.
7. A scalar confidence may order errors poorly; a low AURC/risk curve is empirical, not a per-case bound. Calibration and discrimination (AUROC) measure different properties.
8. Every model, question schema, evidence projection, option order, corpus revision and fallback change potentially changes the score distribution; recalibrate/revalidate.
9. Counts across frames/steps within an episode are correlated. Cluster by task/scenario/episode for uncertainty intervals, not by individual frame.

## 6. Conformal prediction and “ask for clarification” semantics

For a fixed classifier distribution \(p(y\mid x)\), one standard nonconformity score is

\[
a(x,y)=1-p(y\mid x).
\]

Given \(n\) exchangeable calibration examples \((x_i,y_i)\), sort \(a_i=a(x_i,y_i)\) and set \(q=a_{(k)}\), where \(k=\lceil(n+1)(1-\alpha)\rceil\) (if \(k>n\), use \(q=+\infty\)). The prediction set is

\[
\Gamma_\alpha(x)=\{y\in\mathcal{Y}:1-p(y\mid x)\le q\}.
\]

Under exchangeability and the specified split-conformal construction, marginal coverage is at least \(1-\alpha\) (finite-sample rank details as above). This is a statement about **set inclusion over the target distribution**, not “each label probability is accurate,” not class-conditional coverage in general, and not safety under domain shift. KnowNo uses this idea to ask for help when more than one plan remains; its sequence-level treatment is specifically motivated by feedback-dependent contexts that violate naive independent-step calibration.[152]

A robotics clarification policy may say: if \(|\Gamma|=1\), propose its plan for deterministic gates; if \(|\Gamma|>1\), ask a supervisor to resolve ambiguity; if the correct choice is absent from a set with an explicit `other` possibility, stop or request free-form clarification. But the **marginal set coverage guarantee does not by itself prove that the singleton-accepted subset has conditional error ≤ α**. Selective risk on singleton cases must be measured or controlled separately. Task-level success further requires that the human’s answer is correct, the option set includes a safe choice, and subsequent steps satisfy their own physical and policy checks. KnowNo’s paper argument makes assumptions about accurate help and calibrated scenarios; carry those conditions openly.[152]

### Multi-step and adaptive episodes

If there are \(H\) decisions and each has a valid marginal failure bound \(\alpha_h\) under applicable conditions, a union bound gives \(P(\text{any failure})\le\sum_{h=1}^H\alpha_h\). This can be loose, and per-step guarantees need not apply after adaptive feedback changes the state distribution. Do not reuse a one-step CP quantile over an interactive rollout and assert the same bound. Either calibrate at the episode/sequence level (as KnowNo proposes) with exchangeable episode sampling, or report empirical episode outcomes without a formal claim.[152]

## 7. Escalation and value of computation

Let `L` be loss for an incorrect accepted advisory classification (not authorization), `c_e` the direct fallback cost, and \(\Delta t\) its added latency cost expressed in the same utility units. Given state \(x\), suppose the current decision’s probability correct is \(q_1(x)\), and after a specific fallback it is \(q_2(x)\). The expected net value of escalating rather than accepting is

\[
\operatorname{VoC}(x)=L\,[q_2(x)-q_1(x)]-c_e-\lambda\Delta t- c_{queue}(x),
\]

where \(\lambda\) converts latency into cost and \(c_{queue}\) captures queue/resource externalities. Escalate only when estimated VoC is positive and the bounded request budget permits it; otherwise accept only if selective rules pass or abstain/review. When the downstream loss is unbounded/high-consequence or unknown, do **not** trust a learned VoC router: deterministic gates / human review should dominate.

This one-step expression is a myopic approximation: it compares one escalation with immediate acceptance and assumes calibrated conditional quality estimates, fixed or measurable costs, and no important option value from subsequent computation. Hansen and Zilberstein’s anytime-algorithm framework models metalevel control as a sequential dynamic program and includes uncertain progress/domain state and monitoring cost; importing that method would require estimating the task-specific performance and state-transition model, not simply substituting a confidence threshold.[165] Until those ingredients are validated, use a bounded one-fallback policy and compare its measured cost/quality curve instead of claiming optimal routing.

For binary actions with current probability \(q_1\) and fallback probability \(q_2\), this simple value model assumes the fallback’s correctness estimates are calibrated conditional on the same evidence and decision family, with both qualities measured on the actual routed subset. Error independence is not mathematically required for this expected-loss difference, but correlated context errors can eliminate the expected improvement and invalidate an unconditioned estimate. JevOut makes context stability testing essential; REFLEX’s limited advantage over a cheap cascade in some external settings warns against presuming a separate decision model saves calls when baseline routing is already easy.[85][156]

A two-stage cascade can be written as

\[
\pi(x)=\begin{cases}
\text{accept cheap decision}, & s(x)\ge t \land G(x)=\text{eligible},\\
\text{fallback once}, & s(x)<t \land G(x)=\text{eligible for advisory},\\
\text{stop/review}, & G(x)\in\{\text{blocked},\text{unknown}\}\text{ or technical error},
\end{cases}
\]

where \(G\) is a deterministic graph/policy/physical gate. No model output may flip `blocked`/`unknown` into `eligible`. The retried/escalated route has a hard cap (e.g., a single fallback attempt; exact value chosen by project), deadline and idempotency token. On timeout/invalid response, there is no implicit retry-as-success.

### Cost and latency accounting

Measure end-to-end, not just model latency:

\[
C_{episode}=C_{graph}+C_{projection}+C_{model}+C_{fallback}+C_{review}+C_{retry},
\]

\[
T_{episode}=T_{queue}+T_{graph}+T_{model}+T_{fallback}+T_{review}+T_{controller}+T_{observation}.
\]

The displayed time sum is a sequential accounting approximation. With overlapping services, measure actual wall-clock critical-path latency instead of summing overlapping durations.

Report p50/p95/p99 by decision and whole episode, model/fallback call counts, retries/refusals/timeouts, token/request billing at observed rates, review minutes, and quality at matched information. Include model/adapter overhead and stale-check recomputation. RouteLLM and FrugalGPT show how routing/cascades can be framed against a cost-performance budget, but their reported savings are not portable to this graph/robot setting.[153][154]

## 8. Metrics ledger for agent implementation

| Metric | Definition / denominator | Why keep it |
|---|---|---|
| Accepted coverage | Model-accepted eligible decisions / all eligible advisory decisions | Quantifies how much model advice is used rather than fallback. |
| Selective risk | Incorrect accepted advice / accepted decisions; report numerator/denominator/interval | Makes coverage–error tradeoff visible; never conflate with action safety. |
| Mandatory-gate violations | Number of executed attempts when deterministic precondition/gate denied or unknown | Must be exactly zero in the test harness; finite zero is not proof of universal safety. |
| Support precision/recall | NLI `supports` adjudication per atomic claim, with false support emphasized | Measures evidence usefulness; report contradiction recall too. |
| Candidate recall@K | Relevant supporting/contradicting gold spans in retrieved candidates | Separates first-stage graph retrieval misses from reranker errors. |
| Evidence traceability | Decisions with immutable source+revision+span IDs and valid offsets / decisions | A semantic label without auditable evidence is not a corpus answer. |
| Conformal coverage / set size | Gold option in set / examples; average set size and singleton coverage | Do not report only the nominal target; also distinguish singleton selective risk. |
| Alias false-merge rate | Incorrect committed entity links / all accepted suggestions; weighted cost | False merge is more dangerous than `none`. Canonical commits should require independent review. |
| Escalation utility | Correctness uplift vs extra model+review+latency cost per episode | Tests whether a fallback earns its cost rather than just raising token count. |
| Model-use efficiency | Fallback/generative calls and dollars per successfully resolved incident | Direct test of routing benefit against deterministic and generative-only baselines. |
| Context sensitivity | Fraction of matched answer-preserving context/order perturbations changing output; high-confidence subset | Exposes JevOut-style instability and option-order artifacts. |
| End-to-end mission outcomes | Verified completion, premature resume, blocked-correctly, deadlock, time, observation/travel cost | Connects decision utility to the actual task; do not let controller interlock hide unsafe intent. |
| Technical availability | Invalid/refused/unavailable/timeout, retry and stale-version rejection rates | Defines fail-closed behavior and operational burden. |

## 9. Minimal statistical reporting protocol

1. Freeze question schema, prompt/rubric, model version, graph projection/query, candidate-generation policy, labels, fallback, timeout, and acceptance rule before final test.
2. Partition by incident family, simulator seed, source revision, and episode. Keep paraphrases/frames of one incident in one partition; reserve an untouched test set.
3. Fit any probability calibration and threshold on calibration data only; choose policy/threshold on validation; report once on test. If data are scarce, use nested/clustered resampling and say uncertainty is large.
4. Compute calibration, selective, ranking, cost and latency statistics per question family. Use paired scenario-level bootstrap or exact paired tests where appropriate. Avoid treating 100 correlated steps as 100 independent incidents.
5. Report all failures, including omitted true choices, unavailable provider, wrong alias, stale graph version, unauthorized plan proposals, and fallback errors. Never average away mandatory-gate violations.
6. Compare deterministic graph baseline, optional NLI reranker, System One, generative-only, and selective System One+fallback. Same candidates/evidence/options and same deadline. Include ablations for graph grounding, contradiction retrieval, abstention, and gates.
7. Treat results from papers as method evidence and motivation only. There is no existing project benchmark result to insert into tables.

## 10. Decision rules and failure behavior in one place

- If the exact source/revision/approval/currentness graph witness is absent: model can say `insufficient`, but deterministic result is `blocked/unknown`.
- If an active applicable restriction remains without a valid release: keep courier stopped; evidence reranking cannot erase it.
- If retrieved spans conflict: retain both and surface them; route to operator if deterministic policy cannot resolve priority/temporal scope.
- If model chooses an ineligible option, gives malformed probabilities, refuses, times out, exceeds deadline, or sees stale graph/input versions: discard response, log status, use bounded deterministic fallback/review.
- If an alias is uncertain: return `none`/human review, never merge.
- If confidence is high but context perturbation or adversarial check fails: disable the model-accept route for that family pending mitigation and retest.
- If model benefit is not better than deterministic ranking/branch selection at matched quality and total cost: remove it from the live path; retain only as an optional research tool.
- Regardless of model class or conformal set: physical clearance, task claim, current authorization and controller interlocks must pass independently at dispatch.

<!-- GENERATED CITATION REFERENCES -->

## Sources

[32] https://docs.falkordb.com/graphrag/architecture.md — GraphRAG SDK Pipeline Architecture
[35] https://docs.falkordb.com/graphrag/reliability-and-grounding.md — Reliability and Grounding
[45] https://docs.typesafe.ai/confidence.md — Confidence
[65] https://arxiv.org/html/1706.04599v2 — On Calibration of Modern Neural Networks
[66] https://arxiv.org/html/1705.08500v2 — Selective Classification for Deep Neural Networks
[84] https://arxiv.org/html/2609.37647v1 — Evaluating and Benchmarking the System One Model Jev
[85] https://arxiv.org/html/2609.30243v2 — JevOut: Natural Context Can Flip Decision Models
[150] https://arxiv.org/html/2204.07447v2 — Stretching Sentence-pair NLI Models to Reason over Long Documents and Clusters (SENTLI)
[152] https://proceedings.mlr.press/v229/ren23a.html — Robots That Ask For Help: Uncertainty Alignment for Large Language Model Planners (KnowNo)
[153] https://arxiv.org/html/2406.18665v4 — RouteLLM: Learning to Route LLMs from Preference Data
[154] https://arxiv.org/pdf/2305.05176 — FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance
[156] https://arxiv.org/html/2609.26532v1 — REFLEX with Jev for Efficient Selective Control in LLM Agents
[165] https://www.sciencedirect.com/science/article/pii/0004370200000680 — Monitoring and control of anytime algorithms: A dynamic programming approach
