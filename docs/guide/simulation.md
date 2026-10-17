# Simulation model and robotics assumptions

## Native single-owner world

[`FacilityWorld`](../../services/simulator/world.py) owns one `mujoco.MjModel` / `MjData` pair and advances it with `mujoco.mj_step`. The simulation service is the single step owner; API callers exchange typed commands, projected status and bounded sensor observations rather than importing mutable physics state ([`services/simulator/service.py`](../../services/simulator/service.py)).

The MJCF facility asset is [`services/simulator/assets/facility.xml`](../../services/simulator/assets/facility.xml). It declares a planar indoor corridor with north and south walls, staging/delivery sites, recovery bay, three mobile bodies, a light carton, heavy box, parcel, and a scenario occluder. One native timestep is configured at 0.01 s. The corridor's nominal wall-to-wall clear width is 1.4 m (walls centered at y=±0.81 with 0.11 m half-width; the declared interior in bootstrap is y=±0.7).

The runtime footprint parameters are scout 0.22 m, recovery 0.38 m, courier 0.50 m ([`world.py`](../../services/simulator/world.py), [`runtime/bootstrap.py`](../../src/witness_fleet/runtime/bootstrap.py)). They are synthetic scenario values, not measurements or safety margins certified for physical hardware. The parcel fixture is 2 kg; object properties and actuators are literal simulation parameters in the MJCF, not field-calibrated robot specifications.

## S0 sensor interface

The only active mission sensor mode is S0: nine bounded MuJoCo range rays across a ±0.55 rad fan, maximum 4.0 m, with observation expiry at 50 ticks. The implementation derives a visible obstacle/gap or insufficient/unknown result from its sensor ray projection ([`services/simulator/sensors.py`](../../services/simulator/sensors.py)). At capture time the adapter validates frame episode/tick consistency, records the observing robot, visibility, pose, configuration hash and expiry ([`runtime/sensing.py`](../../src/witness_fleet/runtime/sensing.py)).

S0 is controlled simulated range-feature sensing, **not camera perception, a learned detector, or raw human-like vision**. Visibility shortfall and occlusion can yield `unknown`. A scout's view is not relabeled as courier evidence. Physical fit is scoped by robot/payload; a passable scout gap is not a passable loaded-courier gap.

## Bounded motion and effect proof

Allowed skill kinds and parameter bounds are checked by the native world. Commands target bounded travel, recovery, inspection, verification, delivery, hold or wait behavior; arbitrary trajectories, shell commands, Python and Cypher are not controller inputs ([`world.py`](../../services/simulator/world.py), [`runtime/execution.py`](../../src/witness_fleet/runtime/execution.py)). Contact counters, displacement, stability windows and sensor postconditions are distinct from a controller's self-report. A held world neutralizes actuators, but no physical braking-distance or emergency-stop certification is claimed.

The simulator keeps a receipt journal and checkpoint. Its restart logic preserves known identity and latches HOLD if the checkpoint fails to cover the latest admission; motion past the last durable checkpoint may be uncertain ([`services/simulator/service.py`](../../services/simulator/service.py), [`services/simulator/journal.py`](../../services/simulator/journal.py)). No exactly-once physical effect claim is made.

## Limits readers should retain

- Planar slide-joint robot bodies are not a complete wheel, suspension, localization or manipulator model.
- Recovery is a bounded pusher interaction with primitive bodies, not a tested grasping arm or contact-rich field task.
- The deterministic simulator sensor uses known model geometry to synthesize limited features; it is not independent optical perception.
- Reproducible seed and native receipts do not create real-world validity or calibrated probabilities.
- A simulator oracle/evaluator, where used in diagnostic tests, must remain distinct from policy-visible observations.
- A displayed map or diagram is not a guarantee of continuous collision avoidance, safe stopping, operational floor conditions, or transfer to any robot platform.

The repository's higher-level [simulation design contract](../../SIMULATION.md) and [security specification](../../SECURITY.md) include broader proposed scenario and isolation requirements. Read proposal status on those docs carefully; they do not all describe implemented or verified features.
