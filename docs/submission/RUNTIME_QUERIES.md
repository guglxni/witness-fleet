# Executable query and graph traversal map

This page maps judge claims to executable source. It documents the implemented path, not the proposed Cypher templates in [`GRAPH_SCHEMA.md`](../../GRAPH_SCHEMA.md). The live mission uses parameterized FalkorDB Cypher plus deterministic Python validation. It does not claim to run every algorithm listed in sponsor documentation.

## Primary track: Track 01, agents that act on connected data

| Decision point | Executable path | What the source does |
|---|---|---|
| Read a bounded tenant graph | [`GraphStore.read_snapshot`](../../src/witness_fleet/graph/store.py) | Reads the version root, nodes and directed edges; brackets materialized reads with graph-version checks, retries boundedly, and rejects oversize/truncated snapshots. |
| Claim an eligible task and its complete resource set | [`GraphStore.claim_task`](../../src/witness_fleet/graph/store.py#L381) | Executes a conditional mutation checking coordinator/task versions, robot availability, task status, conflicting robot/task/resource claims and the exact required-resource set; creates the claim/fences and increments versions in that query. |
| Validate the connected policy and source chain | [`validate_governance`](../../src/witness_fleet/graph/governance.py) | Python traverses the graph snapshot and validates governance roots, edge direction/cardinality, owner and approval, explicit scope, exact source revision and span, and retained source bytes. Invalid/missing records are errors, not permission. |
| Authorize a task against current policy and physical evidence | [`authorize`](../../src/witness_fleet/policy/authorizer.py) and [`runtime/execution.py`](../../src/witness_fleet/runtime/execution.py) | Applies deterministic checks to claim, versions, governance witnesses and fresh evidence before command admission. |
| Select work and enforce dependencies | [`runtime/mission.py`](../../src/witness_fleet/runtime/mission.py) and [`planning/`](../../src/witness_fleet/planning/) | Executes the declared mission plan and filters dependency-invalid or ineligible work. |
| Record outcome evidence | [`runtime/outcomes.py`](../../src/witness_fleet/runtime/outcomes.py) | Preflights retained command/evidence identity, then performs a conditional graph transition and replay validation. It does not make MuJoCo part of the graph transaction. |
| Advance native state and produce measurements | [`services/simulator/service.py`](../../services/simulator/service.py), [`world.py`](../../services/simulator/world.py) | MuJoCo owns the native simulated world; the service executes bounded commands and returns physical evidence. |

The core path is **graph read → Python policy/provenance validation → deterministic eligibility/authorization → conditional task/resource claim → typed command to MuJoCo → fresh evidence → verified graph outcome**. If required graph state or claim writes fail, the normal action path cannot proceed. The optional model/corpus lane is not used to authorize SC-001 actions.

## Secondary track 02: scoped coordination

The claim operation coordinates a task and its required shared resources using task versions, coordinator epoch, claim state and fences. The mission manifest and dependency checks live in [`runtime/bootstrap.py`](../../src/witness_fleet/runtime/bootstrap.py) and [`runtime/mission.py`](../../src/witness_fleet/runtime/mission.py). Command identity and retained known/unknown outcomes are handled by the runtime and the [simulator journal](../../services/simulator/journal.py). This is centrally coordinated simulation with fail-closed reconciliation; it is not decentralized swarm consensus or a general agent-memory benchmark.

## Secondary track 03: scoped policy provenance

The source-linked policy path is implemented in [`graph/governance.py`](../../src/witness_fleet/graph/governance.py) and described in the [graph/evidence guide](../guide/graph-model.md). Synthetic `Decision`, `Restriction`, `Permission`, `Release`, `Owner`, `ApprovalEvent`, `EvidenceSpan`, `Revision` and `Source` records are connected through typed directed relationships. Python validates exact retained source bytes/spans, owner roster, approval, scope and effective interval. This is a bounded policy-provenance workflow, not a general enterprise assistant. Hash integrity proves byte identity, not truth.

## Exact task-claim query

The Cypher below is the complete `cypher` string extracted from the `GraphStore.claim_task` AST at [`store.py`](../../src/witness_fleet/graph/store.py#L381). Only whitespace and line breaks have been added for readability; the executable token sequence is unchanged. The application supplies validated bound parameters. Inspect it as source; do not paste a mutating query into retained demo data.

```cypher
MATCH (s:FleetState {id:'fleet',tenant_id:$tenant_id}), (t:Task {id:$task_id,tenant_id:$tenant_id}), (robot:Robot {id:$robot_id,tenant_id:$tenant_id})
WHERE s.coordinator_epoch=$epoch
  AND t.task_version=$expected_task_version
  AND coalesce(robot.available,false)=true
  AND t.state IN ['READY','PENDING','ACTIVE']
  AND NOT (robot)<-[:HELD_BY]-(:Claim {state:'ACTIVE'})
  AND NOT (robot)<-[:HELD_BY]-(:Claim {state:'UNKNOWN'})
  AND NOT (robot)<-[:HELD_BY]-(:Claim {state:'REASSESS'})
  AND NOT (t)<-[:CLAIMS_TASK]-(:Claim {state:'ACTIVE'})
  AND NOT (t)<-[:CLAIMS_TASK]-(:Claim {state:'UNKNOWN'})
  AND NOT (t)<-[:CLAIMS_TASK]-(:Claim {state:'REASSESS'})
WITH s,t,robot
MATCH (t)-[:REQUIRES_RESOURCE]->(required:Resource)
WHERE required.tenant_id=$tenant_id
WITH s,t,robot,collect(DISTINCT required) AS resources
WHERE size(resources)=size($resource_ids)
  AND size(resources)>0
  AND all(resource IN resources WHERE resource.id IN $resource_ids)
UNWIND resources AS resource
WITH s,t,robot,resource
WHERE NOT (resource)<-[:RESERVES]-(:Claim {state:'ACTIVE'})
  AND NOT (resource)<-[:RESERVES]-(:Claim {state:'UNKNOWN'})
  AND NOT (resource)<-[:RESERVES]-(:Claim {state:'REASSESS'})
WITH s,t,robot,collect(DISTINCT resource) AS resources
WHERE size(resources)=size($resource_ids)
CREATE (cl:Claim {id:$claim_id,tenant_id:$tenant_id,schema_version:$schema_version,created_at:$now,recorded_at:$now, holder_id:$robot_id,robot_id:$robot_id,task_id:$task_id,lease_expires_at_utc:$lease,coordinator_epoch:$epoch, clock_domain:'coordinator_epoch_utc_lease_v1',fence:coalesce(t.claim_fence,0)+1,state:'ACTIVE'})
CREATE (cl)-[:CLAIMS_TASK]->(t)
CREATE (cl)-[:HELD_BY]->(robot)
FOREACH (resource IN resources |
CREATE (cl)-[:RESERVES]->(resource)
SET resource.fence=coalesce(resource.fence,0)+1, resource.resource_version=coalesce(resource.resource_version,0)+1)
SET t.claim_fence=cl.fence,t.task_version=t.task_version+1,s.graph_version=s.graph_version+1
WITH cl,t,s,resources
UNWIND resources AS resource
RETURN properties(cl) AS claim, t.claim_fence AS task_fence, collect({id:resource.id,fence:resource.fence}) AS resource_fences,s.graph_version AS graph_version
```

The line breaks do not introduce or remove Cypher tokens. The claim's conditional checks and graph mutations are within one query. `read_snapshot`, authorization, simulator execution and later outcome recording are distinct steps; see [atomicity boundaries](WHY_FALKORDB.md#atomicity-what-one-query-covers) and the [runtime contract](../../RUNTIME.md).

## Verification entrypoints

- [Hosted mission HTTP integration](../../tests/e2e/test_hosted_simulation.py): isolated FalkorDB + MuJoCo, release gate, no pre-release courier command, seven verified tasks and measured delivery postcondition.
- [Integrated fleet mission](../../tests/e2e/test_integrated_fleet.py): declared seven-task SC-001 assertions.
- [Outcome provenance](../../tests/integration/test_outcome_provenance.py): command/outcome linkage.
- [GraphStore source](../../src/witness_fleet/graph/store.py) and [OutcomeStore source](../../src/witness_fleet/runtime/outcomes.py): authoritative full query strings and write logic.
- Exact baseline CI and deployment proof: [BUILD_STATUS.md](../../BUILD_STATUS.md).

This source map is not a new performance benchmark. The query above is source-derived and its formatting is checked against the runtime literal; it is not an invented schema template.
