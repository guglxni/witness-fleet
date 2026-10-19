# Why FalkorDB is in the control path

## The data is a network of relationships

The mission checks more than isolated records. A decision imposes a restriction; an owner carries authority; a retained source span belongs to a revision and source; scope ties policy to a corridor and action; a release may lift one named restriction. Tasks depend on other tasks, robots have capabilities, and claims reserve tasks and shared resources. The graph makes these typed, directed links explicit in the operational store.

That shape matters when a decision must be explained and checked against all connected evidence. It does not make the visualization authoritative. The runtime checks node identity, relationship direction, scope, provenance, source-span integrity, policy state and physical evidence; a missing or malformed link fails closed.

## Why not a relational database?

A relational design can implement the same behavior. It could store each entity in a table, each relationship in a foreign-key/junction table, and use recursive CTEs or joins for dependency and provenance traversal. With appropriate transactions, compare-and-swap predicates, uniqueness rules and careful testing, that alternative is technically viable.

FalkorDB is the chosen store because the application is organized around connected records and relationship traversal, while the required conditional claim/outcome changes can be expressed as graph mutations. The choice keeps the linked operational graph in the same query model rather than introducing an application-maintained shadow relationship store. This is a product fit, not a claim that relational systems cannot do graph work, that graph queries are always faster, or that the database alone grants permission.

## What Python does

The runtime is written in Python. `GraphStore` issues parameterized FalkorDB reads and writes. It reads a bounded tenant snapshot; `validate_governance` traverses the materialized nodes and edges and checks the complete source/owner/policy paths; planning selects dependency- and capability-eligible work; the deterministic authorizer checks policy, claims, versions and fresh evidence; the coordinator sends typed commands and validates retained outcomes. Policy traversal is Python code over graph data, not a model-generated query or a claim to use a server-side shortest-path procedure.

The optional corpus SDK/model lane is isolated and is not used by the SC-001 control path. Inference is not part of the demonstrated authorization loop.

## What MuJoCo does

MuJoCo advances the simulated physical world: robot poses, contact, obstacle motion and payload placement. Python owns the simulator service, applies bounded controllers, collects native sensor/effect measurements and turns them into typed evidence. A controller completion or transport receipt is not enough to complete a task; the required postconditions must be measured in the simulated world.

This is a native simulation with simple synthetic assets. It is not a real robot, safety certification, perception benchmark or sim-to-real result.

## The mission loop

The SC-001 manifest has seven tasks and an explicit owner gate:

1. Scout inspection records initial scoped evidence.
2. The recovery robot attempts bounded physical clearance; the attempt still needs verification.
3. The scout parks at its declared pose.
4. A fresh post-recovery check verifies the changed scene. The mission pauses here.
5. A configured local maintenance-owner action explicitly releases the named restriction under the expected policy epoch and scope.
6. The courier takes its own fresh observation, then travels only if current authority and physical checks pass.
7. The courier verifies its path and delivers; a native payload-in-delivery-zone postcondition supports the final outcome.

The release is scripted/configured, not an authenticated human approval. The scout's observation is not courier evidence. The full manifest and assertions are in [`sc-001-mission.md`](../guide/sc-001-mission.md) and [`tests/e2e/test_integrated_fleet.py`](../../tests/e2e/test_integrated_fleet.py).

## Atomicity: what one query covers

`GraphStore.claim_task` sends one conditional Cypher mutation. In that query it checks coordinator epoch, task version, robot availability, task state, active/unknown/reassess claims, the complete required-resource set and resource availability. If those predicates hold, the same query creates the claim and its task/robot/resource edges, increments task/resource fences and versions, and advances `graph_version`. A no-row result is a conflict or failed precondition, not a partial claim. The exact source-derived statement and its clauses are in [`RUNTIME_QUERIES.md`](RUNTIME_QUERIES.md).

The boundary matters:

- `read_snapshot` uses separate node and edge reads bracketed by `graph_version` checks and bounded retries. The source explicitly does not treat those reads as a FalkorDB transaction.
- Authorization and claim admission are separate steps; the execution path rechecks state and binds the authorization receipt to the relevant identities and versions.
- The simulator is a separate service. There is no transaction spanning FalkorDB and MuJoCo. The journal, command identity, receipts, fences and reconciliation logic handle that boundary; they do not create distributed exactly-once semantics.
- An atomic single graph query does not imply rollback across arbitrary `MULTI/EXEC` commands or cross-service actions.

## Evidence is not the same as a claim

A source hash, quote and span offset establish that retained evidence bytes match a particular source revision and locator. They do not establish that the policy is true, current, lawful or authoritative. The governance validator checks owner, approval, scope, effective interval, relationship integrity and the source chain. Physical observations are separate: they must be fresh, scoped, visible and relevant to the robot/task. A proposal or policy record is not a measured world outcome; a transport receipt is not a postcondition. The final outcome requires native simulator evidence tied to the command and episode.

The live records are synthetic. The public metric `unauthorized_executed` remains unknown (`null`), not zero. See the [graph/evidence guide](../guide/graph-model.md), [outcome contract](outcome-contract.md), and [verification status](../../BUILD_STATUS.md).
