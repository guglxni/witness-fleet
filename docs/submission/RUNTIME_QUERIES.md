# Queries and graph algorithms actually used

This page maps to executable source, not the aspirational query templates in `GRAPH_SCHEMA.md`. The mission uses parameterized FalkorDB Cypher and deterministic graph validation; it does not claim to run every algorithm listed in sponsor documentation.

## Execution map

| Product decision | Actual implementation |
|---|---|
| Read versioned tenant state, nodes and directed edges | [`GraphStore.read_snapshot`](../../src/witness_fleet/graph/store.py): reads bracketed by graph-version checks; oversize snapshots fail closed |
| Reserve a task and its complete resource set | [`GraphStore.claim_task`](../../src/witness_fleet/graph/store.py): conditional atomic Cypher checks coordinator/task versions, robot availability and conflicting claims, then allocates fences |
| Follow restriction/permission/release source and ownership paths | [`validate_governance`](../../src/witness_fleet/graph/governance.py): deterministic traversal of the materialized FalkorDB nodes/edges; validates exact source revisions/spans and authority |
| Gate motion using authority and fresh native evidence | [`authorize`](../../src/witness_fleet/policy/authorizer.py), [`runtime/execution.py`](../../src/witness_fleet/runtime/execution.py) |
| Persist command-bound physical outcomes | [`runtime/outcomes.py`](../../src/witness_fleet/runtime/outcomes.py): preflight + conditional graph writes + replay validation |
| Reject dependency-invalid work and select mission tasks | [`runtime/mission.py`](../../src/witness_fleet/runtime/mission.py), [`planning`](../../src/witness_fleet/planning) |

Policy traversal over a FalkorDB snapshot is implemented in Python. It is not presented as a server-side shortest-path algorithm or model-generated query. The graph contains the canonical records and relationships; if graph reads/claims fail, the normal action path cannot proceed.

## Representative read queries

The following static read strings are used by `GraphStore` with bound parameters:

```cypher
MATCH (s:FleetState {id:$id, tenant_id:$tenant_id})
RETURN properties(s) AS state
```

```cypher
MATCH (c:Claim)-[:CLAIMS_TASK]->(t:Task {id:$task_id,tenant_id:$tenant_id})
RETURN properties(c) AS claim
```

```cypher
MATCH (c:Claim)-[:RESERVES]->(r:Resource {id:$resource_id,tenant_id:$tenant_id})
RETURN properties(c) AS claim
```

## Exact task-claim query

Extracted from the executable `GraphStore.claim_task` string. Run only against an isolated synthetic fixture through the application, which supplies validated parameters. Do not paste mutating queries into retained judge/demo data.

```cypher
MATCH (s:FleetState {id:'fleet',tenant_id:$tenant_id}), (t:Task {id:$task_id,tenant_id:$tenant_id}), (robot:Robot {id:$robot_id,tenant_id:$tenant_id}) WHERE s.coordinator_epoch=$epoch AND t.task_version=$expected_task_version AND coalesce(robot.available,false)=true AND t.state IN ['READY','PENDING','ACTIVE'] AND NOT (robot)<-[:HELD_BY]-(:Claim {state:'ACTIVE'}) AND NOT (robot)<-[:HELD_BY]-(:Claim {state:'UNKNOWN'}) AND NOT (robot)<-[:HELD_BY]-(:Claim {state:'REASSESS'}) AND NOT (t)<-[:CLAIMS_TASK]-(:Claim {state:'ACTIVE'}) AND NOT (t)<-[:CLAIMS_TASK]-(:Claim {state:'UNKNOWN'}) AND NOT (t)<-[:CLAIMS_TASK]-(:Claim {state:'REASSESS'}) WITH s,t,robot MATCH (t)-[:REQUIRES_RESOURCE]->(required:Resource) WHERE required.tenant_id=$tenant_id WITH s,t,robot,collect(DISTINCT required) AS resources WHERE size(resources)=size($resource_ids) AND size(resources)>0 AND all(resource IN resources WHERE resource.id IN $resource_ids) UNWIND resources AS resource WITH s,t,robot,resource WHERE NOT (resource)<-[:RESERVES]-(:Claim {state:'ACTIVE'}) AND NOT (resource)<-[:RESERVES]-(:Claim {state:'UNKNOWN'}) AND NOT (resource)<-[:RESERVES]-(:Claim {state:'REASSESS'}) WITH s,t,robot,collect(DISTINCT resource) AS resources WHERE size(resources)=size($resource_ids) CREATE (cl:Claim {id:$claim_id,tenant_id:$tenant_id,schema_version:$schema_version,created_at:$now,recorded_at:$now, holder_id:$robot_id,robot_id:$robot_id,task_id:$task_id,lease_expires_at_utc:$lease,coordinator_epoch:$epoch, clock_domain:'coordinator_epoch_utc_lease_v1',fence:coalesce(t.claim_fence,0)+1,state:'ACTIVE'}) CREATE (cl)-[:CLAIMS_TASK]->(t) CREATE (cl)-[:HELD_BY]->(robot) FOREACH (resource IN resources | CREATE (cl)-[:RESERVES]->(resource) SET resource.fence=coalesce(resource.fence,0)+1, resource.resource_version=coalesce(resource.resource_version,0)+1) SET t.claim_fence=cl.fence,t.task_version=t.task_version+1,s.graph_version=s.graph_version+1 WITH cl,t,s,resources UNWIND resources AS resource RETURN properties(cl) AS claim, t.claim_fence AS task_fence, collect({id:resource.id,fence:resource.fence}) AS resource_fences,s.graph_version AS graph_version
```

## Verification entrypoints

- [Native mission end-to-end](../../tests/e2e/test_hosted_simulation.py): real isolated FalkorDB + MuJoCo, all seven tasks and delivery postcondition.
- [Outcome provenance](../../tests/integration/test_outcome_provenance.py): command/outcome linkage.
- [Graph store](../../src/witness_fleet/graph/store.py) and [outcome store](../../src/witness_fleet/runtime/outcomes.py) are the authoritative full query source.

A source code/query inventory is not a new benchmark. See the exact commit's [CI results](https://github.com/guglxni/witness-fleet/actions/workflows/verify.yml) and [deployment evidence](../guide/deployment-evidence.md).
