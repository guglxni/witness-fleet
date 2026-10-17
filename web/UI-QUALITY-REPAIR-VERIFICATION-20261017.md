# Parent verification - UI QUALITY repair (2026-10-17)

## Disposition

The two findings from completed `deleg_62344231` were reproduced against the reported hashes and repaired in the frontend only. This is **locally verified and independently SPEC accepted; QUALITY remains pending**. Completed SPEC `deleg_35fbb13d` passed all bounded requirements and independently ran 58 tests plus typecheck. Parent read the final report `REVIEW-SPEC-QUALITY-REPAIR-20261017.md` (SHA-256 `9513083d2220b4ebca531f90662c9ae01fe76f427640b6b86331bf3dae123567`), validated all 8 recorded digests and matched each exact file; the 5 owned source/test hashes also match the frozen manifest. Separate QUALITY review `deleg_8d2410d4` has been dispatched. The SPEC report title references the QUALITY repair, but it does not substitute for that separate review. Earlier SPEC/QUALITY reports apply only to their historical hashes and are retained unchanged.

Scope: `UI-QUALITY-REPAIR-SCOPE-20261017.md`. No backend/runtime/graph/simulator source was changed and no real control/mutation request was sent. No service restart, public deployment, paid inference, commit or submission.

## Repairs and regressions

- Exact verified states replace substring matching. UNVERIFIED / NOT_VERIFIED / partial variants do not get green or a check; controller completion stays distinct.
- Snapshot reducer rejects cross-episode replacement unless the caller explicitly supplies episode-change authority. Same-episode revision ordering remains monotonic.
- Latest REST request + episode generation fences reject late reads/errors; guarded incident response can establish a reset-revision episode, while controls cannot.
- One active SSE stream replaces competing one-shot hydration. Old instance/generation callbacks cannot publish or alter freshness. Wrong-episode and regressing snapshots cannot unlock stale controls.
- Active-stream episode mismatch locks and latches until a REST refresh begun after the mismatch, then a matching stream snapshot. No global episode ordering is fabricated.
- Episode-scoped approval draft identity, retained-source cache remount, witness response generation guard, old-action-message clearing and request-ID reset prevent UI cross-episode leakage. This does not reconcile backend unknown outcomes.

The test-first sequence is documented in the scope report and tool/session history. New branches were exercised red then green; extra first-pass boundary tests are regression strengthening, not manufactured RED evidence.

## Executed checks

- `npm test`: **58 unique tests**, 4 files, no failures/errors/skips. JUnit programmatically reconciled against 58 unique classname/name pairs.
- `npm run typecheck`: passed.
- `npm run build`: passed; bundle `index-DoIUqIvP.js`, unchanged CSS `index-BxI07yES.css`. `emptyOutDir:false` preserves historical build assets.
- `npm run test:e2e`: **12 passed** at desktop/mobile configurations using existing Vite server. Synthetic projected states plus existing empty-backend view; not fleet acceptance.
- Race/component test file: **21 cases**, repeated **5 consecutive runs** without failure. These are repeat executions, not 105 distinct tests.
- Production-bundle isolated transport probe: **320px and 1440px passed**. Deferred REST responses, queued closed-stream callbacks, wrong-episode freshness lock, and verified tag/glyph checks. Every API response in this probe is explicitly synthetic; no real API control path is exercised.
- Real unintercepted production API/DOM inspection: **11 unique viewports passed** (320x700, 360x800, 375x812, 390x844, 414x896, 430x932, 768x1024, 1024x768, 1165x900, 1440x1000, 844x390). Each loads a retained source and a 10-node/9-edge witness. No document overflow, page errors, mutation requests or sampled typography failures.
- Read-back of live state before/after: same incident, revision 250000000000, graph version 250, tick 0, zero commands, inspection_only, dispatch_ready false. No motion or restart acceptance inferred.
- Parent source hash comparison against live-verification manifest passed; `git diff --check` passed. HTTP read-back confirmed the served JS and CSS hashes exactly match the built files; all 12 frozen source/test/design hashes still match. Changed UI source scan found no dynamic HTML/eval injection sinks. Since frontend files are still untracked in the larger worktree, this report binds exact bytes rather than implying a reviewed commit.

## Evidence paths

Under `artifacts/showcase-20261017/ui-quality-repair/`:

- `unit.xml`, `race-repetition.json`
- `verify-responsive.mjs`, `responsive.jsonl`, `summary.json`, `manifest.json`
- `verify-production-races.mjs`, `production-races.jsonl`, `synthetic-races-{320,1440}.png`
- `320x700-{source,witness}.png`, `390x844-{source,witness}.png`, `1440x1000-{source,witness}.png`
- `frozen-hashes.json`

Headless Chromium is not physical iOS/Android validation. Synthetic races prove UI handling, while real read-only probes prove actual inspection payload rendering. Neither proves an autonomous fleet mission.

## Frozen input SHA-256

| File | SHA-256 |
|---|---|
| `web/src/App.tsx` | `fabfea8e882ed3e2013f09b61007ab2e147f6fef98de3bd5f989da0e01ddd872` |
| `web/src/state.ts` | `ee9d8f3452907bd37f7029a4106d1adb8ada01d60408df7065f8239ba4a212cd` |
| `web/src/styles.css` | `5f3e16248169df13a86cb01fc615a8e7e5c0bbf077667e6fcd206c6f0b6e8117` |
| `web/src/api.ts` | `f02d1b440017fb150e845f8f6f79ba35d89a71146dae362840d4544fefef35ab` |
| `web/tests/state.test.ts` | `0799f0914c5bc0c331c44420079dc0bb1d3382560ddbcaa347c5423ac74d51a5` |
| `web/tests/status.test.ts` | `52d41b6501702475952a7af4a996613dd9ffa4e5e4c4b0865dbce9d53184b200` |
| `web/tests/projection-races.test.tsx` | `0940a2ab262067bd811d0d990c7491f096b63fc8f98b8d5143f48734cbbe03c4` |
| `web/tests/operator-console.test.tsx` | `95ce51b712315e4d3850bf0432d3636a7ad01c8d297f47a7d208b5ac95861876` |
| `web/api-contract.ts` | `01d1f6370e2c460c34b55a923591edb41245e9e369ff131a5757accc479d1052` |
| `web/e2e/local-waiting.spec.ts` | `f15f93433a9d3921e0d823b51d001b90e9e95c81ff00069b45695ce1cc37ae77` |
| `web/e2e/evidence-readability.spec.ts` | `cb28bd2b53aea141c457cd004a659a1d9e3c3e057a44100f7b29bde7b005e7c7` |
| `DESIGN.md` | `ee84c2862ba2892814fc3bff30eff2e05d4d432adf59a7085cb5306fe56fe0c8` |
