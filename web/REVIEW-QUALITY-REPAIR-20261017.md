# Independent UI QUALITY / security review — 2026-10-17

## Verdict and scope

**PASS — no blocking findings in the frozen frontend within the bounded UI repair scope.** I independently reviewed the current App/state paths, their regression tests, API validation boundary, styles, contract and DESIGN.md, plus the scope/verification reports and predecessor QUALITY/SPEC reviews. The two predecessor QUALITY findings are closed in the inspected bytes: positive status styling is exact-state-only, and cross-episode snapshots are deny-by-default except at guarded REST/incident establishment paths.

This is frontend quality/security review only. It is not acceptance of backend authorization, fleet/runtime behavior, motion, physical safety, or hackathon readiness. Client-side stale locks are UI behavior, not an authorization boundary. The SPEC PASS is supporting context, not a substitute for this review.

## Findings

**None blocking or non-blocking within the reviewed scope.**

### Evidence for the repaired paths

- `web/src/state.ts:13–19`: only normalized exact `verified` and `outcome verified` receive the verified tone. Unknown/prefixed/suffixed values are neutral or explicitly unresolved; `controller done` and `completed` remain in-progress. `StatusTag` uses that single tone to select both CSS class and glyph (`web/src/App.tsx:417–420`). The status tests cover `UNVERIFIED`, `NOT_VERIFIED`, variants, controller completion, and `OUTCOME_VERIFIED`; rendered regressions check class and glyph.
- `web/src/state.ts:3–10`: `acceptSnapshot` refuses episode changes by default and rejects non-increasing revisions within one episode. In `App.tsx`, only refresh and incident creation pass episode-change authority; ordinary controls and SSE do not. REST refreshes are fenced by request sequence and episode generation; mutations invalidate pre-write reads; old action responses/errors are generation-checked (`App.tsx:63–103, 171–196`).
- Stream callbacks are tied to active `EventSource` identity and episode generation; cleanup closes old sources, and queued callbacks are ignored (`App.tsx:111–155`). Wrong-episode stream state latches stale and locks writes; a matching stream snapshot cannot alone clear the mismatch—REST must re-establish state first. Older same-episode snapshots do not restore freshness (`App.tsx:124–145`).
- Episode changes clear witness, witness errors/loading, action result, and retained request IDs. Witness responses are generation-checked; approval confirmation and payload identity include episode/release/policy scope and request version; retained source cards include episode identity in their React key (`App.tsx:44–50, 63–77, 229–247, 358–362`). These are UI isolation properties, not backend outcome reconciliation.
- API state and POST responses are structurally checked before use; caller-controlled path identifiers are encoded at use sites. Dynamic projection values in the reviewed UI are rendered as React text. A targeted source scan found no `innerHTML`, `dangerouslySetInnerHTML`, `eval`, `new Function`, or `document.write` sink in `web/src`.

## Checks run

From `web/`:

- `npm test` — **passed: 4 test files, 58 tests**.
- `npm run typecheck` — **passed** (`tsc -b`).
- In repo root, `git diff --check` — exit 0. The frontend tree is untracked in the larger worktree, so this check does not constitute a tracked diff review.
- SHA-256 manifest verification against `artifacts/showcase-20261017/ui-quality-repair/frozen-hashes.json` — **12/12 entries matched**.
- Targeted dynamic-HTML/eval sink scan under `web/src` — **0 matches**.

I did not repeat the parent's E2E, live read-only viewports, production bundle race probe, or build. Their results are reported in `UI-QUALITY-REPAIR-VERIFICATION-20261017.md`, but are not represented as checks I ran. No backend, Python, graph, simulator, service, or live API tests were run; no real POST/control request, permission-sensitive action, service restart, secret access, or paid inference was used.

## Review basis — exact SHA-256

Measured with `shasum -a 256` in the repository. Hashes bind this verdict to the exact current bytes; source/test changes require a new review.

| Artifact | SHA-256 |
|---|---|
| `web/src/App.tsx` | `fabfea8e882ed3e2013f09b61007ab2e147f6fef98de3bd5f989da0e01ddd872` |
| `web/src/state.ts` | `ee9d8f3452907bd37f7029a4106d1adb8ada01d60408df7065f8239ba4a212cd` |
| `web/src/styles.css` | `5f3e16248169df13a86cb01fc615a8e7e5c0bbf077667e6fcd206c6f0b6e8117` |
| `web/src/api.ts` | `f02d1b440017fb150e845f8f6f79ba35d89a71146dae362840d4544fefef35ab` |
| `web/api-contract.ts` | `01d1f6370e2c460c34b55a923591edb41245e9e369ff131a5757accc479d1052` |
| `web/tests/state.test.ts` | `0799f0914c5bc0c331c44420079dc0bb1d3382560ddbcaa347c5423ac74d51a5` |
| `web/tests/status.test.ts` | `52d41b6501702475952a7af4a996613dd9ffa4e5e4c4b0865dbce9d53184b200` |
| `web/tests/projection-races.test.tsx` | `0940a2ab262067bd811d0d990c7491f096b63fc8f98b8d5143f48734cbbe03c4` |
| `web/tests/operator-console.test.tsx` | `95ce51b712315e4d3850bf0432d3636a7ad01c8d297f47a7d208b5ac95861876` |
| `web/e2e/local-waiting.spec.ts` | `f15f93433a9d3921e0d823b51d001b90e9e95c81ff00069b45695ce1cc37ae77` |
| `web/e2e/evidence-readability.spec.ts` | `cb28bd2b53aea141c457cd004a659a1d9e3c3e057a44100f7b29bde7b005e7c7` |
| `web/package.json` | `95a67b4c3fd228b4026c72883048225486e8af289ce19f536803a54238bbbd3e` |
| `DESIGN.md` | `ee84c2862ba2892814fc3bff30eff2e05d4d432adf59a7085cb5306fe56fe0c8` |
| `web/UI-QUALITY-REPAIR-SCOPE-20261017.md` | `d6d2bea63def2c48a84a73d3a44ea70bc24b59eaae20aaf518abd4e08161b3f1` |
| `web/UI-QUALITY-REPAIR-VERIFICATION-20261017.md` | `0a6c60bb3a54262a19f49fbd300c79c79a964284d491b6e003e40919dc2a5808` |
| `web/REVIEW-QUALITY-FINAL-20261017.md` | `f776fd014e5d4453aa23fdbfbc1124060dcbe6e2430dbbe7f4407001685c4b4f` |
| `web/REVIEW-SPEC-QUALITY-REPAIR-20261017.md` | `9513083d2220b4ebca531f90662c9ae01fe76f427640b6b86331bf3dae123567` |

## Limitations and boundary

- Frontend tests and race fixtures are synthetic. They verify UI projection behavior but not server-side authorization, idempotency semantics, distributed ordering, or actual fleet outcomes.
- There is no global monotonic episode token in this frontend contract; cross-episode order is intentionally not inferred. REST establishment is a UI authority defined by the bounded scope, not proof of backend freshness.
- Browser-based E2E and real read-only live probes were not rerun in this independent review. No deployment or physical-device testing was performed.
- Worktree `HEAD` is `16e0a539a83abac4ec925c0908d261e91cf4a3eb` on `main`, but the web tree is untracked; this report binds exact source hashes, not a committed frontend diff.
- No production/test files were edited. Only this independent review report was created.
