# Witness Fleet

[![Verification](https://github.com/guglxni/witness-fleet/actions/workflows/verify.yml/badge.svg)](https://github.com/guglxni/witness-fleet/actions/workflows/verify.yml) · [MIT](LICENSE)

## Evidence before motion

**A corridor can be physically clear and still be forbidden.** Witness Fleet runs a three-robot MuJoCo simulation in which current company authority, fresh physical evidence, task ownership and measured outcomes stay separate.

[Product site](https://witness-fleet.vercel.app) · [Interactive simulation](https://witness-fleet-guglxni.eastus.cloudapp.azure.com/demo) · [Three-minute demo script](docs/submission/DEMO_SCRIPT.md) · [Five-check judge walkthrough](docs/submission/JUDGE_GUIDE.md) · [Submission brief and disclosure](docs/submission/SUBMISSION_BRIEF.md)

> This is a simulation, not hardware control or safety certification. The hosted mission uses a configured synthetic demo-owner release, not authenticated human identity. The deterministic SC-001 control path does not use live model inference.

![Witness Fleet system boundaries](docs/diagrams/system-boundaries.svg)

## Start with proof

The last pinned core verification and deployment run tested source commit [`51e789d`](https://github.com/guglxni/witness-fleet/commit/51e789daf75fff7f8bb29b84523679813449aa7d). CI passed **935 main tests and 10 corpus tests**, with no failures, errors or skips; the Azure deployment job also passed and checked the public revision. That pinned run establishes the runtime baseline, not later frontend revisions. See [verification scope](BUILD_STATUS.md) and the workflow result attached to each source commit.

The strongest observable path is the seven-task SC-001 mission: scout observation; bounded recovery; post-recovery verification; a pause at the owner-release gate; then fresh courier sensing, travel and native delivery verification. The test checks that no courier command exists before the explicit release and that the final delivery postcondition is measured. [Task manifest and assertions](docs/guide/sc-001-mission.md) · [exact execution map](docs/submission/RUNTIME_QUERIES.md) · [FalkorDB rationale and limits](docs/submission/WHY_FALKORDB.md).

## The distinction the system enforces

A scout sees an obstruction. A recovery robot moves it. That does not grant the courier permission to enter. The courier proceeds only after a source-linked configured owner release, current deterministic authorization, and fresh courier-scoped evidence. A transport acknowledgment is not a physical outcome; the final delivery claim needs native postcondition evidence.

### What each part does

| Part | Implemented responsibility | Boundary |
|---|---|---|
| **FalkorDB operations graph** | Stores tenant-scoped tasks, dependencies, claims, typed governance, source revisions/spans, and outcomes | The graph stores connected records; Python validation and the native simulator still do their own work |
| **Python runtime** | Reads a bounded graph snapshot, validates provenance and governance, selects eligible tasks, applies deterministic policy, coordinates commands, and checks outcomes | No model confidence or arbitrary generated query grants permission |
| **MuJoCo simulator** | Advances the native synthetic world and reports sensor/effect evidence such as contacts, displacement, stability and payload placement | Simple simulation geometry is not production robotics or sim-to-real evidence |
| **Command journal and graph writes** | Preserve identity, fences, receipts, known/unknown outcomes and verified task state | No distributed transaction or exactly-once guarantee across FalkorDB and the simulator |
| **Operator interface and hosted gateway** | Show mission state, collect explicit demo actions, isolate visitor sessions and return bounded state | A configured demo owner is not human IAM; public demo sessions do not expose local operator APIs or hardware |

See [architecture and ownership](docs/guide/architecture.md), [simulation assumptions](docs/guide/simulation.md), [security boundaries](docs/guide/security.md), and the [runtime contract](RUNTIME.md).

## Try the hosted simulation

Open the [interactive simulation](https://witness-fleet-guglxni.eastus.cloudapp.azure.com/demo), create one session, and run the initial tasks. The mission pauses after recovery and verification; no courier command should appear before the release. Confirm the explicitly labeled synthetic demo-owner release, then run the remaining tasks and inspect the final verified task/command states. The judge guide lists five visible conditions and recovery steps if the hosted service is unavailable.

## Run the native local mission

Prerequisites: **Python 3.12+, uv, Node.js 24+, Docker, FFmpeg**. The mission needs no cloud credentials or paid inference.

```bash
git clone https://github.com/guglxni/witness-fleet.git
cd witness-fleet
uv sync --frozen --extra dev --extra simulator
npm --prefix web ci
npm --prefix web run build
.venv/bin/witness-fleet doctor
.venv/bin/python -m scripts.run_local_mission \
  --run-dir /tmp/witness-fleet-new-run --port 8095
```

Open **http://127.0.0.1:8095**. Startup does not move robots. Select **Run tasks**, inspect the pause and its witnesses, explicitly submit the local synthetic demo-owner release, then select **Run tasks** again. The launcher creates its own loopback FalkorDB server. Ctrl-C stops only that container and retains the volume and run directory. Choose a new run directory for a new demonstration; do not reset retained evidence.

## Why FalkorDB, and what it does not prove

The relevant data is connected: a restriction is imposed by a decision, owned by an authority, supported by an exact source span and revision, scoped to a corridor, and possibly lifted by a release; tasks also depend on one another and reserve shared resources. The runtime uses those explicit relationships as an operational record and for conditional graph writes. A relational database with foreign keys, join tables, recursive queries and suitable transaction/CAS logic could implement the same workflow. The reason for the graph here is direct representation and traversal of those relationships, not a claim that relational systems cannot do it or that a graph is automatically faster. See [WHY_FALKORDB.md](docs/submission/WHY_FALKORDB.md).

Python materializes and validates a bounded snapshot; it does not claim a server-side graph algorithm for policy traversal. The task claim is a single conditional Cypher mutation, but snapshot reads, later authorization and simulator motion are not one database transaction. See the [exact source-linked query map](docs/submission/RUNTIME_QUERIES.md) and [graph model](docs/guide/graph-model.md).

## Product site and preserved media

The product site uses original robot diagrams, Vanta, GSAP and Lenis with accessible motion controls. Recorded native footage is identified separately from illustration. These media files remain available in the repository:

- [Original 86-second narrated launch film](site/public/media/launch.mp4) · [sanitized provenance](site/public/media/provenance.json) · [editable motion project](media/launch/README.md)
- [Campaign cut](site/public/media/campaign/product-ad.mp4) · [credits](site/public/media/campaign/CREDITS.md)
- [Industry-view cut](site/public/media/campaign/product-ad-iv.mp4) · [credits](site/public/media/campaign/CREDITS-IV.md)
- [FalkorDB cut](site/public/media/campaign/product-ad-falkordb.mp4) · [credits](site/public/media/campaign/CREDITS-FALKORDB.md)
- [Alternate film cut](site/public/media/campaign/film-ii.mp4) · [campaign transcript](site/public/media/campaign/transcript.txt)

The main film includes recorded MuJoCo footage, an OpenDesign Motion excerpt and ElevenLabs Sarah narration; HyperFrames produced the film. The campaign files retain their own credits. FalkorDB server uses SSPL; GSAP uses its Standard License; ElevenLabs is proprietary. Do not describe the full stack as OSI FOSS. See [third-party notices](THIRD_PARTY.md) and [publication scope](PUBLICATION.md).

## Hackathon tracks and participant action

- **Primary, Track 01: Agents That Act on Connected Data.** FalkorDB relationships supply current restrictions, permissions, dependencies and evidence to deterministic authorization before native actions.
- **Secondary, Track 02: Agent Memory and Coordination.** Scoped to a centrally coordinated simulation: shared task state, claim fences, dependencies, retained command/outcome history and tested fail-closed recovery. This is not decentralized swarm consensus.
- **Secondary, Track 03: Company Brain.** Scoped to synthetic decisions, owners, restrictions and releases linked to retained source spans. This is not a general enterprise assistant.

The [submission brief](docs/submission/SUBMISSION_BRIEF.md) preserves the AI-use disclosure and paste-ready links. Listing tracks and publishing a repository do not submit an entry; the participant must select tracks, review the disclosure and complete the organizer's form.

## Verification and deeper reading

The [Verification workflow](.github/workflows/verify.yml) runs isolated test environments. The [Azure deployment workflow](.github/workflows/deploy-azure.yml) consumes a tested revision, deploys by digest and checks the public revision; Vercel is a separate product-site deployment. A configured workflow is not proof of a passed run. Consult the pinned [CI and deployment record](BUILD_STATUS.md) and the actual [Actions history](https://github.com/guglxni/witness-fleet/actions).

| Start here | Implementation detail |
|---|---|
| [Judge guide](docs/submission/JUDGE_GUIDE.md) | [SC-001 mission](docs/guide/sc-001-mission.md) |
| [Runtime query map](docs/submission/RUNTIME_QUERIES.md) | [Graph/evidence model](docs/guide/graph-model.md), [proposed schema](GRAPH_SCHEMA.md) |
| [Why FalkorDB](docs/submission/WHY_FALKORDB.md) | [Architecture and ownership](docs/guide/architecture.md) |
| [Guide index](docs/guide/README.md) | [Native simulation assumptions](docs/guide/simulation.md) |
| [Evidence and verification](docs/guide/evidence.md) | [Security and failure behavior](docs/guide/security.md), [failure modes](FAILURE_MODES.md) |
| [Editable diagrams](docs/diagrams/README.md) | [Math and robotics](MATH.md), [robotics derivations](math/ROBOTICS.md) |

The implemented demonstration is SC-001, not the full design space in the specifications. The optional model lane is disabled for that mission. A hash proves which bytes were retained, not that arbitrary source text is true. Review [AI-use disclosure](docs/submission/SUBMISSION_BRIEF.md#ai-assistance-and-runtime-behavior) and [third-party terms](THIRD_PARTY.md) before reuse or publication.

## Repository map

```text
src/witness_fleet/     graph, policy, planning, runtime, API and hosted gateway
services/simulator/   native MuJoCo world, controllers, sensors and durable journal
services/corpus/      isolated optional corpus SDK environment
web/                  local operator console
site/                 public product launch website and preserved media
fixtures/             synthetic policies and scenarios
tests/                unit, contract, integration, adversarial and native E2E
scripts/              setup, suite runner, capture and verification
deploy/azure/         Bicep infrastructure and VM deployment script
docs/guide/           source-grounded engineering guides
docs/submission/      judge path, execution map, disclosure and packaging checklist
docs/diagrams/        editable diagram sources and rendered previews
```

**Agent instruction files:** the original protected-file consent timeout left `AGENTS.md`, `CLAUDE.md` and `SKILL.md` absent. They were not recreated under alternative names. The specifications are documentation, not a substitute for protected agent instructions.
