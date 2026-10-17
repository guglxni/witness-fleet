# Detailed upstream integration source audit

> Inspection appendix only. `../INTEGRATIONS.md`, `../architecture.md` and `../ADRS.md` define current choices. Source examples below are upstream research, not commands to execute wholesale and not a record of successful installation. Do not import a live Hermes plugin or modify services to use a reference.

# Integration research: verified repository inventory and build recommendation

**Scope:** repository/dependency recommendations for the Graph Hacks fleet project, based on the supplied earlier research reports plus a read-only `gh` audit on 2026-10-15. No repository was cloned; no application, provider, benchmark, simulator, or model was run. The inventory verifies source metadata, exact immutable commits, license paths/text and source paths, not cross-package runtime compatibility.

## Decision

Keep the first build narrow: **original MuJoCo physical world + direct FalkorDB Python client + canonical graph queries/state, with a small Python backend.** The graph is the shared primary source for current tasks, restrictions, evidence and verified episodes. Use an isolated optional System One assessor only for bounded interpretation/ranking; deterministic code checks authorization, scope, freshness, physical clearance and execution state.

- Pin the server to FalkorDB **v6.0.2** at `7b7b4d1ed23fe78e69fa5da0c9e4f2ea2e73f3e9`; direct client at audited SHA below. Persist storage deliberately. Server is **SSPL v1**, not OSI-approved.
- Use the official `falkordb-py` package/client. Retrieval query paths explicitly expose `ro_query`; application-owned parameterized queries and strict read/write separation are required. No arbitrary LLM-authored Cypher, unrestricted `GraphRAG.query`, or claim that raw `GraphRAG.query()` is read-only.
- Model three simple original robot MJCF entities in **one MuJoCo process/clock**. On macOS/Apple arm64, native use is documented by the pinned MuJoCo source guide: prebuilt dynamic libraries for arm64 on macOS, Python `pip install mujoco` bundle, and `mjpython` for `viewer.launch_passive`. This is docs/code evidence, not an install or local arm64 execution test.
- Choose at most one narrow GraphRAG-SDK company-corpus graph if it demonstrably improves ingestion/retrieval. The pinned SDK has a deterministic structured `TableMapping` path (source and example tree-verified); keep it outside canonical authority, use stable external IDs and explicit source revisions, and isolate dependencies from the Microsoft SDK if required. Keep the demo viable without the SDK.
- Decision integration: `guglxni/ms-decision-provider` is a source-verified reference candidate (not installed or exercised) and Microsoft-Decision-1 is an optional assessor, not an action authority. Its source resolves runtime settings through Hermes secret scope; no secrets were read. Any actual plugin install, credential config, API call or policy-gate enablement needs explicit owner approval.
- Core sim remains wholly new, simple, and single-clock. **No physical/scenario code reuse** from Awign or RobotFleet; both have no project-level license evidence. No dependency on A*, CCH, or unverified GraphRAG read-only enforcement.

## Verified repository groups

### Core/source-adapter priority

