# Frontend implementation report · 2026-10-17

## Scope

Redesigned `web/` as a dark, industrial Witness Fleet operator console aligned to the project `DESIGN.md` and Linear's restrained information hierarchy. `web/api-contract.ts` was not edited. No backend, documentation outside `web/`, generated assets or commits were changed.

## UX and interaction changes

- Reframed the operator's core message as **“Physically clear. Loaded courier still restricted.”** with a clearly labeled *decision principle — not a live episode claim*. Physical clearance remains `Unknown`; neither robot poses nor empty observation arrays imply a clear route. The contract has no explicit courier-clearance verdict.
- Added a live-gate summary, independent backend dispatch status, returned hold reason, graph/policy/coordinator epochs, and dispatch sequence. Connection, stale, unavailable, and empty-projection states remain visually explicit.
- Renamed the scene to “Robot pose projection” and show only backend-projected S0 robot coordinates in a dynamically framed plot; clearly disclaim inferred facility geometry.
- Separated task/dependency rows from command/receipt records. Command projection status and reconciliation remain separate from outcome verification; absent verified outcomes are identified as absent, not simulated.
- Kept source identity, exact returned text, owner/revision/hash/normalizer metadata, and witness graph/table/edge/span displays API-linked. Added lazy retained-source loading through the existing `GET /api/sources/{revision_id}` endpoint.
- Recast approval as a supported backend request preview; explicitly calls out scope limitations and backend rejection/stale possibilities, shows returned restriction records when present, leaves confirmation unselected, and binds the existing epoch/event ID payload.
- Preserved stale-SSE monotonic snapshot handling and explicit hold/step/run semantics. Structured backend error codes now display with their HTTP status; offline/checking/stale states all lock mutations.
- Respected the existing deterministic model-disabled label; no scores or fixture-backed data are used in live app code. Synthetic projections exist only as explicitly labeled tests.
- Reworked responsive layout and contrast, native form styling, keyboard focus, skip navigation, reduced-motion behavior, table alternatives and long-text wrapping.

## Files changed

- `web/src/App.tsx`
- `web/src/styles.css`
- `web/src/api.ts`
- `web/tests/operator-console.test.tsx`
- `web/e2e/local-waiting.spec.ts`
- `web/IMPLEMENTATION-20261017.md` (this report)

## Verification

- `npm test`: **24 passed** (Vitest).
- `npm run typecheck`: passed.
- `npm run build`: passed (Vite production bundle).
- `npm run test:e2e`: **6 passed** (Playwright desktop/mobile empty and 320px waiting states, plus a synthetic connected projection).
- Real local backend smoke: `GET /api/state` returns **503**, health endpoint remains reachable; frontend reports waiting and renders no robot projection until actual state exists.
- Screenshots saved by Playwright under ignored `web/test-results/`: `evidence-first-waiting.png`, `evidence-first-waiting-narrow.png`, and `synthetic-connected-projection.png` (desktop/mobile projects).
- SHA-256: `src/App.tsx` `ba43173d8250ad4d094fb74128b2cd103855fba0aa6005eef00134ca68d38d70`; `src/styles.css` `bc5fb07cc85d9b11fc525ed1d902ddd129b553f26ad297143918f14ba24a943b`; `src/api.ts` `f02d1b440017fb150e845f8f6f79ba35d89a71146dae362840d4544fefef35ab`; operator tests `a645caf0ca7420ad8fbd69e89325cc6c042d78c05cbf01c7dcdf6b7c0a4a2f63`; E2E `37580adc2ec07156a4aa2cd3d63f37263f98cd1d27a1e236e83d3e5686f0022b`.

## Limits / follow-up

The current supplied projection contract does not expose a semantic, courier-specific physical clearance result or full approval scope/approver identity. UI labels those unavailable instead of inferring them from S0 positions or populating fabricated sample state. Live connected visuals were exercised with a synthetic Playwright route fixture only; actual backend projection remains unavailable (503) and should be checked by the parent after backend integration. No production authentication, physical safety certification, or real-world operation is claimed.
