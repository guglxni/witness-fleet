# Final independent UI QUALITY review · 2026-10-17

## Scope and verdict

Reviewed the frozen Witness Fleet frontend only: render/state handling, API boundary, styles, DESIGN.md, targeted tests, completed SPEC review and parent verification. No implementation or test files were changed; no backend controls, graph requests, service restarts, or live runtime actions were run. The completed SPEC dispositions remain supported, but **UI QUALITY is not accepted**: two concrete state/status correctness issues remain in the reviewed code. This is not backend, fleet-motion, physical-safety, or hackathon-readiness acceptance.

## Blocking findings

1. **High — unverified status strings can render as verified/green.** `web/src/state.ts:11–16` tests `/outcome verified|verified/` after its unresolved patterns. Consequently `decisionStateTone('UNVERIFIED')` and `decisionStateTone('NOT_VERIFIED')` both return `verified`; `StatusTag` in `App.tsx:386–389` then renders the verified class and check glyph. That is a misleading positive state for plausible status values and violates DESIGN.md's distinction between verified outcomes and unresolved states. Match explicit normalized states (or use a deny-by-default mapping) and add regression cases for `UNVERIFIED` and `NOT_VERIFIED`, ensuring neither is styled/marked as verified.

2. **High — snapshots from a different episode always replace the displayed episode, regardless of age/source.** `acceptSnapshot` in `web/src/state.ts:3–9` accepts every incoming projection when episode IDs differ. The UI calls it for independently completing REST refresh/action responses and both event streams (`App.tsx:60–66, 101–108, 135–143, 156–158`). A delayed snapshot for an earlier episode can therefore replace a newer one, and the visible dispatch/freshness context and action affordances can be based on that stale projection. The existing state test at `web/tests/state.test.ts:17–20` asserts unconditional cross-episode replacement, so it does not guard against the race. Add request/stream generation or equivalent freshness authority for episode changes; test that late old-episode REST/SSE snapshots cannot replace the current projection. Backend authorization is outside this review.

## Positive review notes

- UI copy and structure keep backend dispatch readiness distinct from physical clearance, policy/claim unknowns, and verified outcomes; action responses are not presented as accepted or physically verified.
- Projection and witness data are validated before rendering; request path identifiers are URL-encoded; dynamic content is rendered as React text rather than injected HTML.
- Controls lock on stale/offline states; approval requires an unchecked confirmation tied to release/policy scope; evidence has a table alternative and the graph scroll region is keyboard-focusable.
- The completed SPEC review's six findings were closed on its hash-bound artifacts. The parent verification reports responsive checks at 11 viewports; that broader parent verification was read, not repeated here.

## Executed checks

From `web/` during this review:

- `npm test` — **26 passed**, 3 test files.
- `npm run typecheck` — passed.
- `npm run test:e2e -- e2e/evidence-readability.spec.ts --project=desktop` — **2 passed** (320px and 1440px).
- Read-only focused probe of `decisionStateTone` confirmed `UNVERIFIED` and `NOT_VERIFIED` currently return `verified`; cross-episode `acceptSnapshot` returns the incoming projection even when its episode is an old one.

No build or broad backend suite was run. Test success does not supersede the two findings above.

## Exact reviewed input hashes (SHA-256)

| Artifact | SHA-256 |
|---|---|
| `web/src/App.tsx` | `ea6ea65f6746521e588ea3a79f30f73d116ca022c89e91d4cc145b064cffbd87` |
| `web/src/styles.css` | `5f3e16248169df13a86cb01fc615a8e7e5c0bbf077667e6fcd206c6f0b6e8117` |
| `web/src/api.ts` | `f02d1b440017fb150e845f8f6f79ba35d89a71146dae362840d4544fefef35ab` |
| `web/src/state.ts` | `a94014c70028b15a052b4a7fb5e831512f67c359e1fb377e15ba0874c8498f81` |
| `web/tests/operator-console.test.tsx` | `95ce51b712315e4d3850bf0432d3636a7ad01c8d297f47a7d208b5ac95861876` |
| `web/tests/state.test.ts` | `c20c76ba8061b27a071d0656c606e84d97e09d142cb615cae1e4bf951e3a561c` |
| `web/tests/status.test.ts` | `730ee67a6485e34498c8653b37e19c392db5a59aa83eb5718535a96c9e878c3a` |
| `web/e2e/evidence-readability.spec.ts` | `cb28bd2b53aea141c457cd004a659a1d9e3c3e057a44100f7b29bde7b005e7c7` |
| `web/e2e/local-waiting.spec.ts` | `f15f93433a9d3921e0d823b51d001b90e9e95c81ff00069b45695ce1cc37ae77` |
| `web/api-contract.ts` | `01d1f6370e2c460c34b55a923591edb41245e9e369ff131a5757accc479d1052` |
| `web/package.json` | `95a67b4c3fd228b4026c72883048225486e8af289ce19f536803a54238bbbd3e` |
| `DESIGN.md` | `ee84c2862ba2892814fc3bff30eff2e05d4d432adf59a7085cb5306fe56fe0c8` |
| `web/REVIEW-SPEC-FINAL-20261017.md` | `d9f6d7ff4a05fca401845e79415a05ab0397b52de2921701dd3a2f311eea2633` |
| `web/PARENT-VERIFICATION-20261017.md` | `96cd5a7e634a14ae485b702bda5a4df8ef3167ae9dca8a3b5b161644c3f5c946` |

The artifacts above identify the exact review basis; changes to any listed UI source or test artifact invalidate this hash-bound review.