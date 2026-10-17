# Evaluation statistics and computed synthetic examples

These examples are **illustrative arithmetic**, computed in Python and saved in `../evidence/math-worked-examples.json`. They are not inference outputs, simulation data or performance measurements.

## 1. Calibration example

Binary predictions $p=(0.9,0.6,0.2,0.8)$ and gold labels $y=(1,0,0,1)$ give $BS=\frac14\sum_i(p_i-y_i)^2=0.1125$. This only demonstrates the formula. Multiclass Brier uses sum over all class probabilities and has a different scaling; report which convention is used.

Log loss clipping is a numeric reporting convention; preserve original zeros and invalid values. Empty evaluation data must fail before network calls or report no data, not a fabricated metric. Empty confidence bins are omitted from bin means. At zero accepted predictions, coverage is zero and selective risk is **undefined**, never zero.

## 2. Ranking metrics

For candidate relevance grades $rel_i$, $DCG@k=\sum_{i=1}^{k}(2^{rel_i}-1)/\log_2(i+1)$ and $nDCG=DCG/IDCG$. If IDCG is zero, report undefined/no relevant labels and a separate no-evidence accuracy, not arbitrary perfect ranking. MRR uses reciprocal rank of first relevant candidate; misses contribute zero. Report support and contradiction recall separately, because a combined relevance metric can hide missed contradictions.

Candidate recall assesses retrieval before reranking. A reranker cannot recover a gold span absent from candidates. Mandatory policy completeness is assessed over the entire applicable rule set, not nDCG@k.

## 3. Paired experiment design

Use the same incident seeds/configurations, source revisions, observation budget and permitted actions across variants. Group related templates/paraphrases/frames in the same split. Preserve temporal holdouts and scenario-family holdouts separately where feasible. Fallback/model/dependency versions and option order protocol are frozen before final testing.

Bootstrap independent **episodes/groups**, not correlated frames, for paired differences in completion, cost and latency. Report raw numerators, denominators, number of independent groups, exclusions and uncertainty. A threshold selected on test labels invalidates the claimed holdout.

## 4. Zero failures does not mean zero risk

For $n$ independent identically distributed Bernoulli trials with zero failures, the one-sided confidence bound at $1-\alpha$ solves $(1-p)^n=\alpha$, giving $p_{upper}=1-\alpha^{1/n}$.

Computed illustration: zero failures among 100 independent trials gives a 95% one-sided upper bound of about **2.9513%**, not 0%. The independent/common-distribution assumption is not automatically true of scripted fixtures or repeated frames. Do not apply this bound to 100 near-identical steps and claim robot safety.

## 5. Cost and value-of-computation example

If advisory correctness were calibrated at $q_{fast}=0.80$ and a particular fallback at $q_{fallback}=0.94$, wrong-label loss were 1 unit, extra compute 0.04 units and delay 0.02 units, the simple net value is $(0.94-0.80)-0.04-0.02=0.08$ units. These invented **example inputs** only illustrate the equation; neither model's correctness is known here.

Conditional quality estimates must be measured, and a fallback can share the same error. Include provider failures, retries, queueing, review and stale recomputation. Cost per success divides actual total cost by verified successful incidents; zero successes makes the ratio undefined/infinite with counts, not zero.

## 6. Robustness denominators

Ordinary perturbation flip rate: changed predictions / all independently gold-preserving paired items. Targeted attack success: at least one fixed-target flip among initially correct items under a declared search budget. These are different denominators and tasks; JevOut's optimized targeted success is not normal traffic error prevalence.[85]

For choice rotations, map labels back to the same semantic ID before comparing. Include missing correct option, repeated-call variance and high-confidence wrong fraction. An abstention is not necessarily a failure; evaluate its downstream review cost and whether fallback resolves the incident.

## 7. Acceptance decisions

Predeclare one primary improvement objective (evidence ranking or cost at non-inferior accepted error) and hard invariant blockers. Report all secondary slices, including rare false support and contradictory restrictions. Do not retain a model just because aggregate accuracy improves while a hard gate becomes bypassable. Results with too little data support “inconclusive”, not a forced winner.

<!-- GENERATED CITATION REFERENCES -->

## Sources

[85] https://arxiv.org/html/2609.30243v2 — JevOut: Natural Context Can Flip Decision Models
