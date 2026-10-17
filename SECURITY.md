> Contract alignment: RUNTIME.md owns durable lease clocks, command state names, policy propagation ordering and local synthetic approval. REQUIREMENTS.md owns requirement IDs; this document owns EV/INV/FM identifiers. All test paths are proposed.

# Witness Fleet Security Specification (Proposed)

**Status:** design requirements and test oracles only. These invariants are proposed, not implemented or verified. No live security tests or external model calls were performed. Use synthetic/public/owned data only; never load restricted company documents, personal data, secrets, or credentials for the demo.

## 1. Security boundary and protected assets

Witness Fleet is a simulation-first, three-robot coordinator (scout, recovery robot, loaded courier) with one authoritative MuJoCo physics owner. The policy/control path may see only declared sensor observations, validated operational graph state, approved policy records, and bounded model candidate output. Simulator truth, evaluator labels, privileged overlays, and hidden annotations are outside the policy boundary.

Protected assets:

- Integrity of current restriction/release, owner, source revision/span, observation, task, claim, command, and outcome records.
- Availability and integrity of the canonical tenant operations graph `wf:<tenant>:ops`.
- Confidentiality and integrity of the isolated optional corpus graph `wf:<tenant>:corpus` and any source bytes.
- Tenant-scoped graph access, model egress control, command/action integrity, audit history, and safe stop/hold behavior.

Trust boundaries: (1) robot sensor adapter ↔ coordinator; (2) coordinator ↔ FalkorDB ops graph; (3) optional GraphRAG-SDK ↔ tenant corpus graph; (4) external System One provider; (5) simulator evaluator/visualization ↔ policy process; and (6) human/operator approvals ↔ policy ingestion. Corpus text, retrieved passages, model outputs, aliases, and controller acknowledgements are untrusted inputs.

## 2. Invariants (all are proposed)

### INV-001 — Hidden simulator truth is evaluator-only

Policy, planner, model prompt builder, UI control API, and graph ingestion cannot read simulator-only geometry/state, evaluator outcomes, scenario labels, hidden collision flags, or display annotations. A single physics owner advances MuJoCo; read-only sensors expose only permitted observations. The deterministic planar adapter is limited to unit tests and is not evidence of primary simulator integration. Security/evaluation gate: `EV-001`.

### INV-002 — Explicit evidence classes and freshness

Observation, hypothesis, predicted effect, approved policy, action acknowledgement, and verified outcome are distinct types/records. Predictions and acknowledgements never satisfy sensor postconditions. Evidence includes source, actor/robot, event time (`world_tick`), recorded time, quality, frame, predicate, scope, and configured expiry. Real monotonic time controls process-local deadlines; durable leases use the coordinator-epoch/UTC protocol in RUNTIME.md; simulator time controls observation event order. Future timestamps, stale readings, out-of-order updates, or scope mismatch cannot authorize actions.

### INV-003 — Policy scope and precedence are deterministic

Authorization is a deterministic function of all current restrictions applicable to corridor, action, robot class, payload, task, site, and effective interval. A deny dominates an allow. Scoped permission for inspector/recovery permits only the named scope and does not override another applicable blanket ban. A blanket no-entry restriction blocks recovery as well as courier. A release is valid only if explicitly approved by an authorized principal, effective now, in scope, and linked via `LIFTS` to the targeted restriction. It cannot erase a different restriction. Physical clearance and policy permission are independent necessary predicates. Newest timestamp, retrieval rank, similarity, or model confidence is not policy precedence. Missing authority or unresolved contradiction means hold/needs approval.

### INV-004 — Canonical graph is the authority witness

The authoritative source-to-action proof is traversable entirely within the same canonical ops graph: `Decision-IMPOSES->Restriction-APPLIES_TO->Corridor`, `Decision-OWNED_BY->Owner`, `Decision-SUPPORTED_BY->EvidenceSpan-IN_REVISION->Revision-REVISION_OF->Source`; release edges link the exact restriction, approver, and supporting evidence. Stable tenant-scoped IDs and explicit effective intervals are required. SDK/vector results may nominate candidate evidence only; inability to traverse the canonical witness cannot be repaired by model prose or a cross-graph join.

