# Verification status

## Scientific-interface release

The scientific interface is published. Runtime commit
[`289489c`](https://github.com/guglxni/witness-fleet/commit/289489ca4adff91177c6faeaec1bbdcb1b49c91c)
passed [Linux Verification](https://github.com/guglxni/witness-fleet/actions/runs/39239468093)
and [Azure deployment](https://github.com/guglxni/witness-fleet/actions/runs/39240476155).
The live Azure health revision matched; a fresh public browser session completed
seven verified tasks/commands and one delivery, with no courier before the explicit
synthetic release. Subsequent site/docs-only commits do not replace this runtime.
Its release checks are:

| Surface | Verification |
| --- | --- |
| Python runtime + corpus | 972 tests: 961 main + 11 isolated corpus; zero failures, errors or skips |
| Public website | 64 unit/component tests + 48 Chromium browser tests; typecheck and production build pass |
| Hosted workbench | 25 unit/component tests + 9 Chromium browser tests; typecheck and production build pass |
| Local operator console | 77 unit/component tests + 12 Chromium browser tests; typecheck and production build pass |
| Native hosted path | Fresh isolated FalkorDB + native MuJoCo via actual HTTPS/UI: seven verified tasks and commands, explicit release gate, one delivery |

The native path was checked at eleven viewport sizes including short landscape:
no document/body horizontal overflow, no application page errors or failed assets,
and no WCAG A/AA violations in the checked completed desktop state. Viewport
emulation is not physical-device testing. The fixture-driven browser suites and
native end-to-end mission are distinct checks, not interchangeable evidence.

The screenshot repairs include uniform dark code panels, native-size scrollable
schema labels, full-ID receipt inspection/copying and responsive receipt layout.
The hosted workbench rejects incomplete scenes, labels 2D approximations, disables
unsupported fallback modes, and excludes hidden layers from scene selection.
All ambiguous mutation outcomes still fail closed; history is read-only.

The runtime container was built and its packaged JS/CSS/fonts were exercised over
container-local HTTP. The scan identified inherited base-image/tooling findings,
including high/critical entries; independent bounded comparison found no new
candidate vulnerability entries. This is **not a zero-vulnerability claim**.
Unpatched dependencies remain a disclosed risk. See the interface and deployment
guides for the authority boundary and exact-revision publication requirements.

The records below remain historical proofs; their counts are not the current suite.

## Pinned core proof

[Verification run 39104896235](https://github.com/guglxni/witness-fleet/actions/runs/39104896235) passed on source commit [`51e789daf75fff7f8bb29b84523679813449aa7d`](https://github.com/guglxni/witness-fleet/commit/51e789daf75fff7f8bb29b84523679813449aa7d). The isolated Python job reported **935 main tests + 10 corpus tests**, with zero failures, errors or skips. Ruff passed. Both frontend jobs passed their typecheck, unit-test, production-build and Playwright steps on that same commit.

[Azure deployment run 39105369889](https://github.com/guglxni/witness-fleet/actions/runs/39105369889) also passed for that exact source commit. Its job built and pushed the tested source, deployed it, and checked the public revision. The associated [deployment evidence](docs/guide/deployment-evidence.md) describes the public mission read-back and its simulation-only scope.

These are proofs for the linked runtime commit, not an evergreen green light. Later website and documentation revisions have separate verification; use the Actions run attached to the exact source commit.

## Website verification

The proof-first website was exercised locally with **50 component/unit tests and 33 browser tests**, zero failures or skips. Browser coverage includes the recorded-evidence inspector at ten viewport widths, keyboard access, WCAG checks, the single YouTube player, archived-media hashes, favicon assets and static-control non-mutation checks. Typechecking and the production build passed. The retained receipt was checked against the original capture manifest; all 602 tokens of the formatted claim query match the source literal. These are frontend and document checks, not a fresh full runtime certification.

The runtime deployment workflow compares the successful CI revision with the healthy live runtime's exact commit. Site/docs-only changes skip the Azure replacement; changes to runtime inputs still require the existing deployment and public-revision verification. Unknown comparison or health state stops the job rather than guessing.

## What the tests establish

The source commit's test manifest includes a hosted HTTP mission against isolated FalkorDB and native MuJoCo. It asserts a seven-task session with scout, recovery and courier roles; recovery and verification before the owner gate; no courier command before explicit release; then seven `VERIFIED` tasks and seven `OUTCOME_VERIFIED` commands. The native delivery receipt checks `payload_in_delivery_zone` is true. This supports an implemented synthetic simulation path, not a physical robot claim or authenticated human approval.

The metric `unauthorized_executed` remains **null** in the public evidence; it is not reported as zero. Model inference is not used by the SC-001 control path.

## Limits and next verification

- Software and MuJoCo simulation checks are not hardware commissioning, safety certification, or sim-to-real validation.
- A successful HTTP receipt is not itself proof of physical outcome; inspect the linked native postcondition and test assertion.
- Runtime-baseline CI at `51e789d` is distinct from the current website checks above.
- CI, Vercel deployment and public read-back must be checked against their exact source revision; a badge alone is not evidence of deployment parity.

The workflow status badge and current Actions history are available at [Verification](https://github.com/guglxni/witness-fleet/actions/workflows/verify.yml) and [all Actions runs](https://github.com/guglxni/witness-fleet/actions).
