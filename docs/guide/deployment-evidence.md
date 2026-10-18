# Deployment evidence

## Live endpoints

- Product: https://witness-fleet.vercel.app
- Interactive simulation: https://witness-fleet-guglxni.eastus.cloudapp.azure.com/demo
- Minimal process health: https://witness-fleet-guglxni.eastus.cloudapp.azure.com/healthz

## Executed cloud acceptance

The first Azure HTTPS run returned `complete`, with **7 tasks VERIFIED**, **7 commands OUTCOME_VERIFIED**, **recovery_verified=1**, and **delivery_completed=1**. The same final request ID returned an identical response. Missing Origin was rejected and `/api/state` remained inaccessible. Real native payload-placement evidence was verified through the corresponding Linux integration test.

The unknown `unauthorized_executed` metric remains null; it was not substituted with zero.

The site’s served launch MP4 SHA-256 matches the delivered 86s/1080p narrated file:
`1f781361d281df09999c7051d066c1d610ced861c6932a16fad2a8afe78bc869`.

## Revisions and automation

Vercel’s first Git-triggered production deployment explicitly identified commit `9b778fc9e15817cd6838a2de9b9596a100d87703`, matching GitHub main at that point. Subsequent pushes should be checked by exact deployment `gitSource.sha`.

The Azure pipeline uses GitHub OIDC scoped to the repository’s production environment and deploys a digest from ACR, then compares `/healthz` revision to the tested commit. Failed verification blocks automatic deployment. Initial Linux CI found missing server fixtures and native tick-budget assumptions; those failures are recorded in Actions rather than hidden.

Cloud hosting is an online simulation demonstration, not a physical safety certification or production robotics claim. Public lifecycle limits intentionally preserve data and fail closed at capacity.