### INV-005 — Stale graph, claim and policy versions cannot dispatch

A dispatch is guarded by current `graph_version`, `policy_epoch`, task version, claimant and monotonic fencing token. Recheck immediately before side effect. Policy changes invalidate stale plans and claims. Compare-and-set (CAS) semantics must be validated against the pinned FalkorDB build under independent concurrent clients; a serialized coordinator alone is not proof. Losing claimant rereads before retry. Old fence is rejected by command adapter/simulator even after lease expiry.

### INV-006 — No exactly-once side-effect claim; reconcile UNKNOWN

Each physical command has a durable command ID/idempotency key and explicit status. A send timeout, transport reset, or missing acknowledgement yields `UNKNOWN`, not failure and not success. Query adapter state and fresh sensor evidence before deciding whether to continue, retry, or reassign. A task lease expiring does not make a non-idempotent grasp safe to repeat. The system makes no distributed exactly-once promise.

### INV-007 — Fail-closed authority, honest fallback

Graph outage, malformed graph result, unknown schema/constraint state, stale snapshot, unresolved policy contradiction, invalid/abstaining/refusing/timed-out model, or malformed probability distribution never produces an allow. Model-free fallback may choose only from a deterministic, already-authorized safe action set or hold/escalate. It must report `unavailable`/`invalid`/`abstain` honestly and must not synthesize model answers. If current policy cannot be checked, graph-dependent action remains stopped/held.

### INV-008 — Tenant isolation is enforced at the database boundary

Operations graph key is exactly `wf:<tenant>:ops`; corpus graph key is exactly `wf:<tenant>:corpus`. Authenticate tenant outside the model and derive graph selection server-side; never accept tenant/graph selection from prompt or corpus text. Use tenant-scoped credentials/roles and FalkorDB ACLs for graph-key authorization, plus application allowlisted parameterized Cypher and tenant checks as defense in depth. Node labels or `tenant_id` filters alone are not an authorization boundary. Corpus reader/writer cannot access ops; ops coordinator does not expose arbitrary Cypher; cross-tenant calls fail even when node names/IDs collide.

### INV-009 — Model egress is minimized and explicit

Before any model call, enforce tenant, source classification, field allowlist, payload size, and synthetic/public/owned-data policy. Default submission mode permits only synthetic fixture data. Do not send secrets, auth tokens, private company content, hidden simulator truth, raw graph credentials, or unnecessary identifiers. Record provider/model, sanitized input identity/hash, question schema, labels, usage, latency, and status without logging sensitive source text. Provider errors cannot trigger unbounded retries or duplicate egress.

### INV-010 — Corpus and retrieved content are inert, untrusted data

Instruction-like text in manuals, tickets, chats, SDK chunks, aliases, summaries, or model output cannot invoke tools, select tenant/graph, modify restrictions, approve a release, alter allowlists, or write arbitrary Cypher. Escape/delimit content where applicable, but rely on typed schemas and deterministic authorization rather than prompt wording. Extracted claims remain candidates until source identity/span, authority, scope, and approval are independently validated.

### INV-011 — Alias resolution cannot silently merge authority identities

Entity resolution suggestions are candidate mappings only. Similar names, Unicode confusables, aliases, same asset names across tenants, and exact-name dedup do not merge canonical Owner, Decision, Restriction, Corridor, Robot, or tenant IDs without explicit validated mapping. False merge must not connect an otherwise unrelated policy to a target corridor. Preserve source IDs and merge provenance; ambiguous mapping yields `none_of_these`/review.

### INV-012 — SDK destructive and query APIs are isolated

GraphRAG-SDK-managed corpus lives only in its tenant corpus key. Its raw write-capable query, `delete_all`, document deletion/update, re-sync, pending cutover, and ontology graph deletion cannot reach the ops graph. SDK dependencies receive least-privilege credentials restricted to corpus key; destructive calls require explicit corpus maintenance workflow and backup. No SDK `finalize()`/resolver operation may promote authority automatically. Read-only evidence retrieval uses constrained adapter queries.

### INV-013 — Immutable source revision and exact span

