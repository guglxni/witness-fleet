# Parent verification of the completed UI repair

## Scope and current disposition

Reconciles completed worker `deleg_ef483633`. The worker's App/CSS/test/contract hashes in `REPAIR-20261017.md` matched the files measured by the parent. The mutation warning referred to an identical-old/new no-op patch in `web/tests/operator-console.test.tsx`; it was not evidence of missing test content.

The overflow repair is verified. A broader parent check found incomplete typography repair, which was corrected and re-tested. Independent UI SPEC accepted the historical hashes below. Completed UI QUALITY `deleg_62344231` then BLOCKED those files on false-positive verified styling and cross-episode snapshot races. The bounded frontend repair is recorded in `UI-QUALITY-REPAIR-SCOPE-20261017.md` and `UI-QUALITY-REPAIR-VERIFICATION-20261017.md`; the new hashes passed completed SPEC `deleg_35fbb13d`, verified against all 8 report artifacts. Separate QUALITY `deleg_8d2410d4` completed PASS and its full review basis was hash-verified. Final bounded frontend acceptance is recorded in `UI-REPAIR-ACCEPTANCE-20261017.md`. Nothing in this report accepts fleet motion, policy execution, outcome completion, lease repair or restart resume.

## Initial verification and residual finding

- Worker snapshot: 26 unit tests, typecheck, production build and 8 Playwright tests passed on parent rerun.
- Actual local production build at `http://127.0.0.1:8094`: desktop and 390px live source/witness checks passed, no intercepted responses or mutations.
- Parent expanded actual-live probe to 11 viewports: 320x700, 360x800, 375x812, 390x844, 414x896, 430x932, 768x1024, 1024x768, 1165x900, 1440x1000, 844x390.
- All viewports had no document overflow or page errors. Each loaded an actual retained source and a 10-node/9-edge witness.
- However, nested `td strong`, `.mono`, status tags, witness titles and relationship text remained 9–11px. Parent-only font assertions in existing tests did not cover those leaf declarations. SVG viewBox scaling reduced mobile graph label size to approximately 3.55–3.95 rendered pixels.

## Regression-first correction

Added `web/e2e/evidence-readability.spec.ts`. Its synthetic contract data is test-only, not live-fleet evidence.

1. First invocation timed out because the test task omitted required `last_command_id`; this was a fixture diagnostic, not behavioral RED.
2. Added explicit `last_command_id: null` to the test fixture. The corrected tests failed at both 320px and 1440px: `.status-tag` expected >=13, received 9. The actual-live probe had already independently captured the broader failures.
3. Updated leaf metadata/quote typography to >=13px across breakpoints. Main reason stays 16px.
4. Kept the witness SVG at its native pixel size within a labeled, keyboard-focusable scroll region instead of shrinking labels to fit a phone. Widened nodes for the larger text and adjusted edge centers. Exact IDs remain available in the adjacent table/text list.
5. First fix exposed a more-specific `.witness-table td strong` rule; added matching specificity. Both focused regressions then passed.

## Final executed verification

From `web/`:

- `npm run test:e2e -- e2e/evidence-readability.spec.ts --project=desktop`: **2 passed**.
- `npm test`: **26 passed**, 3 files.
- `npm run typecheck`: passed.
- `npm run build`: passed; emitted `index-BxI07yES.css` and `index-SSBsZPD_.js`.
- `npm run test:e2e`: **12 passed**. This includes the focused cases; counts are not additive.

From the repository root:

- `node artifacts/showcase-20261017/parent-ui-verification/verify-responsive.mjs`: all **11 viewports passed** source/witness, typography, no-overflow, no-page-error and no-mutating-request assertions.
- Programmatic aggregation confirmed all sampled rendered witness labels are **13px**, all Run controls are disabled, and arrow markers exist at every viewport.
- `node scripts/verify_live_console.mjs`: desktop 1440px and mobile 390px passed against the actual local API/build.
- Before/after API state was unchanged: graph version 250, world tick 0, no commands, `operator_mode: inspection_only`, `dispatch_ready: false`.

These are Chromium/headless checks, not physical mobile-device tests. Some source quotations are intentionally collapsed behind an expansion button, and wide tables/graph are intentionally locally scrollable. No document-wide overflow hiding was added.

## Evidence

`artifacts/showcase-20261017/parent-ui-verification/`:

- `responsive-red.jsonl`, `summary-red.json`, `manifest-red.json`: original residual typography failures and worker snapshot hashes.
- `responsive.jsonl`, `summary.json`, `manifest.json`: final real-API measurements and before/after state.
- `320x700-source.png`, `320x700-witness.png`, `390x844-source.png`, `390x844-witness.png`, `1440x1000-source.png`, `1440x1000-witness.png`.
- `verify-responsive.mjs`: reproduction harness; it performs GET/read-only UI inspection only.

Current whole-console captures: `artifacts/showcase-20261017/live-ui/{desktop,mobile}.png` and corresponding `-witness.png` crops.

## Final source/test SHA-256

| File | SHA-256 |
|---|---|
| `web/src/App.tsx` | `ea6ea65f6746521e588ea3a79f30f73d116ca022c89e91d4cc145b064cffbd87` |
| `web/src/styles.css` | `5f3e16248169df13a86cb01fc615a8e7e5c0bbf077667e6fcd206c6f0b6e8117` |
| `web/src/api.ts` (unchanged) | `f02d1b440017fb150e845f8f6f79ba35d89a71146dae362840d4544fefef35ab` |
| `web/api-contract.ts` (unchanged) | `01d1f6370e2c460c34b55a923591edb41245e9e369ff131a5757accc479d1052` |
| `web/e2e/evidence-readability.spec.ts` | `cb28bd2b53aea141c457cd004a659a1d9e3c3e057a44100f7b29bde7b005e7c7` |
| `web/e2e/local-waiting.spec.ts` | `f15f93433a9d3921e0d823b51d001b90e9e95c81ff00069b45695ce1cc37ae77` |
| `web/tests/operator-console.test.tsx` | `95ce51b712315e4d3850bf0432d3636a7ad01c8d297f47a7d208b5ac95861876` |

Final SPEC re-review `deleg_c5081abd` completed: all six findings closed. Parent read `web/REVIEW-SPEC-FINAL-20261017.md` and freshly measured every listed source/test/design hash; all match the reviewed snapshot. The reviewer independently ran 2 targeted E2E tests and 17 operator-console tests, all passing (overlapping the suites above, not additive). Report SHA-256: `d9f6d7ff4a05fca401845e79415a05ab0397b52de2921701dd3a2f311eea2633`. Existing broader QUALITY reviewer `deleg_055f04f5` completed with two backend projection blockers and explicitly did not accept final UI QUALITY. The backend findings are tracked separately in `report-artifacts/integration-20261017/inspection-scope-repair.md`. The frontend SPEC hashes in this historical section were valid when measured. Separate UI-only QUALITY review `deleg_62344231` subsequently completed with two blockers; the ensuing frontend repair changes App/state/tests and invalidates that historical SPEC acceptance for the new snapshot. Fresh SPEC review `deleg_35fbb13d` completed PASS; its report and all 8 input hashes were verified by the parent. Independent QUALITY `deleg_8d2410d4` then completed PASS with no findings; the parent matched its report, all 12 frozen-manifest files and all 17 review-basis artifacts. See `UI-REPAIR-ACCEPTANCE-20261017.md` for final scoped acceptance.

During the UI repair covered by this report, no backend/graph/simulator files or blocked runtime paths were changed. The subsequent inspection coordinator repair is documented separately above. No public deployment, commits, paid inference or submission occurred.
