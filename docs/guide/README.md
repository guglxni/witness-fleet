# Witness Fleet engineering guide

> **Current scope:** a synthetic, simulation-first robotics workflow with a local operator console and a separately isolated hosted demonstration. The repository contains graph-authorized SC-001 mission code and a native MuJoCo simulator. It is not a physical fleet controller, safety certification, or proof that every aspirational scenario is implemented.

This guide explains the executable slice from source, distinguishes it from planned integrations, and links each important behavior to its implementation. Start with the [architecture](architecture.md), then follow the [SC-001 walkthrough](sc-001-mission.md). The [diagram index](../diagrams/README.md) provides editable sources and reproducible render commands.

## Guide map

| Guide | Use it for |
|---|---|
| [Architecture and boundaries](architecture.md) | Components, ownership, runtime vs. optional lanes, trust boundaries |
| [Graph model and authority](graph-model.md) | Node/edge meaning, source provenance, authorization invariants |
| [SC-001 mission lifecycle](sc-001-mission.md) | Seven-task run, owner gate, verified delivery and evidence |
| [Simulation and robotics model](simulation.md) | Facility geometry, bodies, S0 sensing, model limitations |
| [Security and safety boundaries](security.md) | Threat model, HOLD behavior, what this local demo does not guarantee |
| [Local setup and operator runbook](operations.md) | Prerequisites, launch, inspect, hold, preserve and recover local runs |
| [Evidence and verification](evidence.md) | Provenance, statuses, test/evidence interpretation |
| [Interface guide](interfaces.md) | Recorded evidence, schema exploration, sampled native scenes and local operator inspection |
| [Deployment status](deployment.md) | Separate local/hosted boundaries, Azure/Vercel delivery and exact-revision verification |

## Source-of-truth order

- Executed behavior: implementation and tests linked inline in each guide.
- Graph relationship direction: [`GRAPH_SCHEMA.md`](../../GRAPH_SCHEMA.md); the guide describes current behavior where it is implemented.
- Runtime command/dispatch contract: [`RUNTIME.md`](../../RUNTIME.md), alongside executable implementation.
- Simulator assumptions: [`services/simulator/world.py`](../../services/simulator/world.py), [`sensors.py`](../../services/simulator/sensors.py), and [`facility.xml`](../../services/simulator/assets/facility.xml).
- Local setup and tested command history: [`README.md`](../../README.md), [`BUILD.md`](../../BUILD.md), [`RUNBOOK.md`](../../RUNBOOK.md), and retained reports. These documents may contain different workflow generations; prefer the specific launcher and current executable for the flow being described.

Proposed architecture and unimplemented details are labeled **planned** or **pending**. A diagram is not a substitute for runtime verification. Consult [verification status](../../BUILD_STATUS.md) and [deployment evidence](deployment-evidence.md) for the exact tested revision; documentation alone does not establish a new test run, cloud deployment, model inference, or real-robot operation.
