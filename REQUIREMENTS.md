# Requirements and traceability

**All requirements are PLANNED.** Test names and commands are target contracts, not existing implementations. P0 defines complete product; P1 defines the measured model enhancement; P2 is explicitly deferred. Requirement status may change only with a commit and actual evidence artifact.

## Product and system requirements

| ID | Priority | Requirement / acceptance oracle | Planned test path | Implementation gate |
|---|---|---|---|---|
| R-001 | P0 | FalkorDB query results change assignment/action; graph outage blocks new coordinated dispatch | `tests/integration/test_graph_causality.py` | G03 |
| R-002 | P0 | One original MuJoCo world, one step owner, three named robot bodies with different capabilities | `tests/simulation/test_world.py` | G02 |
| R-003 | P0 | Policy receives only declared observations; evaluator truth unavailable to policy process | `tests/adversarial/test_oracle_isolation.py` | G02 |
| R-004 | P0 | Observation records include pose/frame/tick, scope, source, quality and expiry; out-of-order input preserves event time | `tests/unit/test_observations.py` | G01 |
| R-005 | P0 | Predicted effects/hypotheses never become observations; refuted hypotheses remain linked to evidence | `tests/unit/test_hypotheses.py` | G03 |
| R-006 | P0 | Precondition/action/postcondition loop; completion ack alone cannot finish recovery | `tests/simulation/test_verify_effects.py` | G04 |
| R-007 | P0 | Traversability conditioned on robot footprint, payload and current observation; scout passage is not courier clearance | `tests/simulation/test_clearance.py` | G04 |
| R-008 | P0 | Missing/occluded evidence produces unknown, bounded inspection or unresolved hold | `tests/simulation/test_inspection_budget.py` | G04 |
| R-009 | P0 | Task DAG rejects cycles; ready frontier excludes unmet dependencies and invalidated facts | `tests/unit/test_frontier.py` | G03 |
| R-010 | P0 | Assignment excludes infeasible capability/route/policy pairs; empty matching waits rather than unsafe fallback | `tests/unit/test_assignment.py` | G05 |
| R-011 | P0 | Task/resource claim transition has one winner and increasing fences in synchronized multi-client tests | `tests/integration/test_claim_race.py` | G05 |
| R-012 | P0 | Simulator rejects stale fences and duplicate command IDs with mismatched payloads | `tests/contract/test_command_protocol.py` | G05 |
| R-013 | P0 | Coordinator restart reconciles command outcome instead of repeating ambiguous effects | `tests/integration/test_restart_reconcile.py` | G07 |
| R-014 | P0 | DB process restart, container recreation and backup restore tested independently with committed source/graph receipts | `tests/integration/test_durability.py` | G07 |
| R-015 | P0 | Verified episode retrieval changes a later investigation; incompatible procedure held/rejected | `tests/integration/test_episode_reuse.py` | G07 |
| R-016 | P0 | Actual file ingestion retains immutable normalized text and byte hash; exact source spans validate | `tests/unit/test_source_spans.py` | G06 |
| R-017 | P0 | Canonical graph returns source/revision/span/decision/owner/restriction connected witness in one bounded query | `tests/integration/test_policy_witness.py` | G06 |
| R-018 | P0 | Authority, scope, approval, effective interval and explicit supersession determine policy; newer chat cannot overrule | `tests/unit/test_policy_precedence.py` | G06 |
| R-019 | P0 | Every applicable current restriction is evaluated independently of semantic top-k | `tests/adversarial/test_hidden_restriction.py` | G06 |
| R-020 | P0 | Physical clearance cannot override restriction; authorized release still requires fresh physical checks | `tests/e2e/test_clear_but_forbidden.py` | G06 |
| R-021 | P0 | Scoped recovery allowed only where explicit permission exists; blanket ban stops all agents | `tests/e2e/test_blanket_ban.py` | G06 |
| R-022 | P0 | Policy tick domain and durable outbox order are explicit; policy changes invalidate stale plans/receipts; gaps, late revocations and in-flight effects hold/reconcile | `tests/integration/test_policy_race.py` | G06 |
| R-023 | P0 | Tenant graph keys + roles enforce isolation; same labels/IDs in another tenant never affect query, cache or egress | `tests/integration/test_tenant_acl.py` | G01/G09 |
| R-024 | P0 | SDK maps synthetic rows and retrieves candidates in separate corpus graph; contract tested on pin, failure disclosed | `tests/contract/test_sdk_pipeline.py` | G08 |
| R-025 | P0 | Corpus update/delete/merge cannot erase canonical history, affect ops or bypass validation | `tests/adversarial/test_corpus_boundary.py` | G08 |
| R-026 | P0 | Typed model adapter preserves raw probabilities/status/version/usage; malformed/late/refused responses rejected | `tests/contract/test_decision_providers.py` | G08 |
| R-027 | P1 | Evidence classification/reranking evaluated on held-out atomic claims using fixed candidate sets | `tests/evaluation/test_rerank_eval.py` | G08 |
| R-028 | P1 | Per-family calibration/abstention thresholds fitted without test leakage; zero accepted gives undefined risk, not success | `tests/unit/test_metrics.py` | G08 |
| R-029 | P1 | Model comparison includes deterministic and structured-generator baseline; actual cost, retries and latency | `tests/evaluation/test_comparison_manifest.py` | G08 |
| R-030 | P1 | Optional permissible investigation selection improves declared metric or remains disabled | `tests/evaluation/test_investigation_eval.py` | G08 |
| R-031 | P0 | Dashboard displays real API/SSE state, witness, reasons, distinct ack/effect status and explicit approval | `web/tests/operator.spec.ts` | G04/G06/G09 |
| R-032 | P0 | UI supports keyboard, non-color statuses, reduced motion, stale connection indicators | `web/tests/accessibility.spec.ts` | G09 |
| R-033 | P0 | Raw episode trace includes intents AND executed outcomes, graph versions, seeds and reproducible evidence | `tests/evaluation/test_trace_schema.py` | G04/G09 |
| R-034 | P0 | Model/graph/simulator outages cause conservative bounded behavior, never fabricated success | `tests/e2e/test_outage_matrix.py` | G09 |
| R-035 | P0 | Local skill watchdog and stop/hold remain independent of cloud/graph; no arbitrary generated code execution | `tests/simulation/test_watchdog.py` | G02/G04 |
| R-036 | P0 | Baselines receive identical observations, policy corpus, resources and action budgets | `tests/evaluation/test_no_privileged_baseline.py` | G09 |
| R-037 | P0 | Prompt injection, plausible irrelevant context, negation, alias collisions, stale revisions and choice permutations tested | `tests/adversarial/test_semantic_robustness.py` | G08/G09 |
| R-038 | P0 | Fresh extraction/setup works and demo records real tests/actions; all AI/reuse/licenses disclosed | `tests/e2e/test_clean_setup.py` | G10 |

