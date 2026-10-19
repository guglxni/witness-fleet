# Verification status

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
