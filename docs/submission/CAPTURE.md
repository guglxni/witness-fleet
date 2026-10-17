# Graph-native fleet demo recording

`capture_fleet_demo.py` records the actual `mission-v2` SC-001 integration path, not `scripts/capture_simulation.py`. It creates a new unique graph namespace on an explicitly selected loopback FalkorDB port, retains sources in a new run directory, bootstraps the graph/source evidence, constructs the native `SimulatorService` and `MissionController`, then calls `MissionController.run(event_id)`. This is real motion through graph task claims, policy authorization, command dispatch, native receipts, fresh measurements and graph-verified outcomes.

## Preconditions

- Install the repository's simulator extra and native Python environment. On macOS, run with `.venv/bin/mjpython`; MuJoCo rendering requires its native runtime.
- Start a separate FalkorDB server bound to loopback on an explicit port. Do not point at the retained showcase graph/server.
- Prepare a **new empty run directory**. The recorder refuses non-empty paths and never clears them. The path retains simulator journal/checkpoint, source bytes/revisions, MP4, and reports. Keep it for audit.
- Review the source tree and machine display before motion. This is a synthetic lab mission; do not put private material on the recording screen.

## Run

```sh
.venv/bin/mjpython -m scripts.capture_fleet_demo \
  --run-dir artifacts/fleet-demo-20261017 \
  --graph-port 6394 \
  --graph-user default \
  --output fleet-demo.mp4 \
  --approve-demo-owner
```

- `--graph-port` is required and must be a loopback graph service separate from the current showcase service. The script rejects the repository's documented ports `6380` (primary), `6381` (app), `6382` (integration/showcase), and `6383` (reserved inspection), then chooses a new unique namespace (`wf_fleet_demo_<random>`); it does not use the default `wf:demo:ops` graph. The user-selected graph server itself must be newly started and isolated. `--approve-demo-owner` is an explicit opt-in to one scripted action under the configured local maintenance-owner principal. This is **not** a human-authenticated approval. The video and manifest label the action accordingly. Motion is not run by tests.

Optional `--fps` (default 20) and `--sample-every` (default 5 world ticks) configure recording density. Rendering is 640×360. Frame acquisition reads the actual service-owned `world.data` and calls native MuJoCo `Renderer.render()` after service advancement; the service subclass delegates the real `advance()` before capturing. The script never issues direct `world.step`, manufactures observations, changes admission/policy, or sets task outcomes. Caption overlays use only actual mission phase/version/tick fields and identify the scripted local-owner action.

## Output contract

On actual completion (all seven manifest tasks `VERIFIED`, seven matching command outcome receipts `OUTCOME_VERIFIED`, each native command receipt `done`, each local journal receipt `KNOWN` and `OUTCOME_VERIFIED`, mission phase `complete`, recovery and delivery counters 1, no remaining approval, dispatch ready, and simulator not held):

- `fleet-demo.mp4` — native rendered world frames with phase/tick/graph-version captions.
- `mission-state.json` — graph IDs, state/epochs, task states, command receipt summaries, applicable dispatch event hashes/sequences, source revision hashes, and observation payload hashes; raw robot poses are excluded.
- `manifest.json` — video hash/size, provenance source-file hashes, scenario/seed, exact namespace/episode, state snapshot, and explicit scripted-owner disclaimer.
- `failure-report.json` — written only in the validated empty run directory if graph startup or the mission fails; failed runs never get a success manifest or state snapshot.
- `sim/` and `sources/` — retained simulator journal/checkpoint and SourceStore artifacts.

The manifest and state snapshot are created only for verified completion. Any exception/incomplete outcome writes `failure-report.json`, returns a nonzero exit status and does not create a success manifest/state snapshot. Partial video and simulator/source data remain in the run directory for diagnosis; this is not a rollback facility. The script does not claim a commit hash or clean Git tree: per-file SHA-256 provenance is recorded from the workflow/runtime source and native asset files.

## Tests and guardrails

```sh
.venv/bin/python -m pytest tests/unit/test_capture_fleet_demo.py -q
```

Unit tests cover output/run-dir boundaries, explicit owner-action opt-in, strict completion criteria, event/receipt summaries, and excluding private poses from provenance snapshots. They do not create a graph service, authorize, or move robots. For the integrated demo, use only a **new isolated graph server and new empty retained directory**; do not invoke against the showcase graph or existing run.
