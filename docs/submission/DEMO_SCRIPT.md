# Three-minute judge demo script

This is a spoken walkthrough plan, not a claim that a new recording exists. It uses the hosted simulation and repository evidence. Show the actual UI state; do not splice, fast-forward, or narrate an action that did not occur. The timings below pace the narration to a three-minute slot. If the interactive simulation takes longer, let it finish rather than speeding up or implying the timed narration is a measured system benchmark.

## 0:00–0:25 | Set the boundary

**Show:** the [hosted simulation](https://witness-fleet-guglxni.eastus.cloudapp.azure.com/demo), then the declared three-robot mission state.

**Say:** “This is Witness Fleet, a deterministic three-robot MuJoCo simulation. Its decision is not just whether a corridor looks clear. A task also needs current company authority, fresh evidence, and an outcome that the simulator actually verifies. This is not a hardware controller.”

## 0:25–0:55 | Run to the gate

**Show:** start one session and run the initial tasks. Keep the visible pause and task states on screen. Wait for the real result.

**Say:** “The scout observes, the recovery robot attempts bounded clearance, and the system checks the physical result. The courier is still held. Recovery does not grant permission, and the first four tasks finish before the owner gate.”

**Evidence to point out:** `awaiting_owner_release`, recovery verification, no courier command yet, and delivery still incomplete. Do not infer success from a button click or controller receipt.

## 0:55–1:20 | Trace the authority

**Show:** the actual restriction/decision, owner, evidence span and revision links, plus a task dependency if the UI exposes them. Use synthetic records only.

**Say:** “FalkorDB stores the connected operational records: the policy relationship, its scope and source provenance, and the mission dependencies. Python reads and validates that graph snapshot. The graph is not a picture that authorizes motion by itself.”

**Evidence to point out:** the actual displayed edge directions and retained source span. A content hash links bytes; it does not prove that the source is true. A staged release record is not an approval.

## 1:20–1:45 | Make the release explicit

**Show:** the release gate and the real confirm action. Submit the configured synthetic demo-owner release, then show the phase change. Do not obscure that the owner is configured rather than authenticated.

**Say:** “This is an explicit local demo-owner action checked against the current policy epoch and scope. It is not a human identity check. The release changes what is permitted; it does not substitute for new physical evidence.”

## 1:45–2:20 | Let the courier prove its own path

**Show:** run the courier phase and keep the actual status transitions visible. Do not cut from release straight to a fabricated final screen.

**Say:** “Now the courier obtains its own fresh sensing and passes the current authorization checks before travel. Scout clearance cannot be reused as courier evidence. MuJoCo advances the synthetic scene; Python coordinates the tasks and validates the returned evidence.”

## 2:20–2:45 | Inspect the final outcome

**Show:** all task/command states and, where exposed, the native delivery postcondition.

**Say:** “The completion claim is seven verified tasks and seven outcome-verified commands. The delivery receipt is backed by the native `payload_in_delivery_zone` postcondition. A transport acknowledgment alone would not establish that. The separate unauthorized-execution metric is still unknown, not zero.”

## 2:45–3:00 | Name the contribution and limits

**Show:** the [source-linked execution map](RUNTIME_QUERIES.md) and [submission brief](SUBMISSION_BRIEF.md).

**Say:** “Track 01 is primary: connected data changes what this agent can do. Track 02 is scoped to central coordination; Track 03 is scoped to synthetic policy provenance. The mission is deterministic, simulation-only, and uses no live model inference. The linked brief discloses the AI and third-party work.”

## If the live path is unavailable

Use the preserved [launch film](../../site/public/media/launch.mp4) and its [sanitized provenance](../../site/public/media/provenance.json), or the [preserved campaign cuts and credits](../../README.md#product-site-and-preserved-media). Label recorded MuJoCo footage as simulation and explanatory diagrams/animation as designed explanation. Do not describe film footage as a fresh live session, or splice a passing test into apparent runtime footage.
