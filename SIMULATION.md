# Simulation, sensing and actuation contract

**Proposed design, not a simulation run.** Primary simulator: MuJoCo with original primitive assets. Avoid inheriting Awign code/assets without permission. The planar unit-test adapter is useful but is not evidence of contact-based robot recovery.

## 1. Facility and robot design

A small indoor facility has staging area, Corridor C, alternate route, safe observation poses and a recovery bay. Known map geometry is a declared prior; transient obstacles, contact outcomes and current traversability are not handed to the agent as privileged truth.

- Scout: small footprint, inspection skill, no manipulation capacity.
- Recovery robot: larger footprint, bounded package-moving capability with explicit mass/size/grasp limits.
- Courier: wider loaded footprint and a delivery task; cannot inherit the scout's clearance.

Use simple original MJCF primitives, clearly named bodies/geoms/joints and one simulation clock. Do not claim physically accurate mecanum-wheel slip, high-fidelity manipulator sensing or real-world transfer from a simple model. Map/robot parameters are synthetic scenario configuration, not measurements of real hardware.

## 2. Process boundary

`services/simulator` owns MuJoCo model/data and calls `mj_step`. Policy/coordinator communicate through typed requests and observations; they cannot import the world object, evaluator module or raw simulator arrays. Only the simulator service can touch full state. One scheduler advances all robots; asynchronous commands enqueue bounded goals rather than spawning independent stepping loops.

The evaluator can grade actual collision/clearance and record ground truth. The dashboard can show an optional **EVALUATOR / ORACLE** overlay, inaccessible to planner endpoints. Tests use sentinel hidden fields and filesystem/process isolation checks to catch accidental leakage. This is a software boundary to test, not an OS sandbox claim unless hardened separately.

## 3. Sensor modes, with honest labels

### S0 — simulated sensor features (primary)

Return pose-local range/visibility features with occlusion/noise/expiry defined by the scenario. Any simulator metadata used to synthesize these observations stays behind the sensor interface. Document exactly which objects, IDs and distances are exposed. This tests planning with controlled sensing; it is not autonomous visual recognition.

### S1 — rendered camera (stretch)

Return image/frame identity and calibrated pose/camera metadata; a perception worker must infer observations from images. Camera rendering while using hidden segmentation IDs for decisions remains an oracle-assisted mode and must be labeled as such. VLM agreement alone is not independent sensor corroboration.

### Oracle baseline

Explicitly reads ground truth for diagnostic upper bounds. Never compare it as if it had the same information as the production policy, and never use it to populate the normal graph silently.

## 4. Observation contract

`Observation`: observation/event ID, robot, sensor mode, event world tick, ingestion UTC, frame/pose, predicate and subject, value (`true/false/unknown` or measured interval), quality/visibility, uncertainty explanation, expires tick, payload/footprint scope and source locator.

Visibility insufficient → unknown. A narrow free gap measured with uncertainty must be checked against the courier footprint/margin, not a binary “scout passed” label. Correlated observations and repeated paraphrases are not independent trials. Out-of-order input can be retained but not make older evidence current.

## 5. Bounded skills

| Skill | Preconditions | Ack versus outcome | Failure/timeout |
|---|---|---|---|
| `inspect` | Reachable permitted safe viewpoint, sensor available, task claim | Ack means viewpoint request accepted; outcome is new observation | Unknown/occluded within bounded budget → hold/review |
| `travel` | Current permission, route resources, fresh relevant clearance, valid fence | Ack means controller started; arrival must be observed | Collision envelope, lost localization or stale permission → controlled hold |
| `recover` | Explicit scoped permission, capability/grasp/approach conditions, workspace reservation | Ack is not removed obstruction; inspect afterward | Failed/no movement, dropped object or timeout → retain failed attempt, replan |
| `verify` | Safe viewpoint, required sensor capability | Outcome is scoped postcondition evidence | Unknown → task cannot complete |
| `deliver` | Payload compatibility, current policy/physical route, claim | Arrival/drop receipt plus verified outcome | Unresolved delivery remains pending/reconcile |
| `wait` / `hold` | Always available conservative branch subject to local stop semantics | No success of parent task implied | Watchdog stays active |

Controllers cannot accept arbitrary Python, shell, Cypher or model-generated trajectories. A model selects an eligible skill proposal only; deterministic logic provides bounded parameters.

## 6. Reservation and local motion boundary

Use conservative corridor/workspace reservations before motion. A deterministic local controller checks immediate geometry/collision envelopes and speed/acceleration limits. Reservation does not prove continuous collision avoidance. A local stop prevents movement into an immediate hazard but cannot conceal unsafe high-level intent from metrics.

Policy authority is reevaluated before each bounded skill and on relevant revocation events. For an in-flight command, define a safe cancellation/hold trajectory; instantaneous motion cessation is not physically assumed. Record the ordering/tick of policy activation, cancellation receipt and eventual halt.

## 7. Command receipt protocol

A command contains tenant/session, command ID, task ID/version, robot ID, claim fence, action kind, bounded parameters, payload hash and authorization snapshot. On duplicate ID, identical payload returns existing state; changed payload rejects. A new higher fence supersedes older holders; stale commands reject even after a coordinator lease expires.

States: `ACCEPTED → RUNNING → CONTROLLER_DONE → OUTCOME_VERIFIED`, with `FAILED`, `CANCELLED` and `UNKNOWN` branches. `OUTCOME_VERIFIED` requires evidence, not the simulator's controller flag alone. The coordinator's task completion and simulator receipt have separate authorities.

Simulator journal/checkpoint protocol must state when a receipt is durable. If a crash loses certainty about motion, report UNKNOWN and require safe inspection/reconciliation. Do not treat “not in receipt table” as proof the action did not happen after an unclean crash. Resetting the world is a new episode, not successful continuation.

## 8. Required scenario families

Removable carton; non-graspable spill; gap fits scout but not courier; failed removal; object reintroduced after clearance; conflicting viewpoints; delayed/out-of-order observation; blackout/irreducible occlusion; competing claims; stale fence; graph/coordinator/model outage; scoped policy versus blanket ban; overlapping restrictions; expired/superseded policy; incompatible historical recipe; unknown command after restart.

Fixture parameters and seeds live outside model prompts. Hidden labels/outcomes cannot leak through IDs, filenames, family ordering or calibration partitions. Record action replay separately from regeneration by seed.

## 9. Host verification before implementation claims

Probe the selected MuJoCo version/package on Apple Silicon, load minimal original XML, step it, render if needed and verify one clock advances all agents. The documented macOS passive viewer requires `mjpython`; Linux headless rendering is a separate tested setup, not assumed equivalent.[83]

If native rendering fails, diagnose backend requirements without weakening the sensor boundary. A dashboard map projection may show simulator state, but label whether it is sensor view or evaluator view. Do not replace physics with a scripted animation and retain physics claims.

<!-- GENERATED CITATION REFERENCES -->

## Sources

[83] https://mujoco.readthedocs.io/en/stable/python.html — Python - MuJoCo Documentation
