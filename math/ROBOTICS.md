# Robotics mathematics and planning adaptation

**Proposed independent implementation inspired by research; no paper reproduced.**

## 1. Separate physical state, observation and belief

Let world state be $x_t$ (simulator/evaluator only), robot pose $r_t$, action $a_t$, and observation $o_t \sim O(x_t,r_t,a_{t-1})$. The policy receives $o_t$ and a declared static map prior, never full $x_t$. Its evidence state $E_t$ contains observations with timestamps, scope and provenance. Hypotheses $H_t$ and predicted effects $\hat{x}_{t+1}$ are not observations.

For predicate $p$, use $V(p,E_t)\in\{\mathrm{true},\mathrm{false},\mathrm{unknown}\}$. True requires fresh sufficient supporting evidence for the intended actor/action scope; false requires sufficient contrary evidence; missing, stale, occluded or unresolved contradictory inputs yield unknown. This is a declared rule system, not a solved POMDP.

VAP-TAMP motivates precondition/action/postcondition observation and active viewpoints; HUME motivates explicit hypotheses and refutation. Our concurrent adaptation refuses to publish predicted effects as shared observed truth and refuses unverified optimistic assumptions.[100][101]

## 2. Scoped geometric clearance

For a corridor passage with measured gap interval $[g^-_t,g^+_t]$, robot effective width $w_r(\ell)$ conditioned on load $\ell$, and per-side margin $m_r$, a conservative necessary lateral condition is:

$$g^-_t\ge w_r(\ell)+2m_r.$$

This is only a necessary simplified condition: curvature, orientation, swept volume, dynamics, floor hazards and visibility can still block travel. Full planned path $\gamma$ needs the relevant swept robot shape to remain within observed free space plus uncertainty constraints. Scout clearance cannot be substituted for courier clearance.

Synthetic worked arithmetic (computed, not measured): gap estimate 1.10 m with lower-bound uncertainty 0.05 m gives 1.05 m; courier width 0.90 m plus 0.10 m each side requires 1.10 m. The necessary test fails. Values are scenario examples, not real robot measurements. See `../evidence/math-worked-examples.json`.

## 3. Preconditions and outcomes

For skill $a$, let $P_a$ be required preconditions and $Q_a$ required postconditions. Admission requires $\bigwedge_{p\in P_a}[V(p,E_t)=\mathrm{true}]$ plus the policy/task/resource gate. Controller completion only changes receipt state. Task success requires fresh post-action evidence $E_{t'}$ with $t'>t_{start}$ and $\bigwedge_{q\in Q_a}[V(q,E_{t'})=\mathrm{true}]$.

If a condition becomes stale/refuted, invalidate all tasks depending on it via graph traversal. Keep original evidence/refutation history. Model agreement on differently phrased questions does not create independent sensory evidence.

## 4. Task DAG and ready frontier

Let $D=(T,\mathcal{E})$ where $(u,v)\in\mathcal{E}$ means task $u$ depends on prerequisite $v$, matching `Task-DEPENDS_ON->Task`. Reject cycles before scheduling. At time $t$:

$$F_t=\{u\in T: state(u)=pending,\ \forall v\in deps(u), verified(v),\ \forall p\in req(u),V(p,E_t)=true\}.$$

Operational permission and resource readiness further filter proposals. A DAG edge absent does not mean two tasks may share a corridor/workspace concurrently.

## 5. Capability-aware assignment

For robots $R$ and ready tasks $F$, determine eligible pairs $A\subseteq R\times F$ from capabilities, route, load, policy and reservations. Decision variable $z_{ru}\in\{0,1\}$ exists only for eligible pairs.

$$\max_z\sum_{(r,u)\in A}w_{ru}z_{ru},\qquad \sum_u z_{ru}\le1,\quad\sum_r z_{ru}\le1.$$

Use explicit dummy wait/unassigned options and a documented tie-break. Never give an ineligible pair weight zero while allowing it to be selected. An empty feasible set means wait/inspect/escalate, not round-robin fallback. Costs/weights may include priority, estimated route length and observation cost with normalized units; do not call it global time-optimal scheduling.

LiP-LLM supplies ready-frontier weighted assignment; it did not model task execution time and left stronger feedback replanning for future work. Our durations, resource claims and recovery are extensions.[105] KGLAMP and RobotFleet already cover close graph/capability/centralized orchestration ideas, so this is not a novelty claim.[86][148]

## 6. Routing and resource safety

Given robot-eligible graph edges $E_r$ retrieved from FalkorDB, solve $\gamma^*=\arg\min_{\gamma}\sum_{e\in\gamma}c_e$ using nonnegative costs and deterministic ties. Adjacency is a bounded query result with a graph/policy version, not a second authoritative world graph. Revalidate on relevant change.

Shortest path does not solve multi-robot collision-free motion. For first build reserve narrow corridor/workspace resources, validate entry/exit and use local collision/stop envelopes. Higher-throughput time-expanded multi-agent planning is deferred. A learned graph CBF and its formal assumptions are a different layer, not inherited by using graph-shaped data.[89]

## 7. Bounded evidence gathering

For unresolved hypotheses, candidate inspection action $a$ has allowed set membership, expected information value and cost. An ideal score might be:

$$U(a)=\mathbb{E}[H(b_t)-H(b_{t+1})\mid a]-\lambda C(a),$$

where $b_t$ is a calibrated belief distribution and $H$ entropy. **The first build does not have such a calibrated belief model.** Use a transparent deterministic heuristic (missing prerequisite coverage, visible region, travel cost) or bounded System One priority among already eligible actions. Label the entropy formula conceptual unless probabilities and observation model are fitted/tested.

Proposed default budget: two additional viewpoints and two recovery attempts, then unresolved hold. Compare against a competent equal-budget active-inspection baseline. Conformal help-seeking is optional, not a shortcut from confidence to permission.

## 8. Memory applicability

A procedure from episode $e$ is a candidate only if verified(e), robot capability/configuration match, map/hazard compatibility and current authority checks hold. Formally $Applicable(e,s)=Verified(e)\land Compatible(e,s)\land RegroundedPreconditions(s)$. Similarity ranks episodes after this gate; a past success cannot replace current verification. This is typed plan reuse, not motor-skill transfer.[118][135]

## 9. Test translation

Tests must cover gap equality and negative/NaN dimensions, unknown/contradictory evidence, expiry exactly at boundary, out-of-order observations, DAG cycles, infeasible pairs, all-wait assignments, resource conflict, failed effects, reintroduced obstruction and incompatible procedure. Use property-based tests for monotonic safety: adding an applicable prohibition cannot turn DENY into ALLOW; increasing robot width cannot improve clearance under fixed evidence.

<!-- GENERATED CITATION REFERENCES -->

## Sources

[86] https://arxiv.org/html/2602.04129v2
[89] https://arxiv.org/html/2401.14554v4
[100] https://arxiv.org/html/2604.26988v1
[101] https://arxiv.org/html/2607.06501v1
[105] https://arxiv.org/html/2410.21040v1
[118] https://arxiv.org/html/2407.04363v3
[135] https://arxiv.org/html/2303.11366v4
[148] https://arxiv.org/html/2510.10379v1
