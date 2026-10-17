# Verified GitHub repositories and selective checkout recipes

**Audit date: 15 October 2026.** 23 distinct canonical repositories and full commit pins were verified with `gh`; the parent independently rechecked every exact commit. Recursive source trees and license-file paths were inspected by the repository specialist and validated against the retained manifest. This is **source/link verification**, not installed/running integration or license clearance for model weights/data.

## Clone only what the current gate needs

Recommended inspection checkouts for the first build: FalkorDB/falkordb-py, FalkorDB/GraphRAG-SDK, google-deepmind/mujoco, and the Microsoft adapter reference. FalkorDB server source is useful for version-sensitive behavior; use a separately verified pinned Docker image rather than building the server unnecessarily. HUME/VeriGraph and model-evaluation repositories are read-only research references. All others remain optional/deferred.

Never run a blanket install/clone-all script. Paths below use distinct repository-local `.research/vendor/` directories, not live Hermes plugins. Cloning is not installing. After checkout inspect upstream README, LICENSE and package manifest, then follow INTEGRATIONS.md. Full pins and provenance are in [repository-manifest.json](evidence/repository-manifest.json); full tree evidence is in [repository-manifest-full.json](evidence/repository-manifest-full.json).

| Repository | Placement | Code-license interpretation | Selected source seams |
|---|---|---|---|
| [FalkorDB/FalkorDB](https://github.com/FalkorDB/FalkorDB) | core | SSPL v1 (source-available, not OSI open source) | `src/lib.rs`, `Cargo.toml`, `graph/Cargo.toml` |
| [FalkorDB/falkordb-py](https://github.com/FalkorDB/falkordb-py) | core | MIT | `falkordb/falkordb.py`, `falkordb/graph.py`, `pyproject.toml` |
| [FalkorDB/GraphRAG-SDK](https://github.com/FalkorDB/GraphRAG-SDK) | Selected narrow integration; disclosed fallback if blocked | Apache-2.0 | `graphrag_sdk/src/graphrag_sdk/api/main.py`, `graphrag_sdk/src/graphrag_sdk/ingestion/structured_pipeline.py`, `graphrag_sdk/examples/11_structured_ingestion.py` |
| [google-deepmind/mujoco](https://github.com/google-deepmind/mujoco) | core | Apache-2.0 | `python/pyproject.toml`, `python/mujoco/__init__.py`, `doc/python.rst` |
| [guglxni/ms-decision-provider](https://github.com/guglxni/ms-decision-provider) | core-reference-adapter | MIT | `provider.py`, `plugin.yaml`, `tests/test_security.py` |
| [typesafe-ai/typesafe-sdk-python](https://github.com/typesafe-ai/typesafe-sdk-python) | optional-hosted-client | MIT | `src/typesafe_sdk/_core/client/sync/client.py`, `src/typesafe_sdk/_core/client/aio/client.py`, `pyproject.toml` |
| [typesafe-ai/system-one-adapter-python](https://github.com/typesafe-ai/system-one-adapter-python) | optional-baseline | MIT | `src/system_one_adapter/_client.py`, `src/system_one_adapter/providers/openai.py`, `pyproject.toml` |
| [threefruits/HUME](https://github.com/threefruits/HUME) | research-reference | MIT | `hume/planning/block_processing/hypotheses.py`, `hume/planning/block_processing/verification.py`, `hume/planning/model.py` |
| [daniekpo/verigraph](https://github.com/daniekpo/verigraph) | research-reference | MIT | `verigraph/core/graph_planner.py`, `verigraph/core/iterative_planner.py`, `verigraph/core/simple_plan_checker.py` |
| [getzep/graphiti](https://github.com/getzep/graphiti) | deferred | Apache-2.0 | `graphiti_core/driver/falkordb_driver.py`, `examples/quickstart/quickstart_falkordb.py`, `pyproject.toml` |
| [OSU-NLP-Group/HippoRAG](https://github.com/OSU-NLP-Group/HippoRAG) | deferred | MIT | `src/hipporag/HippoRAG.py`, `src/hipporag/embedding_store.py`, `pyproject.toml` |
| [AIRI-Institute/AriGraph](https://github.com/AIRI-Institute/AriGraph) | deferred | MIT | `pipeline_arigraph.py`, `graphs/contriever_graph.py`, `graphs/hypergraph.py` |
| [docling-project/docling](https://github.com/docling-project/docling) | deferred | MIT | `docling/document_converter.py`, `packages/docling/pyproject.toml`, `docs/getting_started/quickstart.md` |
| [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) | deferred | MIT | `libs/langgraph/pyproject.toml`, `libs/checkpoint-sqlite/pyproject.toml`, `LICENSE` |
| [splintered-reality/py_trees](https://github.com/splintered-reality/py_trees) | deferred | BSD-3-Clause text (GitHub NOASSERTION) | `py_trees/trees.py`, `py_trees/behaviour.py`, `pyproject.toml` |
| [open-policy-agent/opa](https://github.com/open-policy-agent/opa) | deferred | Apache-2.0 | `server/server.go`, `v1/server/server.go`, `go.mod` |
| [NandhaKishorM/laya](https://github.com/NandhaKishorM/laya) | deferred-local-model | Apache-2.0 | `examples/02_hello_world_decision.py`, `examples/34_calibration_temperature.py`, `pyproject.toml` |
| [strands-labs/strands-decider](https://github.com/strands-labs/strands-decider) | deferred-local-model | Apache-2.0 | `src/strands_decider/server.py`, `src/strands_decider/cli.py`, `src/strands_decider/mlx_engine.py` |
| [Jovian-Dsouza/awign-hackathon-2026](https://github.com/Jovian-Dsouza/awign-hackathon-2026) | reference-only-no-reuse | No root license found; no reuse | `robot-sim/src/dsr_sim/world.py`, `robot-sim/src/dsr_sim/run.py`, `robot-sim/pyproject.toml` |
| [therohangupta/robot-fleet](https://github.com/therohangupta/robot-fleet) | reference-only-no-reuse | No root license found; no reuse | `robot_fleet/server/__main__.py`, `robot_fleet/cli/robotctl.py`, `pyproject.toml` |
| [AppliedMachineLearning-Lab/jev-benchmarking](https://github.com/AppliedMachineLearning-Lab/jev-benchmarking) | optional-evaluation | MIT | `jev_benchmarking/runner.py`, `jev_benchmarking/evaluate.py`, `jev_benchmarking/metrics.py` |
| [xzx34/JevOut](https://github.com/xzx34/JevOut) | optional-evaluation | Apache-2.0 | `context_optimization/optimize.py`, `context_optimization/evaluate.py`, `context_optimization/repeatability.py` |
| [nokia-applied-research/AnyJev](https://github.com/nokia-applied-research/AnyJev) | optional-probability-baseline | Apache-2.0 | `anyjev/decider.py`, `anyjev/readout.py`, `anyjev/calibrate/permute.py` |

## Exact independent checkout recipes

Run from the project root only when that repository is needed. The target directory must not already exist; do not overwrite an existing checkout. `git fetch`/checkout must succeed and the final SHA equality check must pass. Do not install all extras from a research repository.

### FalkorDB/FalkorDB

Primary graph server and canonical authority/evidence graph. Pin v6.0.2; SSPL is source-available, not OSI-approved.

Verified pin: [7b7b4d1ed23fe78e69fa5da0c9e4f2ea2e73f3e9](https://github.com/FalkorDB/FalkorDB/commit/7b7b4d1ed23fe78e69fa5da0c9e4f2ea2e73f3e9).

```bash
gh repo clone FalkorDB/FalkorDB .research/vendor/FalkorDB--FalkorDB -- --filter=blob:none --no-checkout
git -C .research/vendor/FalkorDB--FalkorDB fetch origin 7b7b4d1ed23fe78e69fa5da0c9e4f2ea2e73f3e9
git -C .research/vendor/FalkorDB--FalkorDB checkout --detach 7b7b4d1ed23fe78e69fa5da0c9e4f2ea2e73f3e9
test "$(git -C .research/vendor/FalkorDB--FalkorDB rev-parse HEAD)" = "7b7b4d1ed23fe78e69fa5da0c9e4f2ea2e73f3e9"
```

License text: [LICENSE](https://github.com/FalkorDB/FalkorDB/blob/7b7b4d1ed23fe78e69fa5da0c9e4f2ea2e73f3e9/LICENSE). Root LICENSE text is SSPL v1; server is not OSI-approved. Do not call entire stack FOSS.

### FalkorDB/falkordb-py

Official Python client; parameterized queries and explicit read-only retrieval seam.

Verified pin: [31f63f44a5745b9bec65969a1db706906718cb82](https://github.com/FalkorDB/falkordb-py/commit/31f63f44a5745b9bec65969a1db706906718cb82).

```bash
gh repo clone FalkorDB/falkordb-py .research/vendor/FalkorDB--falkordb-py -- --filter=blob:none --no-checkout
git -C .research/vendor/FalkorDB--falkordb-py fetch origin 31f63f44a5745b9bec65969a1db706906718cb82
git -C .research/vendor/FalkorDB--falkordb-py checkout --detach 31f63f44a5745b9bec65969a1db706906718cb82
test "$(git -C .research/vendor/FalkorDB--falkordb-py rev-parse HEAD)" = "31f63f44a5745b9bec65969a1db706906718cb82"
```

License text: [LICENSE](https://github.com/FalkorDB/falkordb-py/blob/31f63f44a5745b9bec65969a1db706906718cb82/LICENSE). 

### FalkorDB/GraphRAG-SDK

One optional, isolated corpus lane: deterministic TableMapping ingestion and retrieval, never canonical policy authority.

Verified pin: [35e67a0b27fdcc7f2c28508b09e86169851a8187](https://github.com/FalkorDB/GraphRAG-SDK/commit/35e67a0b27fdcc7f2c28508b09e86169851a8187).

```bash
gh repo clone FalkorDB/GraphRAG-SDK .research/vendor/FalkorDB--GraphRAG-SDK -- --filter=blob:none --no-checkout
git -C .research/vendor/FalkorDB--GraphRAG-SDK fetch origin 35e67a0b27fdcc7f2c28508b09e86169851a8187
git -C .research/vendor/FalkorDB--GraphRAG-SDK checkout --detach 35e67a0b27fdcc7f2c28508b09e86169851a8187
test "$(git -C .research/vendor/FalkorDB--GraphRAG-SDK rev-parse HEAD)" = "35e67a0b27fdcc7f2c28508b09e86169851a8187"
```

License text: [LICENSE](https://github.com/FalkorDB/GraphRAG-SDK/blob/35e67a0b27fdcc7f2c28508b09e86169851a8187/LICENSE). 

### google-deepmind/mujoco

Original simple 3-robot MJCF simulation and one authoritative clock. No physical code reuse.

Verified pin: [12720007ea3c98238990190dcba6d93fee0dd4c1](https://github.com/google-deepmind/mujoco/commit/12720007ea3c98238990190dcba6d93fee0dd4c1).

```bash
gh repo clone google-deepmind/mujoco .research/vendor/google-deepmind--mujoco -- --filter=blob:none --no-checkout
git -C .research/vendor/google-deepmind--mujoco fetch origin 12720007ea3c98238990190dcba6d93fee0dd4c1
git -C .research/vendor/google-deepmind--mujoco checkout --detach 12720007ea3c98238990190dcba6d93fee0dd4c1
test "$(git -C .research/vendor/google-deepmind--mujoco rev-parse HEAD)" = "12720007ea3c98238990190dcba6d93fee0dd4c1"
```

License text: [LICENSE](https://github.com/google-deepmind/mujoco/blob/12720007ea3c98238990190dcba6d93fee0dd4c1/LICENSE). 

### guglxni/ms-decision-provider

Read-only reference for Microsoft-Decision-1 transport/validation and evaluation patterns. The fleet implements its own minimal adapter; this does not require installing/modifying a Hermes plugin. Provider access and configuration are separately authorized.

Verified pin: [f82d9bf5203496eb8a9ab7a7740a7909ab2c04cc](https://github.com/guglxni/ms-decision-provider/commit/f82d9bf5203496eb8a9ab7a7740a7909ab2c04cc).

```bash
gh repo clone guglxni/ms-decision-provider .research/vendor/guglxni--ms-decision-provider -- --filter=blob:none --no-checkout
git -C .research/vendor/guglxni--ms-decision-provider fetch origin f82d9bf5203496eb8a9ab7a7740a7909ab2c04cc
git -C .research/vendor/guglxni--ms-decision-provider checkout --detach f82d9bf5203496eb8a9ab7a7740a7909ab2c04cc
test "$(git -C .research/vendor/guglxni--ms-decision-provider rev-parse HEAD)" = "f82d9bf5203496eb8a9ab7a7740a7909ab2c04cc"
```

License text: [LICENSE](https://github.com/guglxni/ms-decision-provider/blob/f82d9bf5203496eb8a9ab7a7740a7909ab2c04cc/LICENSE). 

### typesafe-ai/typesafe-sdk-python

Hosted Jev client for evaluation only; code MIT does not license service/model.

Verified pin: [f36e68549ceca3191e5791e5f99ea1baa1a258b5](https://github.com/typesafe-ai/typesafe-sdk-python/commit/f36e68549ceca3191e5791e5f99ea1baa1a258b5).

```bash
gh repo clone typesafe-ai/typesafe-sdk-python .research/vendor/typesafe-ai--typesafe-sdk-python -- --filter=blob:none --no-checkout
git -C .research/vendor/typesafe-ai--typesafe-sdk-python fetch origin f36e68549ceca3191e5791e5f99ea1baa1a258b5
git -C .research/vendor/typesafe-ai--typesafe-sdk-python checkout --detach f36e68549ceca3191e5791e5f99ea1baa1a258b5
test "$(git -C .research/vendor/typesafe-ai--typesafe-sdk-python rev-parse HEAD)" = "f36e68549ceca3191e5791e5f99ea1baa1a258b5"
```

License text: [LICENSE](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f36e68549ceca3191e5791e5f99ea1baa1a258b5/LICENSE). 

### typesafe-ai/system-one-adapter-python

Generative API adapter shaped like System One; not native calibrated inference.

Verified pin: [e1d4cc938204b22fc5a3c3aca7044072fe3f712d](https://github.com/typesafe-ai/system-one-adapter-python/commit/e1d4cc938204b22fc5a3c3aca7044072fe3f712d).

```bash
gh repo clone typesafe-ai/system-one-adapter-python .research/vendor/typesafe-ai--system-one-adapter-python -- --filter=blob:none --no-checkout
git -C .research/vendor/typesafe-ai--system-one-adapter-python fetch origin e1d4cc938204b22fc5a3c3aca7044072fe3f712d
git -C .research/vendor/typesafe-ai--system-one-adapter-python checkout --detach e1d4cc938204b22fc5a3c3aca7044072fe3f712d
test "$(git -C .research/vendor/typesafe-ai--system-one-adapter-python rev-parse HEAD)" = "e1d4cc938204b22fc5a3c3aca7044072fe3f712d"
```

License text: [LICENSE](https://github.com/typesafe-ai/system-one-adapter-python/blob/e1d4cc938204b22fc5a3c3aca7044072fe3f712d/LICENSE). 

### threefruits/HUME

Hypothesis-driven planning concepts only; alpha research code, not a required dependency.

Verified pin: [c9e170887a037863a77d1d549239ad1ff9e7b55a](https://github.com/threefruits/HUME/commit/c9e170887a037863a77d1d549239ad1ff9e7b55a).

```bash
gh repo clone threefruits/HUME .research/vendor/threefruits--HUME -- --filter=blob:none --no-checkout
git -C .research/vendor/threefruits--HUME fetch origin c9e170887a037863a77d1d549239ad1ff9e7b55a
git -C .research/vendor/threefruits--HUME checkout --detach c9e170887a037863a77d1d549239ad1ff9e7b55a
test "$(git -C .research/vendor/threefruits--HUME rev-parse HEAD)" = "c9e170887a037863a77d1d549239ad1ff9e7b55a"
```

License text: [LICENSE](https://github.com/threefruits/HUME/blob/c9e170887a037863a77d1d549239ad1ff9e7b55a/LICENSE). 

### daniekpo/verigraph

Execution-verifiable scene graph planning reference; released repo excludes its real-robot perception/grasp stack.

Verified pin: [5c07fb8f228049e228b53637e3867650f6854fa5](https://github.com/daniekpo/verigraph/commit/5c07fb8f228049e228b53637e3867650f6854fa5).

```bash
gh repo clone daniekpo/verigraph .research/vendor/daniekpo--verigraph -- --filter=blob:none --no-checkout
git -C .research/vendor/daniekpo--verigraph fetch origin 5c07fb8f228049e228b53637e3867650f6854fa5
git -C .research/vendor/daniekpo--verigraph checkout --detach 5c07fb8f228049e228b53637e3867650f6854fa5
test "$(git -C .research/vendor/daniekpo--verigraph rev-parse HEAD)" = "5c07fb8f228049e228b53637e3867650f6854fa5"
```

License text: [LICENSE](https://github.com/daniekpo/verigraph/blob/5c07fb8f228049e228b53637e3867650f6854fa5/LICENSE). 

### getzep/graphiti

Temporal graph memory alternative; defer in favor of direct episode/task persistence.

Verified pin: [aca369364226a666ca541b061ff2a1a54b80f2ff](https://github.com/getzep/graphiti/commit/aca369364226a666ca541b061ff2a1a54b80f2ff).

```bash
gh repo clone getzep/graphiti .research/vendor/getzep--graphiti -- --filter=blob:none --no-checkout
git -C .research/vendor/getzep--graphiti fetch origin aca369364226a666ca541b061ff2a1a54b80f2ff
git -C .research/vendor/getzep--graphiti checkout --detach aca369364226a666ca541b061ff2a1a54b80f2ff
test "$(git -C .research/vendor/getzep--graphiti rev-parse HEAD)" = "aca369364226a666ca541b061ff2a1a54b80f2ff"
```

License text: [LICENSE](https://github.com/getzep/graphiti/blob/aca369364226a666ca541b061ff2a1a54b80f2ff/LICENSE). 

### OSU-NLP-Group/HippoRAG

Retrieval baseline/reference; inspected code uses igraph, not a FalkorDB backend.

Verified pin: [d5c8329422e0a0b834a15874545cb6a74b4f9b26](https://github.com/OSU-NLP-Group/HippoRAG/commit/d5c8329422e0a0b834a15874545cb6a74b4f9b26).

```bash
gh repo clone OSU-NLP-Group/HippoRAG .research/vendor/OSU-NLP-Group--HippoRAG -- --filter=blob:none --no-checkout
git -C .research/vendor/OSU-NLP-Group--HippoRAG fetch origin d5c8329422e0a0b834a15874545cb6a74b4f9b26
git -C .research/vendor/OSU-NLP-Group--HippoRAG checkout --detach d5c8329422e0a0b834a15874545cb6a74b4f9b26
test "$(git -C .research/vendor/OSU-NLP-Group--HippoRAG rev-parse HEAD)" = "d5c8329422e0a0b834a15874545cb6a74b4f9b26"
```

License text: [LICENSE](https://github.com/OSU-NLP-Group/HippoRAG/blob/d5c8329422e0a0b834a15874545cb6a74b4f9b26/LICENSE). 

### AIRI-Institute/AriGraph

Semantic/episodic research reference, not a verified FalkorDB adapter.

Verified pin: [e884b76d7fa5185a3a8a55e5a67393b5a43f5ef2](https://github.com/AIRI-Institute/AriGraph/commit/e884b76d7fa5185a3a8a55e5a67393b5a43f5ef2).

```bash
gh repo clone AIRI-Institute/AriGraph .research/vendor/AIRI-Institute--AriGraph -- --filter=blob:none --no-checkout
git -C .research/vendor/AIRI-Institute--AriGraph fetch origin e884b76d7fa5185a3a8a55e5a67393b5a43f5ef2
git -C .research/vendor/AIRI-Institute--AriGraph checkout --detach e884b76d7fa5185a3a8a55e5a67393b5a43f5ef2
test "$(git -C .research/vendor/AIRI-Institute--AriGraph rev-parse HEAD)" = "e884b76d7fa5185a3a8a55e5a67393b5a43f5ef2"
```

License text: [LICENSE](https://github.com/AIRI-Institute/AriGraph/blob/e884b76d7fa5185a3a8a55e5a67393b5a43f5ef2/LICENSE). 

### docling-project/docling

Add only if PDFs/layout parsing are needed; model downloads and runtime assets have separate terms.

Verified pin: [6fadbae317b09c4dd4051c0f1fc1746c6baf04bc](https://github.com/docling-project/docling/commit/6fadbae317b09c4dd4051c0f1fc1746c6baf04bc).

```bash
gh repo clone docling-project/docling .research/vendor/docling-project--docling -- --filter=blob:none --no-checkout
git -C .research/vendor/docling-project--docling fetch origin 6fadbae317b09c4dd4051c0f1fc1746c6baf04bc
git -C .research/vendor/docling-project--docling checkout --detach 6fadbae317b09c4dd4051c0f1fc1746c6baf04bc
test "$(git -C .research/vendor/docling-project--docling rev-parse HEAD)" = "6fadbae317b09c4dd4051c0f1fc1746c6baf04bc"
```

License text: [LICENSE](https://github.com/docling-project/docling/blob/6fadbae317b09c4dd4051c0f1fc1746c6baf04bc/LICENSE). 

### langchain-ai/langgraph

Workflow/checkpoint option only if a canonical graph state machine is insufficient.

Verified pin: [5eb60aef6f3837a1fb632a8abc6cf8e8da81785b](https://github.com/langchain-ai/langgraph/commit/5eb60aef6f3837a1fb632a8abc6cf8e8da81785b).

```bash
gh repo clone langchain-ai/langgraph .research/vendor/langchain-ai--langgraph -- --filter=blob:none --no-checkout
git -C .research/vendor/langchain-ai--langgraph fetch origin 5eb60aef6f3837a1fb632a8abc6cf8e8da81785b
git -C .research/vendor/langchain-ai--langgraph checkout --detach 5eb60aef6f3837a1fb632a8abc6cf8e8da81785b
test "$(git -C .research/vendor/langchain-ai--langgraph rev-parse HEAD)" = "5eb60aef6f3837a1fb632a8abc6cf8e8da81785b"
```

License text: [LICENSE](https://github.com/langchain-ai/langgraph/blob/5eb60aef6f3837a1fb632a8abc6cf8e8da81785b/LICENSE). 

### splintered-reality/py_trees

Behavior-tree primitives only; root text/manifest say BSD-3-Clause while GitHub reports NOASSERTION.

Verified pin: [41ec377108b3786f2cfe529facb0566332691766](https://github.com/splintered-reality/py_trees/commit/41ec377108b3786f2cfe529facb0566332691766).

```bash
gh repo clone splintered-reality/py_trees .research/vendor/splintered-reality--py_trees -- --filter=blob:none --no-checkout
git -C .research/vendor/splintered-reality--py_trees fetch origin 41ec377108b3786f2cfe529facb0566332691766
git -C .research/vendor/splintered-reality--py_trees checkout --detach 41ec377108b3786f2cfe529facb0566332691766
test "$(git -C .research/vendor/splintered-reality--py_trees rev-parse HEAD)" = "41ec377108b3786f2cfe529facb0566332691766"
```

License text: [LICENSE](https://github.com/splintered-reality/py_trees/blob/41ec377108b3786f2cfe529facb0566332691766/LICENSE). GitHub SPDX NOASSERTION; pinned root LICENSE text and pyproject declare BSD-3-Clause.

### open-policy-agent/opa

Policy engine if rule complexity warrants it; first use a small deterministic evaluator.

Verified pin: [89d111ce4b45c3af9b79ac1137efe2e9aab6cc92](https://github.com/open-policy-agent/opa/commit/89d111ce4b45c3af9b79ac1137efe2e9aab6cc92).

```bash
gh repo clone open-policy-agent/opa .research/vendor/open-policy-agent--opa -- --filter=blob:none --no-checkout
git -C .research/vendor/open-policy-agent--opa fetch origin 89d111ce4b45c3af9b79ac1137efe2e9aab6cc92
git -C .research/vendor/open-policy-agent--opa checkout --detach 89d111ce4b45c3af9b79ac1137efe2e9aab6cc92
test "$(git -C .research/vendor/open-policy-agent--opa rev-parse HEAD)" = "89d111ce4b45c3af9b79ac1137efe2e9aab6cc92"
```

License text: [LICENSE](https://github.com/open-policy-agent/opa/blob/89d111ce4b45c3af9b79ac1137efe2e9aab6cc92/LICENSE). 

### NandhaKishorM/laya

Local typed decision model comparison; package Apache-2.0, checkpoint/data licensing separate.

Verified pin: [432312b36714d8889eba405507b37eda25257d9c](https://github.com/NandhaKishorM/laya/commit/432312b36714d8889eba405507b37eda25257d9c).

```bash
gh repo clone NandhaKishorM/laya .research/vendor/NandhaKishorM--laya -- --filter=blob:none --no-checkout
git -C .research/vendor/NandhaKishorM--laya fetch origin 432312b36714d8889eba405507b37eda25257d9c
git -C .research/vendor/NandhaKishorM--laya checkout --detach 432312b36714d8889eba405507b37eda25257d9c
test "$(git -C .research/vendor/NandhaKishorM--laya rev-parse HEAD)" = "432312b36714d8889eba405507b37eda25257d9c"
```

License text: [LICENSE](https://github.com/NandhaKishorM/laya/blob/432312b36714d8889eba405507b37eda25257d9c/LICENSE). 

### strands-labs/strands-decider

Local decision model comparison; Apple MLX extra exists, but defer inference from critical path; weights separate.

Verified pin: [6039cf8b64c6074e75804000c07ac3d4cce795f7](https://github.com/strands-labs/strands-decider/commit/6039cf8b64c6074e75804000c07ac3d4cce795f7).

```bash
gh repo clone strands-labs/strands-decider .research/vendor/strands-labs--strands-decider -- --filter=blob:none --no-checkout
git -C .research/vendor/strands-labs--strands-decider fetch origin 6039cf8b64c6074e75804000c07ac3d4cce795f7
git -C .research/vendor/strands-labs--strands-decider checkout --detach 6039cf8b64c6074e75804000c07ac3d4cce795f7
test "$(git -C .research/vendor/strands-labs--strands-decider rev-parse HEAD)" = "6039cf8b64c6074e75804000c07ac3d4cce795f7"
```

License text: [LICENSE](https://github.com/strands-labs/strands-decider/blob/6039cf8b64c6074e75804000c07ac3d4cce795f7/LICENSE). 

### Jovian-Dsouza/awign-hackathon-2026

No root LICENSE path and GitHub license null. Only nested SO-101 asset LICENSE; reference only absent clearance.

Verified pin: [8adb8792204a12634b1a80f9824eebf4e5f9e993](https://github.com/Jovian-Dsouza/awign-hackathon-2026/commit/8adb8792204a12634b1a80f9824eebf4e5f9e993).

```bash
gh repo clone Jovian-Dsouza/awign-hackathon-2026 .research/vendor/Jovian-Dsouza--awign-hackathon-2026 -- --filter=blob:none --no-checkout
git -C .research/vendor/Jovian-Dsouza--awign-hackathon-2026 fetch origin 8adb8792204a12634b1a80f9824eebf4e5f9e993
git -C .research/vendor/Jovian-Dsouza--awign-hackathon-2026 checkout --detach 8adb8792204a12634b1a80f9824eebf4e5f9e993
test "$(git -C .research/vendor/Jovian-Dsouza--awign-hackathon-2026 rev-parse HEAD)" = "8adb8792204a12634b1a80f9824eebf4e5f9e993"
```

**No root license located at this pin. Reference-only; do not adapt/redistribute without permission.**

### therohangupta/robot-fleet

No root LICENSE path and GitHub license null despite paper claim; do not copy code without clarification.

Verified pin: [67c5f724727bf25d4955fedbfb1fd63f8ec29914](https://github.com/therohangupta/robot-fleet/commit/67c5f724727bf25d4955fedbfb1fd63f8ec29914).

```bash
gh repo clone therohangupta/robot-fleet .research/vendor/therohangupta--robot-fleet -- --filter=blob:none --no-checkout
git -C .research/vendor/therohangupta--robot-fleet fetch origin 67c5f724727bf25d4955fedbfb1fd63f8ec29914
git -C .research/vendor/therohangupta--robot-fleet checkout --detach 67c5f724727bf25d4955fedbfb1fd63f8ec29914
test "$(git -C .research/vendor/therohangupta--robot-fleet rev-parse HEAD)" = "67c5f724727bf25d4955fedbfb1fd63f8ec29914"
```

**No root license located at this pin. Reference-only; do not adapt/redistribute without permission.**

### AppliedMachineLearning-Lab/jev-benchmarking

Paper-linked Jev shadow/calibration/evaluation reference; third-party datasets and stored API response data need separate rights review.

Verified pin: [87562114d23597f610754f057e5e0da8659dbcfb](https://github.com/AppliedMachineLearning-Lab/jev-benchmarking/commit/87562114d23597f610754f057e5e0da8659dbcfb).

```bash
gh repo clone AppliedMachineLearning-Lab/jev-benchmarking .research/vendor/AppliedMachineLearning-Lab--jev-benchmarking -- --filter=blob:none --no-checkout
git -C .research/vendor/AppliedMachineLearning-Lab--jev-benchmarking fetch origin 87562114d23597f610754f057e5e0da8659dbcfb
git -C .research/vendor/AppliedMachineLearning-Lab--jev-benchmarking checkout --detach 87562114d23597f610754f057e5e0da8659dbcfb
test "$(git -C .research/vendor/AppliedMachineLearning-Lab--jev-benchmarking rev-parse HEAD)" = "87562114d23597f610754f057e5e0da8659dbcfb"
```

License text: [LICENSE](https://github.com/AppliedMachineLearning-Lab/jev-benchmarking/blob/87562114d23597f610754f057e5e0da8659dbcfb/LICENSE). 

### xzx34/JevOut

Paper-linked answer-preserving context perturbation evaluation; good bounded robustness test after baseline.

Verified pin: [c8ab231728abb54bd61cf3c8812cb48811aae36b](https://github.com/xzx34/JevOut/commit/c8ab231728abb54bd61cf3c8812cb48811aae36b).

```bash
gh repo clone xzx34/JevOut .research/vendor/xzx34--JevOut -- --filter=blob:none --no-checkout
git -C .research/vendor/xzx34--JevOut fetch origin c8ab231728abb54bd61cf3c8812cb48811aae36b
git -C .research/vendor/xzx34--JevOut checkout --detach c8ab231728abb54bd61cf3c8812cb48811aae36b
test "$(git -C .research/vendor/xzx34--JevOut rev-parse HEAD)" = "c8ab231728abb54bd61cf3c8812cb48811aae36b"
```

License text: [LICENSE](https://github.com/xzx34/JevOut/blob/c8ab231728abb54bd61cf3c8812cb48811aae36b/LICENSE). 

### nokia-applied-research/AnyJev

Training-free typed probabilities from open LMs. Not model-free: needs checkpoint + inference runtime; Tacit checkpoints are separate assets.

Verified pin: [b03158e9ba18e84c01054aaa393481925088db07](https://github.com/nokia-applied-research/AnyJev/commit/b03158e9ba18e84c01054aaa393481925088db07).

```bash
gh repo clone nokia-applied-research/AnyJev .research/vendor/nokia-applied-research--AnyJev -- --filter=blob:none --no-checkout
git -C .research/vendor/nokia-applied-research--AnyJev fetch origin b03158e9ba18e84c01054aaa393481925088db07
git -C .research/vendor/nokia-applied-research--AnyJev checkout --detach b03158e9ba18e84c01054aaa393481925088db07
test "$(git -C .research/vendor/nokia-applied-research--AnyJev rev-parse HEAD)" = "b03158e9ba18e84c01054aaa393481925088db07"
```

License text: [LICENSE](https://github.com/nokia-applied-research/AnyJev/blob/b03158e9ba18e84c01054aaa393481925088db07/LICENSE). 

## Important exclusions and license distinctions

- Awign has separate dashboard/warehouse/tabletop paths and unresolved project-wide licensing; it is not an integrated swarm to import. RobotFleet is close centralized orchestration prior art but its inspected repository did not establish the paper’s claimed MIT license.
- Graphiti has a real FalkorDriver but is deferred. HippoRAG uses igraph; it is not a drop-in FalkorDB backend. AriGraph is a semantic/episode reference, not a fleet adapter.
- HUME and VeriGraph can inform independent implementations; their experimental/symbolic checks are not a full physical safety stack. Avoid all-extras installs and simulator-oracle leakage.
- AnyJev training-free readout still needs a model and inference runtime. Strands/Laya model weights, base-model terms, datasets and third-party assets require separate checks. H2O-Lightning remains a model-card research lead, not a selected GitHub dependency.
- The TypeSafe client/adapter code license does not grant access/redistribution rights for Jev. The Microsoft provider is a source reference; do not install it into the user's live Hermes plugins to run this project.
- Never claim the entire stack is OSI FOSS: the server is SSPL, and hosted models are separate proprietary services.

## Rechecking before use

```bash
gh repo view FalkorDB/GraphRAG-SDK --json name,url,defaultBranchRef
gh api repos/FalkorDB/GraphRAG-SDK/commits/35e67a0b27fdcc7f2c28508b09e86169851a8187 --jq .sha
gh api 'repos/FalkorDB/GraphRAG-SDK/git/trees/35e67a0b27fdcc7f2c28508b09e86169851a8187?recursive=1' --jq .truncated
```

The last command checks whether a tree listing was complete; it does not run the software. Read source at the exact pin. Moving docs/HEAD may describe newer behavior. An update requires lock changes, license review and rerunning contract tests.
