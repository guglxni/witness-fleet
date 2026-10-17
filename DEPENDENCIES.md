# Dependency and build evidence

## Observed on 2026-10-15, Mac Mini arm64/macOS 27

- Main Python environment resolved and installed with `uv sync --extra dev --extra simulator`; frozen sync passed. Python 3.12.6, MuJoCo 3.16.0, FalkorDB client 1.8.0, FastAPI 0.143.1, Pydantic 2.14.1, NumPy 2.5.4, pytest 9.1.1, Ruff 0.17.0, mypy 1.20.2.
- Native MuJoCo executed 100 actual physics steps, advancing to 0.2 simulated seconds. `mjpython scripts/smoke_native.py` rendered 320x240 RGB with nonuniform pixels; output at artifacts/dependency-smoke. This validates native library/rendering, not the fleet.
- FalkorDB Docker tag is **6.0.2**, not v6.0.2. Pinned OCI digest: sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6; supports arm64 and amd64. New witness-fleet-graph container is healthy, graph module version60002, AOF yes, appendfsync always, named persistent volume at /var/lib/falkordb/data. Original graphhacks-fdb untouched.
- Real parameterized write and read returned the same toolchain-smoke record. ACL roles were amended to include INFO because official Python client performs a sentinel/server probe during construction; this is a verified client prerequisite, not broadening graph-key permissions.
- GraphRAG SDK exact source35e67a0b27fdcc7f2c28508b09e86169851a8187 cloned with gh and installed in isolated services/corpus/.venv; version1.4.0. hnswlib0.8.0 compiled on arm64; Torch2.14.1, GLiNER0.2.29, SciPy1.18.1 and imports pass, MPS available. TableMapping is exported from graphrag_sdk, not structured_pipeline. No model weights or paid inference installed/run by this import smoke.
- Node26.7.0 satisfies selected Vite8.3.4/Vitest5.0.4/Playwright1.64.1 engines. npm installed React19.3.1, Three, TypeScript, Vite, Vitest, testing-library and Playwright; macOS arm64 Chromium/headless-shell/FFmpeg binaries downloaded. Actual headless browser launched and read a test heading.

## Pending gate

Frontend bundling attempted, but tool approval timed out. Renewed clarify also timed out. Do not retry or rephrase that build or regenerate/clean output without renewed user approval. Dependency presence/headless launch does not count as frontend build success. This block does not permit claiming no future issues; integration tests remain mandatory.

## Reproduction

Main: `uv sync --frozen --extra dev --extra simulator`.
Corpus: first clone pin per INTEGRATIONS then `uv sync --frozen --project services/corpus`.
Web: `npm --prefix web ci` and `npm --prefix web exec playwright install chromium`.
Graph: `docker compose up -d --wait` for the new project service only.
Native rendering: `.venv/bin/mjpython scripts/smoke_native.py`.

Local synthetic roles are **nopass** and socket is loopback-only; not production authentication. Provider credential setup must follow approved secret tooling and does not belong in tracked files.
