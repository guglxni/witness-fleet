# Deployment evidence

## Live endpoints

- Product: https://witness-fleet.vercel.app
- Interactive simulation: https://witness-fleet-guglxni.eastus.cloudapp.azure.com/demo
- Minimal process health: https://witness-fleet-guglxni.eastus.cloudapp.azure.com/healthz

## Scientific-interface release status

The scientific-interface candidate passed its local native mission, responsive
browser suites, production builds and container packaging checks. The authoritative
local counts are in [verification status](../../BUILD_STATUS.md). These are local
results, not evidence that either live endpoint already runs the candidate.

Publication requires a signed commit, its successful CI and exact GitHub/Vercel/Azure
revision read-back. Before replacement, the retained production graph identity,
graph-name digests and six prior session-directory hashes were captured. A release
must preserve those records; a new isolated validation session is additive.

## Historical exact-revision acceptance

Commit `5f0a4c44cc54d3d372a4f09a419c7903f4525ed7` passed [Verification](https://github.com/guglxni/witness-fleet/actions/runs/39103988777): 935 main + 10 corpus tests with zero failures/errors/skips; 73 console + 8 site unit tests; 12 console + 7 site browser tests; both typechecks and production builds. Counts were read from JUnit artifacts and completed job logs.

[Azure automatic deployment](https://github.com/guglxni/witness-fleet/actions/runs/39104478395) passed. Azure `/healthz` and Vercel production `gitSource.sha` both matched that exact commit. The initial OIDC login failure was corrected by matching GitHub's immutable repository/owner subject, without adding long-lived secrets or broader roles.

A headless Chromium test then drove the public `/demo` controls through a fresh isolated session: recovery verified, four commands completed with **no courier command before the gate**, visible release confirmation, explicit synthetic release, then all **7 tasks VERIFIED** and **7 commands OUTCOME_VERIFIED**. Delivery's measured `payload_in_delivery_zone` effect was true. A separate GET read back the final state; revision checks before and after matched; no page errors occurred. This verifies the public simulation, not physical hardware or production human-owner identity. The `unauthorized_executed` metric remains null, not zero.

Newer documentation-only revisions still require their own CI/deployment read-back. Use Actions and the live endpoints rather than treating this dated record as a claim about every future commit.

The live site and demo also passed **22 route/viewport checks** in headless Chromium (320, 360, 375, 390, 414, 430, 768, 1024, 1165, 1440 pixels, plus 844×390 landscape, on each route), with no document/body horizontal overflow or page errors. Mobile navigation, reduced-motion keyboard stage selection, and actual user-triggered film playback passed. The served film reported 86 seconds, 1920×1080 and one caption track. These are browser checks, not physical iOS/Android testing.

## Earlier cloud acceptance

The first Azure HTTPS run returned `complete`, with **7 tasks VERIFIED**, **7 commands OUTCOME_VERIFIED**, **recovery_verified=1**, and **delivery_completed=1**. The same final request ID returned an identical response. Missing Origin was rejected and `/api/state` remained inaccessible. Real native payload-placement evidence was verified through the corresponding Linux integration test.

The unknown `unauthorized_executed` metric remains null; it was not substituted with zero.

The site’s served launch MP4 SHA-256 matches the delivered 86s/1080p narrated file:
`1f781361d281df09999c7051d066c1d610ced861c6932a16fad2a8afe78bc869`.

## Revisions and automation

Vercel’s first Git-triggered production deployment explicitly identified commit `9b778fc9e15817cd6838a2de9b9596a100d87703`, matching GitHub main at that point. Subsequent pushes should be checked by exact deployment `gitSource.sha`.

The Azure pipeline uses GitHub OIDC scoped to the repository’s production environment and deploys a digest from ACR, then compares `/healthz` revision to the tested commit. Failed verification blocks automatic deployment. Initial Linux CI found missing server fixtures and native tick-budget assumptions; those failures are recorded in Actions rather than hidden.

Cloud hosting is an online simulation demonstration, not a physical safety certification or production robotics claim. Public lifecycle limits intentionally preserve data and fail closed at capacity.
