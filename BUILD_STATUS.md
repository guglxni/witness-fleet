# Verification status

## GitHub CI verification

On 18 October 2026, [Verification run 39103193098](https://github.com/guglxni/witness-fleet/actions/runs/39103193098) passed on commit `d0105b5f7324b17de5f19160873388d167ee7d5d`: **935 main + 10 corpus tests**, zero failures/errors/skips, and both frontend jobs (typechecking, unit tests, production builds and browser tests). Counts were read from downloaded JUnit artifacts, not inferred from the workflow badge. This supersedes the older local full-suite count below for that revision. Use the [live workflow page](https://github.com/guglxni/witness-fleet/actions/workflows/verify.yml) to check newer commits; this is not a claim that an untested newer revision has passed.

## Executed locally

- Full partitioned regression after adding the hosted gateway: **932 main tests + 10 corpus tests**, no failures/errors/skips. Run occurred before the later process-lock ordering repair.
- Process-lock repair: regression-first failure reproduced a losing gateway mutating the active-session ledger. Lock acquisition now precedes ledger initialization. **9 focused tests passed**, including the real seven-task hosted HTTP mission; independent bounded verification also passed.
- Launch frontend: **8 unit tests**, production build, **7 browser tests**. Production checked at 320, 390, 768 and 1440 pixels: no horizontal overflow or page errors; film playback verified.
- Film: 86 seconds, 1920×1080, AAC audio, full FFmpeg decode check, sampled encoded frames and audio-level analysis. Served Vercel bytes match the delivered file.
- Diagrams: three editable sources and five rendered artifacts; diagram validation passed.

## Limits

These are software/simulation checks, not hardware commissioning or safety certification. Tests are not a substitute for exact deployed-commit verification. The film contains native simulation evidence plus separately identified designed explanation; captured release uses a configured synthetic demo owner.

Cloud deployment and GitHub Actions status should be checked on the exact current revision. Historical local reports and persistent data are retained privately, not published as a claim of production approval.
