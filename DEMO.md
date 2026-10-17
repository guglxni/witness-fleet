# Demonstration and submission checklist

**Recording script for a future working build. No demo video has been recorded.** Target a concise primary story plus supplementary failure/evaluation clips; do not invent an organizer video-length rule.

## Primary sequence

1. **Show the real scene and mode.** Scout, recovery robot and loaded courier in one simulation; sensor mode S0 or S1 clearly labeled. Display server/model mode and no hidden scripted “success”.
2. **Introduce the incident.** A pose-limited scout report is ambiguous. Show affected orders/tasks via canonical graph dependency query and why unrelated work remains eligible.
3. **Choose and verify recovery.** Show capability/route/resource witness and rejected alternatives. Attempt removal. Display controller acknowledgment separately from fresh postcondition evidence.
4. **Hero moment.** Floor is physically clear for the loaded courier, but it remains stopped. Gate panel reads “Physical: verified / Policy: restricted”.
5. **Explain the company evidence.** Expand the connected canonical witness: restriction, owning decision, owner, exact source span, immutable revision/source. Show the older permissive manual and newer unsigned chat do not silently override the approved restriction.
6. **Change authority legitimately.** Maintenance-owner performs explicit scoped synthetic approval with expected epoch. Show release source and target restriction. Graph changes; stale plan/assessment rejects; fresh physical check runs again.
7. **Resume.** Only after both gates pass, courier executes and outcome is verified. Record actual command/fence/version in trace.
8. **Memory/restart proof.** Replay a comparable new incident or kill coordinator after send/before result commit. New process retrieves prior evidence/claim/command; it reconciles instead of blindly repeating recovery. Show one changed correct action.
9. **Measured model contribution (if available).** Show real same-information comparison and raw counts/costs. If disabled/inconclusive, say so; show shadow/replay mode honestly.

## Supplementary proof clips

- Scoped restriction versus blanket ban (recovery must also stop under blanket ban).
- Failed removal and scout-only gap: no premature courier resume.
- Two synchronized claim clients: one winner, stale fence rejected.
- Second tenant identical names: direct database access denied.
- DB restart/container recreation/restore as separate evidence, not conflated with app restart.
- JevOut-inspired plausible distractor and wrong source revision: no authorization bypass even if semantic judgment changes.
- Graph/model outage: visible unavailable/hold, no fake successful answer.

## Every scene must be traceable

Capture run ID, commit, dependencies, configuration/seed, source hashes, graph/policy epochs, query templates, command/receipt IDs, sensor mode, model mode/provider/version, and raw trace. Record manual actions and resets. A reset is a new episode, not recovery. A replay is not a live model call. Evaluator overlays are labeled and inaccessible to policy.

## Submission materials

Official rules currently require public source repository; README/setup + graph model; relied-on Cypher queries/algorithms; working demo video; deployment or complete local setup; named track(s); AI assistant disclosure and meaningful participant understanding.[39]

Before publication:
- Complete clean setup and P0 proof matrix; record unmet optional/model criteria.
- Verify exact event rules/deadline again.
- Review third-party code/model/data/asset licenses; no Awign/RobotFleet code reuse without permission.
- Scan publication content/history for private material; do not include local endpoints, credentials or real company data.
- Obtain user approval for repo creation/publication and submission. Verify exact remote files/commit/video links afterward.
- Participant can explain: why FalkorDB is central, graph directions, physical versus policy permission, model limitations, concurrency/unknown effects, adopted math and original contribution.

Do not claim a hackathon submission is complete from this documentation bundle alone.

<!-- GENERATED CITATION REFERENCES -->

## Sources

[39] https://www.wemakedevs.org/hackathons/falkordb/rules — Rules | Graph Hacks: Context for AI Agents | WeMakeDevs