Approved source revisions preserve immutable exact normalized UTF-8 text and documented Unicode codepoint offsets; each span resolves to the exact source slice and revision. Revisions coexist; updates create a new revision rather than rewrite history. SDK span propagation is not itself proof of immutable source identity, correct offsets, approval, or cryptographic signature. A source-signature-prefixed property is not a cryptographic signature. Forged/shifted locator or changed bytes make evidence invalid.

### INV-014 — Persistence and audit claims match verified boundary

Application restart, FalkorDB process restart, container recreation, and backup restore are distinct operational cases. Persistent volume and explicit RDB/AOF configuration are required for container durability. State acknowledged within the configured loss window, backup integrity, schema readiness, graph/policy versions, and outstanding command reconciliation must be checked on recovery. Replication is not backup. Never report success on an empty fallback after persistence error. Recovery must not resume a stale plan.

### INV-015 — Annotation and evaluation split separation

Display-only truth annotations, oracle outputs, ground-truth labels, and incident-family identifiers are not agent/model input. Test/train/calibration/held-out evaluation splits group by base incident and source revision so paraphrases, frames, replay, or seed variants of one incident do not leak. The annotation/rendering endpoint is read-only and not reachable through policy tools.

### INV-016 — Attempt and outcome audit integrity

Append-only event records distinguish intent, eligibility result, policy decision, claim, dispatch attempt, acknowledgement, `UNKNOWN`, observed outcome, verification, and final resolution. Denied/failed/unsafe attempts are retained. A simulator/controller stop or later success cannot erase an unsafe earlier attempt. Corrections are superseding events with actor/time/reason, not silent overwrite.

## 3. Proposed trust and privilege design

- **Coordinator:** owns tenant-to-graph mapping and policy evaluation; receives only sanitized sensor DTOs; uses ops-specific least-privilege credentials and allowlisted query templates. No model-controlled Cypher.
- **Corpus ingestion worker:** receives declared synthetic source files, writes only corpus graph, and returns candidate entity/span IDs. It cannot access or mutate ops graph. Any promotion is a separate deterministic validation/review operation with ops credentials.
- **Model adapter:** receives minimal bounded state and candidate snippets only after egress gate. It returns typed labels/distributions with pinned question schema. It cannot call graph, robot, filesystem, or approval tools.
- **Simulator/UI:** physics owner exposes sensor/action adapters. Evaluator oracle and rich display annotations are separate processes/interfaces; policy has no access to their credentials or methods.
- **Approval path:** only configured trusted human/service principals can author approval/release events. Corpus text claiming “approved” or a model identifying an approver does not authenticate that approval.

## 4. Security verification references

The planned adversarial checks are `EV-001` through `EV-018` in `EVALUATION.md`, especially `tests/security/test_tenant_isolation.py`, `tests/security/test_corpus_untrusted_inputs.py`, `tests/security/test_source_span_integrity.py`, `tests/integration/test_claim_cas.py`, and `tests/eval/test_annotation_and_split_leakage.py`. These are proposed test paths, not existing tests. Any violation of INV-001, INV-003 through INV-013, or INV-015 blocks enabling action dispatch; no successful test suite is a certification for physical robot use.

## 5. Decision status and remaining deployment questions

1. Local simulation identity is specified in RUNTIME.md §5: a controlled backend-derived principal and explicit synthetic roster. Production identity/signatures remain out of scope and require a separate ADR.
2. Which exact synthetic fields may egress to the selected System One endpoint, and what retention/logging terms apply to the chosen provider deployment?
3. What is the production tenant/ACL provisioning lifecycle and credential-rotation procedure for FalkorDB? Research shows graph-key ACL scope, not row-level authorization.
4. Source normalization is specified in INTEGRATIONS.md §4 and GRAPH_SCHEMA.md: strict UTF-8, LF normalization, retained original bytes, zero-based half-open Unicode codepoint offsets. Runtime round-trip tests remain required.
5. What observation TTLs are acceptable for each predicate/robot/payload? They must be set per sensor/task and validated, not guessed globally.
6. What are the configured RDB/AOF loss budget, volume/backup/restore owner, and explicit readiness behavior when durability is misconfigured?
