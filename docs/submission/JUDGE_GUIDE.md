# Judge guide

Start at the [product website](https://witness-fleet.vercel.app) and its narrated launch film. The [hosted simulation](https://witness-fleet-guglxni.eastus.cloudapp.azure.com/demo) is separate from the illustrative website: it advances real MuJoCo state only on explicit visitor action.

## What to try

1. Start one isolated session.
2. Run authorized tasks: recovery and verification complete, then the courier waits.
3. Confirm the **synthetic demo-owner release** explicitly.
4. Run the remaining tasks: fresh courier sensing, travel and delivery.
5. Inspect the seven verified task states. This is simulation evidence, not a certification claim.

If capacity is exhausted, the server fails closed. Use the recorded film and local reproduction; there is deliberately no public reset/HOLD-clear button.

## What to inspect

- [README](../../README.md): quickstart and system map.
- [Architecture](../guide/architecture.md), [robotics](../guide/simulation.md), [SC-001](../guide/sc-001-mission.md).
- [Editable diagrams](../diagrams/README.md).
- [Graph authority](../../src/witness_fleet/runtime), [native simulator](../../services/simulator).
- [Public gateway](../../src/witness_fleet/hosting), [deployment](../../deploy/azure/README.md).
- [Video bytes](../../site/public/media/launch.mp4), [sanitized provenance](../../site/public/media/provenance.json).

Model suggestions are non-authoritative; the native SC-001 mission uses deterministic logic. A transport receipt is not a verified physical result. Source hashes establish linkage, not the truth of arbitrary source claims.

## Local reproduction

Follow the root README. Python, corpus and web environments are separate. CI executes tests; green UI/build output alone is not fleet acceptance. Check the exact commit and deployed health revision for current verification status.
