# Legacy graph fixture migration

## Scope

Migrated these integration tests to the reviewed `isolated_console_graph` fixture, with `isolated_runtime_graph` explicitly imported for fixture registration:

- `tests/integration/test_graph_storage.py`
- `tests/integration/test_snapshot_edge_closure.py`
- `tests/integration/test_canonical_source_identity.py`
- `tests/integration/test_claim_query_exclusion.py`
- `tests/integration/test_claim_required_resources.py`
- `tests/integration/test_claim_race.py`

Each test now receives its own retained graph namespace. Additional test clients used for true concurrent writes/interleavings independently connect to that exact same isolated graph, with the fixture host, port, tenant, username, and snapshot caps copied explicitly. No shared fixture, source, production code, graph, or volume was modified or removed.

The oversize unscoped snapshot case now inserts one uniquely named `DispatchEvent` into its isolated namespace before testing the one-node cap; it no longer depends on preexisting demo graph records. The no-match `delete_test_records` case uses an offline `_query` recorder and asserts the exact bound tenant/prefix parameters, write flag, returned count, guarded graph-version expression, and delete statement text without executing the destructive query against a server.

## Verification

- Command: `.venv/bin/python -m pytest tests/integration/test_graph_storage.py tests/integration/test_snapshot_edge_closure.py tests/integration/test_canonical_source_identity.py tests/integration/test_claim_query_exclusion.py tests/integration/test_claim_required_resources.py tests/integration/test_claim_race.py -q --tb=short --junitxml=report-artifacts/legacy-graph-fixtures-junit.xml`
- Result: **26 passed**, 0 failures, 0 errors, 0 skipped (11.37 seconds).
- Per-file counts: graph storage 16; snapshot edge closure 3; canonical source identity 1; claim query exclusion 1; claim required resources 1; claim race 4.
- `git diff --check` passed. Existing retained graph fixtures and backing volumes were left intact.

## SHA-256

- `tests/integration/test_graph_storage.py`: `81c2978ecdeae01b8f5f58fa65efe570bed431428eed188074089c0ce6f1575c`
- `tests/integration/test_snapshot_edge_closure.py`: `910cb0aa2ce9b7a293917465c0fc1ff546cf44b0dd7559af5bfc34fe2c09ee6c`
- `tests/integration/test_canonical_source_identity.py`: `2b0f87c86fa4ea4a50efced4246f3bf26ae31dbc0885f66851e539bea797526a`
- `tests/integration/test_claim_query_exclusion.py`: `791bd05bb7d05e6db8088a91acc3faca321ebd4bac3db3042ffc982205659644`
- `tests/integration/test_claim_required_resources.py`: `80e2bdad119a3ce0c28a76271ecf41ea2af83f6201a54951147b580afc57e7a3`
- `tests/integration/test_claim_race.py`: `240357f779c2ffd2200a7dd85c4ee6b0e2eae7c7a62aa63caea7cac416e87c2b`
- JUnit report `report-artifacts/legacy-graph-fixtures-junit.xml`: `102af6df24ba4146b9cf708f1c3a0a3e1aa5c66f78f8db557d6088f11561f4f9`
