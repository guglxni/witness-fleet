# Judge walkthrough

**Start with the live simulation** at [the hosted demo](https://witness-fleet-guglxni.eastus.cloudapp.azure.com/demo), then use the five checks below to distinguish an observed state from a claim. The product site and its animation explain the idea; the hosted demo advances a separate native MuJoCo simulation only after an explicit action.

**Track fit:** Track 01, Agents That Act on Connected Data, is primary. Tracks 02 and 03 are narrower supporting claims: central coordination and source-linked synthetic policy provenance. The [submission brief](SUBMISSION_BRIEF.md) contains the full scope and AI-use disclosure.

## Five observable conditions

1. **A bounded synthetic session exists.** Create one session. The returned state shows seven declared tasks and the `scout`, `recovery`, and `courier` roles. Startup alone does not move the robots.
2. **Recovery reaches a real gate.** Run the initial work. The session pauses at `awaiting_owner_release` after four commands; recovery is verified, delivery remains incomplete, and no courier command is present. This is a visible dependency/policy boundary, not a narrated promise.
3. **The reason is inspectable.** Follow the displayed restriction, owner, evidence span, source revision, and task dependency links. The source material and owner are synthetic. A staged release is not an approval. A source hash and exact quote establish byte linkage, not that a policy is true or lawful.
4. **Release is explicit and scoped.** Confirm the configured local demo-owner release with the expected policy epoch, then run the courier phase. This is a scripted/configured owner action, not authenticated human identity or a production approval workflow. Courier-specific fresh sensing is required; scout evidence is not inherited as courier evidence.
5. **Completion depends on native evidence.** Inspect the final state: seven tasks `VERIFIED`, seven commands `OUTCOME_VERIFIED`, and the native delivery postcondition `payload_in_delivery_zone: true`. The receipt is tied to a simulator result. The separate `unauthorized_executed` metric remains unknown (`null`), not zero.

The complete assertions are in [`tests/e2e/test_hosted_simulation.py`](../../tests/e2e/test_hosted_simulation.py) and [`tests/e2e/test_integrated_fleet.py`](../../tests/e2e/test_integrated_fleet.py). The run that supports the core proof is pinned in [BUILD_STATUS.md](../../BUILD_STATUS.md); it is runtime-baseline evidence, not a claim about every later frontend revision.

## Where to inspect the implementation

- [Execution map and exact task-claim Cypher](RUNTIME_QUERIES.md): source links for every stage, with the full claim query formatted from `GraphStore.claim_task`.
- [Why FalkorDB](WHY_FALKORDB.md): what connected records buy here, what Python does, and the relational alternative.
- [SC-001 manifest](../guide/sc-001-mission.md), [architecture](../guide/architecture.md), [graph/evidence model](../guide/graph-model.md), and [simulation assumptions](../guide/simulation.md).
- [Main film](../../site/public/media/launch.mp4), [provenance](../../site/public/media/provenance.json), and [preserved campaign cuts](../../README.md#product-site-and-preserved-media).

## Limits to keep in view

The public demo is simulation-only. It does not demonstrate hardware control, production robotics, human IAM, safety certification, decentralized swarm consensus, or live model inference. The central coordinator uses deterministic Python validation over a bounded FalkorDB snapshot. Transport acknowledgment and controller completion are not verified outcomes. The full task claim is one conditional graph mutation, but graph reads, later authorization, and MuJoCo execution do not share a cross-service transaction. Process-death recovery and unknown-receipt HOLD behavior have separate tests; do not claim that the normal filmed mission stages a process kill.

If public session capacity is exhausted, use the preserved film and inspect the linked source/tests. There is intentionally no public reset or HOLD-clear control.
