# UI implementation review · 2026-10-17

## Scope and verdict

Read-only review of the delivered UI against `web/api-contract.ts`, `DESIGN.md`, `DEMO.md`, `SCENARIO_ACCEPTANCE.md`, the changed frontend tests, and the actual implementation. No application source, tests, contract, design file, or build metadata was changed. The UI follows the evidence-first direction well overall: it does not infer physical clearance from poses, separates task rows from command/receipt records, distinguishes controller receipt from verified outcome, labels the hero statement as a principle, and keeps the connected E2E fixture test-only. However, the findings below leave explicit-state and design-contract gaps; passing tests do not close them.

## Findings

1. **[P1] Missing incident state is rendered as a negative dispatch verdict.** `src/App.tsx:241` uses `projection?.dispatch_ready ? 'Dispatch gate reports ready' : 'Dispatch gate not ready'`. With no projection, optional chaining yields the false branch, so the overview says “Dispatch gate not ready” while the decision-principle panel correctly says “Unavailable.” An absent verdict is unknown/unavailable, not a backend denial. Preserve the explicit unavailable state in this summary too.

2. **[P1] An offline refresh retains cached projection without explicitly marking it stale.** `src/App.tsx:79-82` switches to `offline` and keeps the prior projection; only the SSE `stale` state gets the cached-state banner (`:234`). The freshness row (`:299`) reports “Revision N observed” for `offline`, while the retained dashboard remains visible. Writes are locked, but the cached projection itself is not labeled stale as required by `DESIGN.md`. When refresh fails with a projection already present, mark the retained view stale/offline and identify its revision/time as cached; keep controls locked.

3. **[P2] The live gate list omits the independent Policy gate.** `src/App.tsx:296-300` presents Physical, Dispatch, Claim, and Freshness. Dispatch readiness is separately and correctly described as backend-owned, but it is not a policy-permission verdict. The contract has no explicit policy-permitted field, so show Policy as unknown/not exposed rather than substituting Dispatch; retain Dispatch as an additional backend gate. This aligns the four independent Physical / Policy / Claim / Freshness rows in `DESIGN.md` without inventing a result.

4. **[P2] A successful HTTP response is styled as green acceptance.** `src/App.tsx:149,351` maps every successful control/incident response to `kind: 'accepted'` with a green check; `.result-accepted` in `src/styles.css:219` uses the verified-success palette. The text does say “response received,” and it does not claim a physical outcome, but the success icon/color collapses transport/API response with accepted/verified status. Use a neutral response-received state, or render the backend's explicit receipt state distinctly; reserve green for verified outcomes per `DESIGN.md`.

5. **[P2] Witness graph references an undefined arrow marker.** `src/App.tsx:422` sets `markerEnd="url(#witness-arrow)"`, but the SVG only defines the grid pattern (`:261`) and has no `<marker id="witness-arrow">`; the `.witness-arrowhead` CSS class is not attached to any marker. Edge direction therefore lacks the specified arrowheads. The adjacent textual edge listing does preserve source → relationship → target, so this is a graph-visualization conformance gap rather than missing edge data.

6. **[P2] Typography is substantially below the design's stated minimums.** The design asks for 16–20 px main reason text and metadata no smaller than 13 px. `.reason-lead` is 13 px on desktop/12 px at narrow widths; much of the metadata/status/table text is 8–11 px (`src/styles.css`, e.g. lines 51–58, 103–16, 121–25, 153–58, 301–29, 333–43). The actual 320 px screenshot has no horizontal overflow, but those small labels are difficult to read and do not meet the token guidance. Increase critical reason and metadata sizes or reduce secondary density while preserving the narrow layout.

## Correctly handled / residual contract limits

- The hero sentence is visibly caveated as a decision principle, not a live episode claim. S0 poses and empty observations never imply physical clearance; absent incident state has an explicit waiting state and no fabricated roster.
- Tasks/dependencies, command state/reconciliation, and missing verified outcome are distinct. Source identity/text/revision/hash/normalizer and backend witness edges/spans are rendered from responses; no fixed fixture state is seeded in the live app.
- Step/run are gated by backend dispatch readiness; hold remains available when a projection is gated. Approval confirmation starts unchecked, is bound to release and policy epoch, and submits only the contract payload. Structured backend denial codes are preserved.
- The contract does not expose a courier-specific physical-clearance verdict or complete approval scope/approver identity. The UI correctly reports physical unknown and labels approval as a request preview; actual source effective intervals/expiry and full real-fleet currentness must not be claimed until backend fields/evidence exist. The connected E2E projection is synthetic test-only data, not live-backend proof.

## Verification performed

Commands run in `web/` on the current implementation:

- `npm test` — **24 passed**, 3 test files.
- `npm run typecheck` — passed (`tsc -b`).
- `npm run build` — passed; Vite emitted the production bundle.
- `npm run test:e2e` — **6 passed** (desktop/mobile Playwright projects; empty-state, 320 px narrow empty-state, and explicitly synthetic connected projection).

Inspected actual Playwright screenshots under `web/test-results/`: desktop and narrow waiting state, plus the desktop/mobile synthetic connected projection. The empty-state E2E checks 320 px horizontal overflow; the connected projection checks no overflow in its mobile project. These are browser-test captures, not evidence of a complete live fleet.

## Reviewed artifact hashes (SHA-256)

- `src/App.tsx`: `ba43173d8250ad4d094fb74128b2cd103855fba0aa6005eef00134ca68d38d70`
- `src/api.ts`: `f02d1b440017fb150e845f8f6f79ba35d89a71146dae362840d4544fefef35ab`
- `src/state.ts`: `a94014c70028b15a052b4a7fb5e831512f67c359e1fb377e15ba0874c8498f81`
- `src/styles.css`: `bc5fb07cc85d9b11fc525ed1d902ddd129b553f26ad297143918f14ba24a943b`
- `tests/operator-console.test.tsx`: `a645caf0ca7420ad8fbd69e89325cc6c042d78c05cbf01c7dcdf6b7c0a4a2f63`
- `e2e/local-waiting.spec.ts`: `37580adc2ec07156a4aa2cd3d63f37263f98cd1d27a1e236e83d3e5686f0022b`
- `api-contract.ts`: `01d1f6370e2c460c34b55a923591edb41245e9e369ff131a5757accc479d1052`
- `DESIGN.md`: `ee84c2862ba2892814fc3bff30eff2e05d4d432adf59a7085cb5306fe56fe0c8`

Review is limited to UI/spec compliance and the listed frontend checks. It does not certify backend integration, real-fleet evidence, physical safety, or hackathon submission readiness.
