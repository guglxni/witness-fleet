# Integration instructions and dependency gates

**Source-verified design recipes. No application dependency installation, graph mutation, model inference or simulation has run in this task. A documentation-only DESIGN.md linter was executed.** Clone pins are verified in `REPOSITORIES.md`; installation combinations remain to be resolved and tested. Follow PLAN in order. Use the real package roots listed here; a repository root is not always installable.

## 1. Integration topology

```text
main Python runtime -> direct FalkorDB client -> tenant ops
main runtime -> HTTP corpus adapter -> isolated GraphRAG SDK -> tenant corpus + discovered companion keys
main runtime -> HTTP typed-decision adapter -> one authorized provider (optional)
main runtime -> HTTP simulator adapter -> MuJoCo + simulator receipt journal
web UI -> FastAPI read projections + explicit approval commands
```

No remote inference in the physics loop. No direct browser access to FalkorDB. No model invocation through unrestricted general database MCP. Hermes/Claude/Codex can write the project but are not required runtime dependencies.

## 2. Preflight and pins

From a new project worktree inspect `git status`, `gh --version`, `gh auth status`, Python/uv, Node/npm, Docker version/health and occupied ports. Do not print authentication values. Before any install choose exact package versions in lockfiles compatible with the project Python version; target Python 3.12 initially, but let actual resolver/wheel tests decide. Node version follows the selected Vite release's engines, not a guessed fixed major.

Use audited `.research/vendor/OWNER--REPO` clone commands in REPOSITORIES. Do not replace `PIN` with a moving main branch. The inspected MuJoCo/client HEADs are dated source snapshots rather than claimed stable release locks. Record a matching release package/digest after successful smoke tests; source SHA and package version are different identities.

## 3. FalkorDB server and Python client

Audited server: v6.0.2, `7b7b4d1ed23fe78e69fa5da0c9e4f2ea2e73f3e9`. Audited client: `31f63f44a5745b9bec65969a1db706906718cb82`, package root `.research/vendor/FalkorDB--falkordb-py`, module `falkordb`.