#### FalkorDB/FalkorDB — `7b7b4d1ed23fe78e69fa5da0c9e4f2ea2e73f3e9`
[https://github.com/FalkorDB/FalkorDB/tree/7b7b4d1ed23fe78e69fa5da0c9e4f2ea2e73f3e9](https://github.com/FalkorDB/FalkorDB/tree/7b7b4d1ed23fe78e69fa5da0c9e4f2ea2e73f3e9) · pin verified: True · root license `LICENSE` (GitHub `NOASSERTION`) · decision `core`.
Primary graph server and canonical authority/evidence graph. Pin v6.0.2; SSPL is source-available, not OSI-approved.
Source paths verified at this exact tree: `src/lib.rs`, `Cargo.toml`, `graph/Cargo.toml`
Code/license details: Root LICENSE text is SSPL v1; server is not OSI-approved. Do not call entire stack FOSS..

#### FalkorDB/falkordb-py — `31f63f44a5745b9bec65969a1db706906718cb82`
[https://github.com/FalkorDB/falkordb-py/tree/31f63f44a5745b9bec65969a1db706906718cb82](https://github.com/FalkorDB/falkordb-py/tree/31f63f44a5745b9bec65969a1db706906718cb82) · pin verified: True · root license `LICENSE` (GitHub `MIT`) · decision `core`.
Official Python client; parameterized queries and explicit read-only retrieval seam.
Source paths verified at this exact tree: `falkordb/falkordb.py`, `falkordb/graph.py`, `pyproject.toml`
Code/license details: license text fetched.

#### FalkorDB/GraphRAG-SDK — `35e67a0b27fdcc7f2c28508b09e86169851a8187`
[https://github.com/FalkorDB/GraphRAG-SDK/tree/35e67a0b27fdcc7f2c28508b09e86169851a8187](https://github.com/FalkorDB/GraphRAG-SDK/tree/35e67a0b27fdcc7f2c28508b09e86169851a8187) · pin verified: True · root license `LICENSE` (GitHub `Apache-2.0`) · decision `core-optional-single-corpus`.
One optional, isolated corpus lane: deterministic TableMapping ingestion and retrieval, never canonical policy authority.
Source paths verified at this exact tree: `graphrag_sdk/src/graphrag_sdk/api/main.py`, `graphrag_sdk/src/graphrag_sdk/ingestion/structured_pipeline.py`, `graphrag_sdk/examples/11_structured_ingestion.py`, `graphrag_sdk/pyproject.toml`
Code/license details: license text fetched.

#### google-deepmind/mujoco — `12720007ea3c98238990190dcba6d93fee0dd4c1`
[https://github.com/google-deepmind/mujoco/tree/12720007ea3c98238990190dcba6d93fee0dd4c1](https://github.com/google-deepmind/mujoco/tree/12720007ea3c98238990190dcba6d93fee0dd4c1) · pin verified: True · root license `LICENSE` (GitHub `Apache-2.0`) · decision `core`.
Original simple 3-robot MJCF simulation and one authoritative clock. No physical code reuse.
Source paths verified at this exact tree: `python/pyproject.toml`, `python/mujoco/__init__.py`, `doc/python.rst`, `doc/programming/index.rst`, `cmake/MujocoMacOS.cmake`
Code/license details: license text fetched.

#### guglxni/ms-decision-provider — `f82d9bf5203496eb8a9ab7a7740a7909ab2c04cc`
[https://github.com/guglxni/ms-decision-provider/tree/f82d9bf5203496eb8a9ab7a7740a7909ab2c04cc](https://github.com/guglxni/ms-decision-provider/tree/f82d9bf5203496eb8a9ab7a7740a7909ab2c04cc) · pin verified: True · root license `LICENSE` (GitHub `MIT`) · decision `core-reference-adapter`.
Candidate Hermes provider for the existing Microsoft-Decision-1 endpoint; configuration and credential setup require explicit approval.
Source paths verified at this exact tree: `provider.py`, `plugin.yaml`, `tests/test_security.py`
Code/license details: license text fetched.

#### typesafe-ai/typesafe-sdk-python — `f36e68549ceca3191e5791e5f99ea1baa1a258b5`
[https://github.com/typesafe-ai/typesafe-sdk-python/tree/f36e68549ceca3191e5791e5f99ea1baa1a258b5](https://github.com/typesafe-ai/typesafe-sdk-python/tree/f36e68549ceca3191e5791e5f99ea1baa1a258b5) · pin verified: True · root license `LICENSE` (GitHub `MIT`) · decision `optional-hosted-client`.
Hosted Jev client for evaluation only; code MIT does not license service/model.
Source paths verified at this exact tree: `src/typesafe_sdk/_core/client/sync/client.py`, `src/typesafe_sdk/_core/client/aio/client.py`, `pyproject.toml`
Code/license details: license text fetched.

#### typesafe-ai/system-one-adapter-python — `e1d4cc938204b22fc5a3c3aca7044072fe3f712d`
[https://github.com/typesafe-ai/system-one-adapter-python/tree/e1d4cc938204b22fc5a3c3aca7044072fe3f712d](https://github.com/typesafe-ai/system-one-adapter-python/tree/e1d4cc938204b22fc5a3c3aca7044072fe3f712d) · pin verified: True · root license `LICENSE` (GitHub `MIT`) · decision `optional-baseline`.
Generative API adapter shaped like System One; not native calibrated inference.
Source paths verified at this exact tree: `src/system_one_adapter/_client.py`, `src/system_one_adapter/providers/openai.py`, `pyproject.toml`
Code/license details: license text fetched.

#### threefruits/HUME — `c9e170887a037863a77d1d549239ad1ff9e7b55a`
[https://github.com/threefruits/HUME/tree/c9e170887a037863a77d1d549239ad1ff9e7b55a](https://github.com/threefruits/HUME/tree/c9e170887a037863a77d1d549239ad1ff9e7b55a) · pin verified: True · root license `LICENSE` (GitHub `MIT`) · decision `research-reference`.
Hypothesis-driven planning concepts only; alpha research code, not a required dependency.
Source paths verified at this exact tree: `hume/planning/block_processing/hypotheses.py`, `hume/planning/block_processing/verification.py`, `hume/planning/model.py`, `pyproject.toml`
Code/license details: license text fetched.

#### daniekpo/verigraph — `5c07fb8f228049e228b53637e3867650f6854fa5`
[https://github.com/daniekpo/verigraph/tree/5c07fb8f228049e228b53637e3867650f6854fa5](https://github.com/daniekpo/verigraph/tree/5c07fb8f228049e228b53637e3867650f6854fa5) · pin verified: True · root license `LICENSE` (GitHub `MIT`) · decision `research-reference`.
Execution-verifiable scene graph planning reference; released repo excludes its real-robot perception/grasp stack.
Source paths verified at this exact tree: `verigraph/core/graph_planner.py`, `verigraph/core/iterative_planner.py`, `verigraph/core/simple_plan_checker.py`, `verigraph/utils/robot_client.py`, `pyproject.toml`
Code/license details: license text fetched.

#### AppliedMachineLearning-Lab/jev-benchmarking — `87562114d23597f610754f057e5e0da8659dbcfb`
[https://github.com/AppliedMachineLearning-Lab/jev-benchmarking/tree/87562114d23597f610754f057e5e0da8659dbcfb](https://github.com/AppliedMachineLearning-Lab/jev-benchmarking/tree/87562114d23597f610754f057e5e0da8659dbcfb) · pin verified: True · root license `LICENSE` (GitHub `MIT`) · decision `optional-evaluation`.
Paper-linked Jev shadow/calibration/evaluation reference; third-party datasets and stored API response data need separate rights review.
Source paths verified at this exact tree: `jev_benchmarking/runner.py`, `jev_benchmarking/evaluate.py`, `jev_benchmarking/metrics.py`, `docs/datasets.md`, `pyproject.toml`
Code/license details: license text fetched.

### Optional / deferred

- **xzx34/JevOut** (`c8ab231728abb54bd61cf3c8812cb48811aae36b`, Apache-2.0): Paper-linked answer-preserving context perturbation evaluation; good bounded robustness test after baseline. Verified seam: `context_optimization/optimize.py`, `context_optimization/evaluate.py`, `context_optimization/repeatability.py`. Model/code rights separate.
- **nokia-applied-research/AnyJev** (`b03158e9ba18e84c01054aaa393481925088db07`, Apache-2.0): Training-free typed probabilities from open LMs. Not model-free: needs checkpoint + inference runtime; Tacit checkpoints are separate assets. Verified seam: `anyjev/decider.py`, `anyjev/readout.py`, `anyjev/calibrate/permute.py`. Model/code rights separate.
- **getzep/graphiti** (`aca369364226a666ca541b061ff2a1a54b80f2ff`, Apache-2.0): Temporal graph memory alternative; defer in favor of direct episode/task persistence. Verified seam: `graphiti_core/driver/falkordb_driver.py`, `examples/quickstart/quickstart_falkordb.py`, `pyproject.toml`. Model/code rights separate.
- **OSU-NLP-Group/HippoRAG** (`d5c8329422e0a0b834a15874545cb6a74b4f9b26`, MIT): Retrieval baseline/reference; inspected code uses igraph, not a FalkorDB backend. Verified seam: `src/hipporag/HippoRAG.py`, `src/hipporag/embedding_store.py`, `pyproject.toml`. Model/code rights separate.
- **AIRI-Institute/AriGraph** (`e884b76d7fa5185a3a8a55e5a67393b5a43f5ef2`, MIT): Semantic/episodic research reference, not a verified FalkorDB adapter. Verified seam: `pipeline_arigraph.py`, `graphs/contriever_graph.py`, `graphs/hypergraph.py`. Model/code rights separate.
- **docling-project/docling** (`6fadbae317b09c4dd4051c0f1fc1746c6baf04bc`, MIT): Add only if PDFs/layout parsing are needed; model downloads and runtime assets have separate terms. Verified seam: `docling/document_converter.py`, `packages/docling/pyproject.toml`, `docs/getting_started/quickstart.md`. Model/code rights separate.
- **langchain-ai/langgraph** (`5eb60aef6f3837a1fb632a8abc6cf8e8da81785b`, MIT): Workflow/checkpoint option only if a canonical graph state machine is insufficient. Verified seam: `libs/langgraph/pyproject.toml`, `libs/checkpoint-sqlite/pyproject.toml`, `LICENSE`. Model/code rights separate.
- **splintered-reality/py_trees** (`41ec377108b3786f2cfe529facb0566332691766`, NOASSERTION): Behavior-tree primitives only; root text/manifest say BSD-3-Clause while GitHub reports NOASSERTION. Verified seam: `py_trees/trees.py`, `py_trees/behaviour.py`, `pyproject.toml`. Model/code rights separate.
- **open-policy-agent/opa** (`89d111ce4b45c3af9b79ac1137efe2e9aab6cc92`, Apache-2.0): Policy engine if rule complexity warrants it; first use a small deterministic evaluator. Verified seam: `server/server.go`, `v1/server/server.go`, `go.mod`. Model/code rights separate.
- **NandhaKishorM/laya** (`432312b36714d8889eba405507b37eda25257d9c`, Apache-2.0): Local typed decision model comparison; package Apache-2.0, checkpoint/data licensing separate. Verified seam: `examples/02_hello_world_decision.py`, `examples/34_calibration_temperature.py`, `pyproject.toml`. Model/code rights separate.
- **strands-labs/strands-decider** (`6039cf8b64c6074e75804000c07ac3d4cce795f7`, Apache-2.0): Local decision model comparison; Apple MLX extra exists, but defer inference from critical path; weights separate. Verified seam: `src/strands_decider/server.py`, `src/strands_decider/cli.py`, `src/strands_decider/mlx_engine.py`. Model/code rights separate.

### Reference-only, not reuse-cleared

- **Jovian-Dsouza/awign-hackathon-2026** (`8adb8792204a12634b1a80f9824eebf4e5f9e993`): No root LICENSE path; only a nested SO-101 third-party LICENSE. GitHub license is null; reference only absent clearance.
- **therohangupta/robot-fleet** (`67c5f724727bf25d4955fedbfb1fd63f8ec29914`): No root LICENSE path and GitHub license is null despite the paper claim. Do not copy code without clarification.

## Candidate evaluation plan

Priority for a bounded evaluator after core telemetry and baselines exist:

1. **Jev shadow/calibration benchmarking** — `AppliedMachineLearning-Lab/jev-benchmarking` (paper arXiv:2609.37647v1), MIT code. Treat its benchmark scripts, 37-task suite and stored responses as research material, not a requirement to run every benchmark or redistribute those dataset/API records. A hosted Jev account/model is proprietary and service access/cost are separate.
2. **Answer-preserving context robustness** — `xzx34/JevOut` (arXiv:2609.30243v2), Apache-2.0 code. Start with a small synthetic adversarial test set that asks whether injected natural-looking context can flip a bounded assessor. Preserve the correct answer and measure change/targeted flip; do not expose safety authority or real private documents to an optimizer. Its no-key synthetic demo is documented; no demo or model run occurred in this audit.
3. **Optional probability baseline** — `nokia-applied-research/AnyJev` (arXiv:2610.00831), Apache-2.0 code. Separate methods: training-free `Decider` uses any open causal LM with permutation/rotation adjustments and probability readout; `Tacit` uses separately released self-distilled model checkpoints, sometimes with bounded reasoning escalation. **No training needed does not mean model-free.** Pin checkpoint and inference backend, review their licenses/data, disclose hardware, and compare identical states/options. Do not report upstream numbers as project measurements.
4. Compare deterministic graph-only routing/ranking first, then optional Microsoft Decision-1, then the above only if access/runtime are explicitly approved. Keep evidence candidates, question definitions, policy versions and deadlines fixed. Log distributions, status/refusal/timeout, model revision, latency, input hash and escalation; preserve abstain/failure states.

No Jev inference, hosted API request, paid benchmark, data download, calibration exercise or perturbation experiment was performed. All cited benchmark numbers belong to upstream paper/repo claims and require checking original sources before use.

## Dependency and integration boundaries

- **GraphRAG SDK is a corpus assistant, not a system-of-record policy model.** The verified tree includes `graphrag_sdk/src/graphrag_sdk/ingestion/structured_pipeline.py` and `graphrag_sdk/examples/11_structured_ingestion.py`. Structured rows are deterministic, but its main package facade also depends on LLM/embedding provider interfaces and the `finalize` lifecycle. Do not expose raw query, allow a source update to delete audit history, or join different named graphs as though one transaction/traversal existed.
- `FalkorDB/falkordb-py` latest audit HEAD declares redis-py 8.x compatibility boundaries. Treat exact server/client/dependency matching as unverified until parent does an isolated resolver and smoke query; no dependencies installed here.
- TypeSafe SDK and `system-one-adapter-python` are separate MIT packages. The adapter uses generative APIs to synthesize/normalize decision-style responses, so it is a structured-generation baseline, not native probability semantics. Earlier deep dive called out openai SDK upper-bound conflict between GraphRAG optional OpenAI extra and current SDK; isolate provider environments or use a minimal HTTP adapter rather than merging dependencies on assumption.
- `getzep/graphiti` has a real `graphiti_core/driver/falkordb_driver.py` and Falkor quickstart, but Graphiti adds temporal inference and another lifecycle; defer rather than stack with SDK on the first path.
- HippoRAG source (`src/hipporag/HippoRAG.py`) uses a separate retrieval graph stack (`python_igraph` in manifest); use only as a later baseline/port, not a URL-swapped FalkorDB integration.
- LangGraph’s verified repo is a Python monorepo; the separate SQLite saver manifest demonstrates a real saver but adds a second state store. Keep canonical task/action ledger in FalkorDB first.
- OPA, py_trees and Docling are optional capabilities, not first-build dependencies. Use Docling only when real PDF layout matters; start synthetic Markdown/JSON.

## Repeatable pin discipline

For every repo in `REPOSITORIES.md`, use the exact sequence (substitute path literal SHA):

```bash
gh repo clone OWNER/REPO -- --filter=blob:none --no-checkout
cd REPO
git fetch origin FULL_SHA
git checkout --detach FULL_SHA
test "$(git rev-parse HEAD)" = "FULL_SHA"
```

The full SHA is in `repository-manifest.json`. For several repos, clone into explicitly named sibling directories to avoid `cd` ambiguity. The upstream examples below may still say `pip install`/`latest`—that is how upstream documents usage, not a reproducible project lock. Parent implementation should choose exact package versions and record them in its lockfile after compatibility tests.

## Open blockers / not verified

- No installs, lock resolution, build, tests, queries, HTTP requests to model vendors, inference, physical sim, or app startup occurred. The `usage_commands` field records upstream/documented commands and is **not evidence those commands worked locally**.
- No root license for Awign/RobotFleet means stop code/assets reuse pending permission. Repo-level MIT/Apache does not guarantee third-party models, robot mesh/artwork, datasets, cached responses, or dependencies are clear.
- MuJoCo arm64 readiness is source documentation evidence; still needs the authoring Mac’s supported macOS/Python wheel availability and small import/headless-step test at implementation time. Viewer integration separately uses `mjpython` on macOS.
- GitHub metadata pins are immutable and trees complete, but default-branch pins are a dated audit sample, not releases. Prefer an upstream release tag where there is one; otherwise commit pin plus license review.
- No guarantee raw GraphRAG `query()` is read-only. No AStar/CCH dependency. No current official support or operational health is implied by an inspected GitHub repository.

## Evidence artifacts

- [`repository-manifest.json`](../evidence/repository-manifest.json): 23-repository structured inventory; commit/tree/path/license status, exact source paths, usage commands, separate code/model/data licensing notes. The companion `../evidence/repository-manifest-full.json` embeds full recursive tree blob paths; the checked inventory has 23/23 identities, pins and untruncated trees, and 21/23 root license texts fetched (the two deliberately missing-license references have none).
- [`REPOSITORIES.md`](../REPOSITORIES.md): clone recipes, all verified repository pins/paths and license cautions.
- Supplied prior research: `../falkordb-systemone-20261015/deep-dive.md`, `../falkordb-systemone-20261015/sdk/report.md`, `../graphhacks-alltracks-20261015/all-track-research-and-enhancements.md`. The deep-dive recommendation supersedes older Graphiti-first broad stack choices; no integration has actually been installed.
