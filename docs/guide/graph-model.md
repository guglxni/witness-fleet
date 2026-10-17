# Graph model and authority semantics

## Operational graph is the decision boundary

The graph records operational objects and the auditable relations needed to decide whether a bounded proposal can be admitted. Tenant selection is derived by the server; operational and corpus graph names are separate. The normative schema proposal and relationship directions are in [`GRAPH_SCHEMA.md`](../../GRAPH_SCHEMA.md). The executable store, governance validator and bootstrap are [`graph/store.py`](../../src/witness_fleet/graph/store.py), [`graph/governance.py`](../../src/witness_fleet/graph/governance.py), and [`runtime/bootstrap.py`](../../src/witness_fleet/runtime/bootstrap.py).

## Important entities

| Record | Meaning in the workflow |
|---|---|
| `FleetState` | Version root, policy/coordinator epochs and dispatch sequence |
| `Task` | One DAG unit; dependent task points to prerequisite with `DEPENDS_ON` |
| `Robot`, `Capability` | Declared role, footprint and capabilities; not privileged live-world truth |
| `Resource`, `Claim` | Exclusive reservation plus monotonically fenced ownership; an expired lease alone does not prove the old effect absent |
| `Command`, `AuthorizationReceipt`, `DispatchEvent` | Exact proposal, deterministic admission evidence and ordered delivery intent |
| `DeliveryReceipt` | Event applied acknowledgment, not a physical outcome |
| `Observation`, `PlanningFact`, `Hypothesis` | Sensor observation vs. derived accepted input vs. unresolved candidate; these are deliberately distinct |
| `Source`, `Revision`, `EvidenceSpan` | Source identity, immutable retained version and exact half-open Unicode-codepoint quote locator |
| `Decision`, `Restriction`, `Permission`, `Release`, `Owner`, `ApprovalEvent` | Typed governing authority, scope, approval and named restriction release |
| `Episode`, `Procedure`, `Assessment` | Incident history, reviewed candidate procedure, and optional model assessment; similarity/model output is never live authority |

## Directed witness paths

A typical restriction witness is a branching subgraph, not a fictional single chain:

```text
Decision -IMPOSES-> Restriction -APPLIES_TO-> Corridor
    |                                  \
    + -OWNED_BY-> Owner                 (scope target)
    + -SUPPORTED_BY-> EvidenceSpan -IN_REVISION-> Revision -REVISION_OF-> Source
    + <-APPROVES- ApprovalEvent

Release -LIFTS-> that exact Restriction
    + -APPROVED_BY-> Owner
    + -SUPPORTED_BY-> EvidenceSpan -> Revision -> Source
```

Relationship arrows follow [`GRAPH_SCHEMA.md`](../../GRAPH_SCHEMA.md); source chain integrity and exact offsets are checked by [`graph/governance.py`](../../src/witness_fleet/graph/governance.py). A missing, duplicate, cross-tenant, out-of-manifest, malformed, or unround-trippable link is an integrity issue, not evidence of permission. The witness API scopes expansion to the selected canonical root; unrelated decisions sharing an owner/source must not silently widen the result ([`runtime/coordinator.py`](../../src/witness_fleet/runtime/coordinator.py)).

## Deterministic authorization checks

At a high level, execution constructs a versioned proposal and typed claim, then the authorizer requires:

1. a complete evidence bundle and matching graph/policy/task/dependency versions;
2. active claim identity, lease and exact resource-fence set;
3. complete governance integrity and an explicit base permission for the exact corridor/action/robot scope;
4. no applicable active or staged restriction that blocks the action; a release only clears the exact named restriction, never a second one;
5. current, visible, correctly scoped physical observations for every required predicate and for the execution horizon.

Authorization returns a deterministic reasoned status, not a free-text rationale. `DENY`, `NEEDS_APPROVAL`, `NEEDS_EVIDENCE`, and `STALE` remain non-admissions. An `ALLOW` receipt is bound to exact proposal hash, actor/task/claim, resource fences, versions, witnesses and validity tick; existence of a receipt alone does not make changed state admissible. See [`policy/authorizer.py`](../../src/witness_fleet/policy/authorizer.py), [`runtime/execution.py`](../../src/witness_fleet/runtime/execution.py), and [`domain.py`](../../src/witness_fleet/domain.py).

## Sources and semantics

The local demo starts from synthetic source fixtures retained through [`ingestion/source_store.py`](../../src/witness_fleet/ingestion/source_store.py). Offsets identify slices of normalized retained text; a content hash identifies bytes, not their truth. The optional corpus SDK is separately isolated per [`INTEGRATIONS.md`](../../INTEGRATIONS.md). Retrieved passages and model assessments may propose attention/review candidates. They do not mutate canonical authority, select arbitrary graph keys, or bypass the same deterministic authorizer. In the current SC-001 mission, `model_mode` is explicitly `disabled`.

## Schema status

[`GRAPH_SCHEMA.md`](../../GRAPH_SCHEMA.md) labels its query templates a proposed contract and explicitly says they are not runtime-tested there. This guide documents the implemented runtime where referenced, but does not upgrade every proposed Cypher template, migration or graph constraint into a verified deployment guarantee. Validate a contract against the pinned engine before relying on it operationally.