Source checkout installation, **only after creating an isolated venv**, can use:

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python ./.research/vendor/FalkorDB--falkordb-py
```

This installs the checked-out source; final app uses a resolved project lockfile and `uv sync --frozen`, not ad-hoc installs. Inspect the client's `pyproject.toml` redis dependency constraints before resolving SDK in another environment.

Before writing compose: confirm the intended Docker tag exists and record its immutable image digest/platforms using Docker image manifest inspection. Do not invent a digest or assume source release tags always match image tags. Configure a **new** project instance and named volume, loopback-bound Redis port chosen after port check, AOF enabled, deliberate `appendfsync` profile, persistent ACL file and health/readiness checks. Preserve existing `graphhacks-fdb` unchanged. The actual data directory must be read from the selected image's configuration; never guess between `/data` and `/var/lib/falkordb/data`.

Client seam from inspected source:

```python
from falkordb import FalkorDB
# Host/port and role credentials come from controlled runtime configuration.
db = FalkorDB(host="127.0.0.1", port=6380)
graph = db.select_graph("wf:demo:ops")
rows = graph.ro_query("MATCH (n) RETURN n LIMIT 1")
```

This is an illustrative local query, **not executed** and not a proposed unrestricted tool. Verify parameterized `.query(..., params=...)`/`.ro_query(..., params=...)` signatures at the pin; wrap in domain methods that return typed DTOs, timeout/error states and schema versions. Verify constraints operational, distance sort direction and missing query features. Never catch database errors as “no restrictions”.

## 4. GraphRAG-SDK narrow lane

Pin `35e67a0b27fdcc7f2c28508b09e86169851a8187`; installable package root is **`GraphRAG-SDK/graphrag_sdk`**, not the outer monorepo. Inspect:

- `graphrag_sdk/examples/11_structured_ingestion.py`
- `graphrag_sdk/src/graphrag_sdk/ingestion/structured_pipeline.py`
- `graphrag_sdk/src/graphrag_sdk/api/main.py`
- `graphrag_sdk/src/graphrag_sdk/core/models.py`
- `graphrag_sdk/src/graphrag_sdk/core/providers/base.py`
- chunkers `fixed_size.py` and `sentence_token_cap.py`

After selecting actual needed extras and an authorized generation/embedding provider:

```bash
uv venv .venv-corpus --python 3.12
uv pip install --python .venv-corpus/bin/python ./.research/vendor/FalkorDB--GraphRAG-SDK/graphrag_sdk
```

Do not claim this base installation is sufficient for every provider. Resolve required extras in `services/corpus/pyproject.toml`, lock and test them. The source manifest says 1.4.0; package/release/version compatibility is not established by that number alone.[61]

### Integration steps

1. Implement canonical source retention and normalization **before** SDK ingestion. UTF-8 strict decode, normalize CRLF/CR to LF, preserve Unicode codepoints (no NFC/NFKC unless explicitly versioned), retain original bytes/hash and normalized text/hash. Offsets are zero-based half-open Python string indices into normalized text.
2. Load original synthetic owner roster, policy table and tickets using explicit `TableMapping` columns/keys/links from the pinned example. Do not infer stable IDs using an LLM. Stage source-linked candidate records; structured rows do not make arbitrary prose authoritative.[78]
3. Configure tenant corpus key plus exact SDK companion/ontology key allowlist with corpus-only role. Discover actual names in a disposable test; no wildcard granting ops.
4. Configure real embedding/generation interfaces only where required. The facade requires provider contracts and `finalize()` may invoke model-based resolution; structured ingestion alone is not evidence the entire facade is model-free. Disable unwanted fuzzy merging and review exact-name dedup scope.[62][82]
5. Call the pinned retrieval seam to return candidates without generation. Normalize to `CandidateSpan` containing source/revision/chunk/span identity and locator status. Local vs multipath retrieval can differ in chunk metadata; missing locators remain `unresolved`, not invented.[35]
6. Validate every quote against retained normalized revision. Fixed-size chunk offsets can aid mapping; optional chunk-local extractor spans must be translated and verified. Default chunker offsets are not guaranteed.[79][80][81]
7. Return candidates via HTTP to coordinator. Promotion to ops uses deterministic identity/span/approval/scope checks and idempotent event IDs. All decisive source-owner-policy relationships are stored in ops; no cross-graph Cypher join.
8. Test document update/delete/resync/finalize failure without changing canonical history. Corpus replacement is not an immutable approved revision ledger. SDK raw `.query()` is not read-only; never expose it to an agent.[62][63]
9. Fallback: direct typed JSON/Markdown source ingestion and deterministic retrieval remain available. Display `SDK disabled/blocked`, keep R-024 unmet until it actually works. Do not silently call the fallback SDK integration.

## 5. MuJoCo

Audited repo `google-deepmind/mujoco` at `12720007ea3c98238990190dcba6d93fee0dd4c1`. Read `doc/python.rst`, `doc/programming/index.rst`, `python/pyproject.toml`. Prefer the matching tested Python wheel rather than building C++ from HEAD; record wheel/version/hash. Native macOS arm64 support is documented, not locally exercised here.[83]

Before implementing fleet logic: load original minimal XML, step one body, then three bodies on one clock, verify observation DTO boundary and bounded command receipts. On macOS a passive viewer runs via `mjpython`; a normal Python process is suitable only for supported non-viewer modes. Test headless Linux separately before advertising it. Do not install HUME's household simulation or import Awign meshes merely to get a nicer scene.

## 6. System One adapters

Use `DECISION_CONTRACTS.md`. Main project implements a minimal async HTTP provider adapter with validation, deadline, no redirects and sanitized errors. `guglxni/ms-decision-provider` is a **reference** for response mapping/security tests; its Hermes secret-scope/plugin hooks are not standalone project runtime APIs. Do not clone it into a live plugins directory or modify Hermes to run this app.

Microsoft route is resource-host `/providers/microsoft/v1/systemone`, distinct from OpenAI `/v1/decisions`. Jev uses its own endpoint/model IDs. Service access, key/identity setup and billing are operator-controlled; this package contains no credentials. Use authorized synthetic test data only.[41][42][48]

OpenAI Decisions SDK examples and GraphRAG's OpenAI extra can have incompatible SDK version bounds; an HTTP boundary/isolated worker avoids assuming one environment can satisfy both. Also verify whether a selected Azure generator needs Responses rather than Chat Completions before using an SDK provider.[41][61]

Activation steps: contract mocks → live authorized single-request smoke → labeled shadow dataset → frozen per-family calibration → held-out comparison → optional advisory. A successful transport response does not prove useful decisions or safe automation. No budgeted inference runs have occurred.

## 7. Research reference reuse

- **HUME:** inspect symbolic hypotheses and verification action generation; implement our typed ledger independently. Do not inherit optimistic assumptions as shared facts or simulator metadata as perception.
- **VeriGraph:** inspect checker failure reasons and plan-prefix repair; not a substitute for physical feedback.
- **Jev benchmarking:** reuse the idea of frozen requests, content-addressed caching, per-family calibration and retained raw responses. Dataset/API-response redistribution needs separate rights review.
- **JevOut:** use synthetic answer-preserving perturbations with independently checked gold labels; no paid attack optimization required for basic invariance tests.
- **AnyJev:** optional actual-logit baseline. Verify tokenizer labels, discarded probability mass, rotations/prefills and checkpoint license; training-free is not model-free.
- **Graphiti/HippoRAG/AriGraph/Docling/LangGraph/OPA/py_trees:** defer; do not add a second memory framework, authority engine or graph backend because its README looks useful.

## 8. API and UI integration

API contracts in API.md. UI reads projections and event stream; it does not compute authorization from text. Generated explanations must be backed by graph/source IDs. Create UI only after a real source→graph→action→observation slice returns events. Test stale connections and rejected operator approval as visibly as success.

## 9. Integration completion evidence

For every dependency record source pin, installed version, lock/hash, license, platform, exact smoke command, actual output, negative-case test and artifact path. A README code example, dependency resolver success, import success and full end-to-end operation are four different evidence levels. Keep blocked requirements visible and do not manufacture a working integration report.

<!-- GENERATED CITATION REFERENCES -->

## Sources

[35] https://docs.falkordb.com/graphrag/reliability-and-grounding.md — Reliability and Grounding
[41] https://developers.openai.com/api/docs/guides/decisions — Decisions | OpenAI API
[42] https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-microsoft-decision — Deploy and use Microsoft-Decision-1 in Microsoft Foundry - Microsoft Foundry | Microsoft Learn
[48] https://docs.typesafe.ai/api.md — API reference
[61] https://github.com/FalkorDB/GraphRAG-SDK/blob/35e67a0b27fdcc7f2c28508b09e86169851a8187/graphrag_sdk/pyproject.toml — GraphRAG SDK pinned: graphrag_sdk/pyproject.toml
[62] https://github.com/FalkorDB/GraphRAG-SDK/blob/35e67a0b27fdcc7f2c28508b09e86169851a8187/graphrag_sdk/src/graphrag_sdk/api/main.py — GraphRAG SDK pinned: graphrag_sdk/src/graphrag_sdk/api/main.py
[63] https://github.com/FalkorDB/GraphRAG-SDK/blob/35e67a0b27fdcc7f2c28508b09e86169851a8187/graphrag_sdk/src/graphrag_sdk/core/connection.py — GraphRAG SDK pinned: graphrag_sdk/src/graphrag_sdk/core/connection.py
[78] https://github.com/FalkorDB/GraphRAG-SDK/blob/35e67a0b27fdcc7f2c28508b09e86169851a8187/graphrag_sdk/src/graphrag_sdk/ingestion/structured_pipeline.py — GraphRAG SDK: deterministic structured pipeline
[79] https://github.com/FalkorDB/GraphRAG-SDK/blob/35e67a0b27fdcc7f2c28508b09e86169851a8187/graphrag_sdk/src/graphrag_sdk/ingestion/extraction_strategies/graph_extraction.py — GraphRAG SDK: span extraction and propagation
[80] https://github.com/FalkorDB/GraphRAG-SDK/blob/35e67a0b27fdcc7f2c28508b09e86169851a8187/graphrag_sdk/src/graphrag_sdk/ingestion/chunking_strategies/fixed_size.py — GraphRAG SDK: fixed-size chunk offsets
[81] https://github.com/FalkorDB/GraphRAG-SDK/blob/35e67a0b27fdcc7f2c28508b09e86169851a8187/graphrag_sdk/src/graphrag_sdk/ingestion/chunking_strategies/sentence_token_cap.py — GraphRAG SDK: default chunk metadata
[82] https://github.com/FalkorDB/GraphRAG-SDK/blob/35e67a0b27fdcc7f2c28508b09e86169851a8187/graphrag_sdk/src/graphrag_sdk/core/providers/base.py — GraphRAG SDK: provider contracts
[83] https://mujoco.readthedocs.io/en/stable/python.html — Python - MuJoCo Documentation
