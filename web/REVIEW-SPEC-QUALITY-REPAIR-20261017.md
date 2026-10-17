# Independent SPEC / QUALITY repair re-review · 2026-10-17

## Verdict and scope

**PASS — no blocking findings within the bounded UI repair requirements.** Reviewed the stated scope, prior blocked QUALITY review, predecessor SPEC review, current `App.tsx`/`state.ts` behavior, and the three owned regression-test files. The former exact-status and cross-episode replacement findings are addressed in the current code and covered by focused regressions. Episode/request/stream fencing and episode-scoped approval, source, witness, action-message, and idempotency state are consistent with the scope.

This is a hash-bound frontend review, not fleet/runtime/motion/physical-safety/hackathon acceptance. Tests use synthetic fixtures; no live service, E2E browser, backend, graph, simulator, or control request was used. No implementation, test, API, type, style, or backend file was edited. Only this review report was created.

## Requirement review

- **Exact positive status mapping — satisfied.** `decisionStateTone` grants the verified tone only to normalized exact `verified` and `outcome verified`. `unverified`, `not verified`, unknown values, and prefixed/suffixed variants cannot fall through to a positive tone; controller completion is in-progress. `status.test.ts` exercises negative variants and `OUTCOME_VERIFIED`; the synthetic UI regression also checks that `UNVERIFIED` and `NOT_VERIFIED` render without the verified class or check glyph.
- **Episode and revision authority — satisfied.** `acceptSnapshot` rejects episode changes unless the caller explicitly authorizes them and rejects same-episode revision regression. Refresh responses are sequence- and episode-generation-checked; latest REST refresh and incident creation can establish an episode, whereas ordinary controls cannot. Mutations invalidate reads begun before the write. The race suite covers older refresh completion/failure, late incident responses, reset revisions on a current incident response, and same-episode revision races.
- **SSE and freshness fencing — satisfied.** The active stream is checked by source identity and episode generation; cleanup closes it. Queued old-stream callbacks are ignored. Wrong-episode or older snapshots do not refresh freshness; an episode mismatch locks writes and requires REST rehydration followed by a valid snapshot on the replacement scoped stream. The tests exercise mismatch recovery, stale locking, rejected freshness, old callbacks, and old/wrong-episode snapshots. This is UI projection freshness only; it is not motion authorization or an ordering guarantee from the backend.
- **Cross-episode UI isolation — satisfied.** Episode changes clear witness state/error/loading, action result, and retained idempotency IDs. Witness requests capture the episode generation and ignore late results. Approval confirmation is keyed by episode/release/policy scope and its displayed request payload rotates with a changed episode/scope; retry identity remains stable within the same episode after unknown transport outcome. Source cards include episode identity in their React key, so loaded retained text is not carried to a new episode. Regression cases cover source, witness (already loaded and late), approval, action-result, and event-ID isolation.
- **Prior QUALITY findings — closed in current artifacts.** Exact `UNVERIFIED`/`NOT_VERIFIED` presentation is covered at helper and rendered-tag level. Different-episode snapshots are deny-by-default in the helper; only explicitly authorized/current REST establishment paths switch the episode, with races covered. These directly address both blockers in `REVIEW-QUALITY-FINAL-20261017.md`.
- **Earlier SPEC closures — preserved in the inspected UI.** No-projection dispatch is labeled unavailable; retained offline state is explicitly stale with writes locked; Policy remains independently unknown; action responses are labeled as responses rather than acceptance/verification; the witness graph defines and uses its edge marker and has table/text alternatives. Reviewed source and witness metadata typography remains at 13px or greater and the reason lead at 16px. The prior SPEC report's responsive E2E evidence was not repeated here.
- **Boundary — respected.** No backend/API contract or styles were edited, and no real POST or runtime action was made. This review does not establish live E2E behavior or any backend authorization property.

## Executed frontend checks

Run in `web/`:

- `npm test` — **passed**, 4 test files, 58 tests.
- `npm run typecheck` — **passed** (`tsc -b`).

No build, E2E, backend, graph, simulator, or live service tests were run.

## Exact review-basis SHA-256

Measured with `shasum -a 256` during this review:

| Artifact | SHA-256 |
|---|---|
| `web/src/App.tsx` | `fabfea8e882ed3e2013f09b61007ab2e147f6fef98de3bd5f989da0e01ddd872` |
| `web/src/state.ts` | `ee9d8f3452907bd37f7029a4106d1adb8ada01d60408df7065f8239ba4a212cd` |
| `web/tests/state.test.ts` | `0799f0914c5bc0c331c44420079dc0bb1d3382560ddbcaa347c5423ac74d51a5` |
| `web/tests/status.test.ts` | `52d41b6501702475952a7af4a996613dd9ffa4e5e4c4b0865dbce9d53184b200` |
| `web/tests/projection-races.test.tsx` | `0940a2ab262067bd811d0d990c7491f096b63fc8f98b8d5143f48734cbbe03c4` |
| `web/UI-QUALITY-REPAIR-SCOPE-20261017.md` | `d6d2bea63def2c48a84a73d3a44ea70bc24b59eaae20aaf518abd4e08161b3f1` |
| `web/REVIEW-QUALITY-FINAL-20261017.md` | `f776fd014e5d4453aa23fdbfbc1124060dcbe6e2430dbbe7f4407001685c4b4f` |
| `web/REVIEW-SPEC-FINAL-20261017.md` | `d9f6d7ff4a05fca401845e79415a05ab0397b52de2921701dd3a2f311eea2633` |

This verdict applies to the artifacts identified above; any subsequent change to a reviewed source or test invalidates the corresponding review basis.