## Nonfunctional targets

These are engineering targets, not measured service levels. Document any negotiated change before the final benchmark.

- **Reproducibility:** fixed seed/config/asset/dependency hashes and persisted action traces; distinguish action replay from reseeding an unrecorded run.
- **Correctness:** no unauthorized executed action in the finite required suite; report counts/denominators and unsafe intents even when local controls prevented execution.
- **Latency:** no network/LLM waits inside the physics-step loop. Decision stage has a configurable bounded deadline; measure p50/p95/p99 by stage before choosing a user-facing latency claim.
- **Durability:** acknowledged critical transitions survive the explicitly chosen persistence profile; commands with ambiguous physical outcomes stay unresolved. No untested zero-loss promise.
- **Privacy:** public/synthetic source allowlist only; sanitized logging; no private connection details in exports; no raw state in exception text.
- **Maintainability:** locked compatible environments, static types, typed contracts, narrow query/tool surfaces, independent review for boundary changes.
- **Portability:** macOS Apple Silicon is primary dev target, clean Linux/headless judge setup is separately tested before being advertised.

## Deferred requirements register

| ID | Deferred feature | Gate before promotion |
|---|---|---|
| D-001 | Graphiti temporal retrieval | Full P0 plus retrieval ablation demonstrating benefit |
| D-002 | Docling/PDF provenance | Real PDF use case and model/asset license audit |
| D-003 | LangGraph checkpoints / OPA | State machine/policy complexity demonstrably needs them; no duplicate authority |
| D-004 | Alias alignment / learned memory relevance | False-merge and applicability evaluation; no destructive merges |
| D-005 | Conformal clarification sets | Independent calibration data, assumptions and shift analysis |
| D-006 | VLM/image perception / Co-GLANCE distillation | Separate sensor benchmark, licensing/compute and oracle isolation |
| D-007 | Hardware / ROS / Open-RMF | Explicit user authorization, supervised safety plan, separate commissioning |
| D-008 | CCH/A*/GRAPH.COPY branches | Pinned runtime capability test and measured bottleneck |
| D-009 | Local Laya/Strands/H2O/AnyJev | Exact weights/licenses/host smoke tests and fair cost accounting |
| D-010 | T²Mem/VLA/RL/learned CBF | Separate research project; no claimed inherited safety guarantee |

## Status update format

For each requirement record `status`, `implementation_commit`, `test_command`, `artifact_path`, `result`, `limitations`. Allowed status: planned → implemented → tested → measured (where relevant) → demo-recorded. A model-free fallback does not satisfy SDK integration or measured-model requirements. A failed test may be blocked/deferred only with a visible reason and approved scope change.
