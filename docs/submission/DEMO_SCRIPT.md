# Recording script — current truthful demo only

**Working document, not a statement that a recording exists.** The previously authored `DEMO.md` is a future acceptance/story outline, not the script for the currently accepted full fleet mission. This recording plan is deliberately scoped to the inspection-only local showcase documented on 17 October 2026. Refresh state, app, and evidence before recording; if the screen differs, narrate what is actually present.

## Preconditions — stop if any fail

1. The recording machine has the intended project checkout, local showcase services, and a retained synthetic showcase incident. Do not reset, delete, restart, or replace the retained incident to make footage look cleaner.
2. Open the existing console at `http://127.0.0.1:8094` as documented in `docs/SHOWCASE_CURRENT.md`. Do not start a second owner against `artifacts/showcase-20261017`.
3. Confirm the visible status remains inspection-only: simulation/S0; `dispatch_ready: false`; `model_mode: disabled`; no completed recovery, owner release, courier sensing, or delivery. If current status is different, stop and rewrite this script based on fresh verified state.
4. Hide private desktop material, tokens, local usernames/passwords, unrelated notifications, and non-public content. Use only the synthetic sources packaged for this demo.
5. Decide the tracks after checking the actual recorded sequence. Current safe candidate: Company Brain (partial); any Agents That Act on Connected Data claim must be tightly bounded to graph-backed inspection/dependency evidence.

No runtime command is prescribed here to mutate or seed the retained run. The showcase documentation says it already exists and its event identity is retained; use the read-only inspection path and preserve it.

## Suggested narration and shots

### 1. Project and boundary

**Show:** project name and the actual console, including its simulation/S0 and inspection-only status badges.

**Say:** “This is Witness Fleet, a local simulation-first prototype. This recording shows the inspection console and a synthetic policy/evidence graph. It is not a completed autonomous fleet mission.”

### 2. Physical scene versus authority

**Show:** current three robot poses and task/dependency view. Keep `dispatch_ready: false` visible if shown. Do not click a motion/approval control or imply that a robot has moved as part of this scene.

**Say:** “The product question is whether a task is physically supportable and policy-authorized. Those are separate checks. Here I am inspecting retained state, not executing a mission.”

### 3. FalkorDB doing real work

**Show:** a graph-backed task dependency and the displayed dependent/prerequisite edges. If the UI offers a graph witness, open the restriction witness and follow actual stored links: `IMPOSES`, `OWNED_BY`, `SUPPORTED_BY`, `IN_REVISION`, and `REVISION_OF`. Show the exact synthetic source excerpt and revision/hash only if the app exposes them accurately.

**Say:** “FalkorDB is the canonical operational graph in this build. These directed relationships connect the restriction to its owner and retained source evidence; the dependency edges connect tasks. This graph is more than a visual decoration, although the complete graph-authorized mission is still unfinished.”

If the graph pane is unavailable or query text cannot be shown safely, show the inspected Cypher from `artifacts/showcase-20261017/falkordb-queries.json` in a source editor, with no credentials visible. These queries are read-only showcase reads.

### 4. Provenance and limits

**Show:** label synthetic policy and source material as synthetic. Show the staged release record only with its actual `staged` status. Do not represent bootstrap data, an `ApprovalEvent` fixture or a staged release as real human approval.

**Say:** “The evidence here is synthetic lab data. The release is staged, not an actual human approval. The design requires a valid owner release and fresh, courier-owned sensing; that complete sequence is not accepted in this build.”

### 5. Honest close

**Show:** actual status panel; optionally the relevant README/setup entry and the status note in `docs/HACKATHON_STATUS_20261017.md`.

**Say:** “The verified scope is inspection plus one passing graph-policy-native inspection tracer test. Recovery, fresh post-recovery verification, owner release followed by courier sensing and delivery, and process-kill resume remain unverified. The model lane is disabled. This is the behavior shown, not a claim that the planned full mission is done.”

## Do not record as if completed

Do not record a fabricated or scripted courier motion, policy release, fresh clearance observation, delivery receipt, successful restart, model inference, timing benchmark, live deployment, or clean-machine setup. Do not show old component captures as if they came from the current retained showcase; identify their separate scope and date if used at all. Do not splice a passing unit test into apparent live operation.

## Final video QA / metadata to capture

After recording, fill this from the actual file and exact local run; do not guess:

- Local file path: `[fill after recording]`
- Final share URL (only after authorized upload): `[fill after upload and playback check]`
- Duration / resolution / frame rate / audio: `[inspect actual file]`
- Repository commit or exact source snapshot: `[record after review; current tree is dirty/uncommitted]`
- Run/episode identity and graph build: `[read from actual run]`
- What the footage proves: `[describe only visible, verified behaviors]`
- What remains out of scope: full mission, genuine human approval, live model use, and restart recovery unless each is newly completed and independently verified.

This script does not create, publish, upload, or verify a video. The file/URL fields remain blank until actual media exists.
