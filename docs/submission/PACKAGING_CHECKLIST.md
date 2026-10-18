# Package readiness and participant actions

Keep technical readiness separate from organizer submission. A verified repository or deployed demo does not mean an entry was submitted; a submitted form does not prove the code or claims.

## Technical readiness evidence

### Pinned source proof

- [x] Core source commit [`51e789daf75fff7f8bb29b84523679813449aa7d`](https://github.com/guglxni/witness-fleet/commit/51e789daf75fff7f8bb29b84523679813449aa7d) passed [Verification run 39104896235](https://github.com/guglxni/witness-fleet/actions/runs/39104896235): 935 main and 10 corpus tests; zero failures, errors or skips; lint, both frontend test/build jobs and browser-test steps passed.
- [x] [Azure deployment run 39105369889](https://github.com/guglxni/witness-fleet/actions/runs/39105369889) deployed and read back that same source revision.
- [x] A hosted mission integration test checks the release gate, absence of pre-release courier commands, all seven verified tasks and the native delivery postcondition.
- [x] Judge materials now link the [five-condition walkthrough](JUDGE_GUIDE.md), [three-minute script](DEMO_SCRIPT.md), [execution map and full claim query](RUNTIME_QUERIES.md), [FalkorDB rationale](WHY_FALKORDB.md), and [AI-use disclosure](SUBMISSION_BRIEF.md#ai-assistance-and-runtime-behavior).
- [x] Preserved film files, sanitized provenance and campaign credit records remain linked from the [README](../../README.md#product-site-and-preserved-media).

### Verification for an integrated revision

- [ ] Check the Verification run attached to the source commit. The pinned runtime CI above does not replace verification of later revisions.
- [x] The proof-first site passed local typechecking, 49 component/unit tests, its production build, and 32 browser tests. These checks are frontend-scoped, not a replacement for full runtime CI.
- [ ] For a production update, verify the deployed revision and read back the live assets and interactive page.
- [x] The sanitized receipt matches the retained manifest and its source hash; the displayed query preserves all 602 executable tokens. Media credits and prior films remain attached to their artifacts.

## Participant actions in the organizer flow

- [ ] Select Track 01 as primary and Track 02 / Track 03 only if their scoped descriptions are understood and intended.
- [ ] Review the project summary and AI-use disclosure; be prepared to explain the implementation, queries and technical choices.
- [ ] Confirm the repository, live simulation and video links open and show the intended material.
- [ ] Complete the organizer registration/submission flow yourself and retain its receipt. This repository and the hosted demo do not confirm that an entry was submitted.
- [ ] Follow any organizer-specific eligibility or rights fields truthfully. Do not claim manual authorship of every line or independent human assurance from AI-assisted review.

## Scope and rights notes

SC-001 is a deterministic simulation, not physical robotics, production identity, or safety certification. The unauthorized-execution metric is unknown (`null`), not zero. Original application code is MIT; FalkorDB server is SSPL; GSAP uses its Standard License; ElevenLabs is proprietary. The film also contains HyperFrames-produced material, recorded MuJoCo footage and an OpenDesign Motion excerpt; see the preserved credit files and [third-party notices](../../THIRD_PARTY.md). Do not label the whole stack OSI FOSS.
