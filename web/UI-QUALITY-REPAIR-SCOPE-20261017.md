# UI QUALITY repair scope - 2026-10-17

Predecessor: `REVIEW-QUALITY-FINAL-20261017.md` (completed deleg_62344231, BLOCKED). Source hashes matched before repairs. Earlier UI SPEC is historical, not acceptance of these changed files.

## Bounded requirements

1. StatusTag must use exact positive status mapping. UNVERIFIED, NOT_VERIFIED, suffixes/prefixes, controller completion and unknown outcomes must never receive verified color/check. Exact VERIFIED and OUTCOME_VERIFIED remain positive.
2. Different episode IDs have no inherent ordering. Generic acceptSnapshot rejects episode changes by default; same-episode revisions cannot regress.
3. REST bootstraps state. A latest still-current REST refresh or incident-creation response may establish another episode, including a reset revision. Controls may not establish episodes. No backend/global monotonic episode token is invented.
4. Fence older REST requests and callbacks captured in an earlier episode generation. Old failures must not alter the current link. Fence old action responses/errors. In-flight reads begun before a write are superseded.
5. One active SSE connection only, scoped by instance and episode generation. Queued callbacks from closed streams do nothing. Older/wrong-episode snapshots must not refresh freshness. Active episode mismatch locks controls; requires a REST refresh begun after mismatch, then a valid scoped stream snapshot to resume fresh connection display. This is UI projection freshness only, not motion authorization.
6. Remove competing startup one-shot SSE hydration; replay still reads projected events. Preserve API/contract compatibility, no backend modification.
7. Approval confirmation/payload, source cache, witness loading/evidence and old action messages must not bleed across episode changes. Unknown-outcome idempotency IDs are reusable only inside the same episode; UI does not reconcile backend outcomes.
8. Preserve design/readability, non-authoritative response labels, stale/offline write lock and no fabricated data.

## Owned edits

- `web/src/state.ts`
- `web/src/App.tsx`
- `web/tests/state.test.ts`
- `web/tests/status.test.ts`
- `web/tests/projection-races.test.tsx` (new, explicit synthetic transport fixture)

No backend/runtime/graph/simulator edits. No real control request, public deployment, paid inference, commit or submission. All pending lease/outcome/reconciliation paths remain blocked.

## Local evidence before independent review

Regression-first slices observed actual behavioral failures for substring status positives, unconditional episode replacement, valid scoped episode switching after deny-by-default, latest refresh switching, late action replacement, old stream error callbacks, rejected stream freshness, competing hydration, malformed episode identity, approval carryover, witness carryover, source carryover, stale REST freshness and mismatch locking. Existing behavior and final regression-strengthening cases that first passed are not claimed as RED.

`npm test -- --reporter=default --reporter=junit --outputFile.junit=test-results/ui-quality-repair-unit.xml`: 58 passed across 4 files (21 race/render cases, 17 operator cases, 12 state cases, 8 status cases), no skips. Typecheck and production build passed. Emitted `index-DoIUqIvP.js`; CSS remains `index-BxI07yES.css`. The build preserves previous dist files (`emptyOutDir:false`). Responsive/live verification and independent reviews are tracked separately, not inferred from these tests.

## Review rules

Review source hashes, not timestamps or counts. Specification review precedes QUALITY. Reviewers may write only their own reports and test outputs; no source changes or backend/graph/native actions. Any blocking finding keeps UI acceptance open. UI acceptance never implies integrated fleet acceptance.
