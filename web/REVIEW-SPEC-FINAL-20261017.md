# Independent UI SPEC re-review · 2026-10-17

## Scope and verdict

Independent, read-only re-review of the six findings in `web/REVIEW-SPEC-20261017.md`, against the current Witness Fleet UI, `DESIGN.md`, and the targeted UI tests. **All six findings are closed on the reviewed hashes below; none is retained.** No application source, tests, contract, or design files were edited. This is a bounded UI/spec verdict, not backend, fleet, physical-safety, runtime, or submission acceptance.

## Finding dispositions

1. **Closed — absent projection is not a negative dispatch verdict.** `App.tsx` now renders the overview dispatch summary as `Unavailable` when `projection` is absent, with ready/not-ready only when a projection exists. The operator-console test asserts `Unavailable` for the no-incident state.
2. **Closed — retained offline projection is labeled stale.** Offline refresh with a retained projection renders a prominent cached/stale banner naming its revision and world tick; freshness reports a stale cached revision and `writeEnabled` excludes offline/stale states. Tests cover offline refresh and SSE interruption locking. These are UI-state checks, not proof of all transport/runtime failure modes.
3. **Closed — independent Policy gate is explicit.** The reason panel shows Policy as unknown/not exposed by the contract; Physical, Claim, and Freshness remain distinct, and Dispatch remains an additional backend-reported gate. The operator-console test checks the Policy row and its unknown status.
4. **Closed — successful HTTP response is neutral, not accepted/verified.** `runAction` reports “response received”; the result uses the neutral `response` kind with no success check icon/palette. The approval test asserts `result-response`, rejects `result-accepted`, and checks for no SVG icon. Backend response is not presented as a verified physical outcome.
5. **Closed — witness edge marker is defined and used.** The SVG defines `marker#witness-arrow`, and edges reference it via `markerEnd`. The witness test asserts both the marker and its use on an edge. Keyboard access and a textual table/edge listing are also present; this finding concerns marker conformance, not correctness of backend graph contents.
6. **Closed — reason and evidence typography meet the stated minimums at tested widths.** The reason lead is 16px; leaf-level evidence/status/metadata selectors are raised to at least 13px. The targeted E2E measures rendered graph text size (including SVG screen scale), exercises retained source/witness text at 320px and 1440px, checks the graph scroll region is keyboard-focusable, and asserts no document overflow. Its fixtures are explicitly synthetic and test-only; it does not establish readability at every zoom, device, or browser configuration.

## Independent targeted verification

Run in `web/` during this review:

- `npm run test:e2e -- e2e/evidence-readability.spec.ts --project=desktop` — **2 passed** (320px and 1440px).
- `npx vitest run tests/operator-console.test.tsx` — **17 passed**.

The test suite supports the dispositions but is not the sole basis: the corresponding render branches, CSS rules, SVG markup, and assertions were inspected directly. No controls or backend mutations were invoked.

## Exact reviewed artifact hashes (SHA-256)

| Artifact | SHA-256 |
|---|---|
| `web/src/App.tsx` | `ea6ea65f6746521e588ea3a79f30f73d116ca022c89e91d4cc145b064cffbd87` |
| `web/src/styles.css` | `5f3e16248169df13a86cb01fc615a8e7e5c0bbf077667e6fcd206c6f0b6e8117` |
| `web/tests/operator-console.test.tsx` | `95ce51b712315e4d3850bf0432d3636a7ad01c8d297f47a7d208b5ac95861876` |
| `web/e2e/evidence-readability.spec.ts` | `cb28bd2b53aea141c457cd004a659a1d9e3c3e057a44100f7b29bde7b005e7c7` |
| `web/e2e/local-waiting.spec.ts` | `f15f93433a9d3921e0d823b51d001b90e9e95c81ff00069b45695ce1cc37ae77` |
| `web/api-contract.ts` | `01d1f6370e2c460c34b55a923591edb41245e9e369ff131a5757accc479d1052` |
| `DESIGN.md` | `ee84c2862ba2892814fc3bff30eff2e05d4d432adf59a7085cb5306fe56fe0c8` |

The hash list identifies the reviewed source/test/spec basis. Any later file change invalidates this hash-bound verdict for that artifact.
