# Mathematics and research-to-code map

**Design mathematics, not measured fleet performance.** Symbols define implementable contracts. Paper-specific mechanisms and our adaptations are distinguished in RESEARCH.md and RESEARCH_SYSTEM_ONE.md.

| File | Contents | Intended code/test owner |
|---|---|---|
| [Robotics and planning](math/ROBOTICS.md) | Scoped clearance, three-valued evidence, dependency frontier, eligible matching, information gathering | domain / planning / simulator |
| [System One](math/SYSTEM_ONE.md) | NLI ranking, calibration, asymmetric loss, risk/coverage, conformal sets, value of computation, cost | decisions / eval |
| [Temporal authority and coordination](math/GRAPH_AUTHORITY.md) | Validity intervals, permission conjunction, witness completeness, claims/fencing, event identities | graph / policy / runtime |
| [Statistics and worked examples](math/STATISTICS.md) | Ranking metrics, paired episodes, uncertainty, zero-failure bounds, synthetic worked examples | eval / test oracles |

Use one notation owner per concept: `policy_epoch` is governance version; `question_schema_version` is the model question version; `world_tick` is simulation time. A mathematical probability is not authorization. A graph relation is not evidence unless it has valid provenance and role semantics. A finite test with no violation is not a universal safety proof.

Implementation sequence: write a failing test for each equation's boundary cases (empty sets, ties, zero denominator, incompatible scope, malformed probability, stale time, duplicate event, missing relation) before production code. Keep numeric constants configured with units and label whether synthetic assumption, measured estimate or calibrated parameter.
