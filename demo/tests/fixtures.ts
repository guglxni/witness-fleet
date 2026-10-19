import type { MissionState, SceneSnapshot } from '../src/contracts';

export const activeState: MissionState = {
  mission_phase: 'recovery_and_verification', revision_tick: 12,
  tasks: [{ task_id: 'task-001-inspect-south-corridor', kind: 'inspect', state: 'VERIFIED', robot_id: 'scout' }],
  robots: [{ robot_id: 'scout', pose: { x: -4, y: -0.2, yaw: 0.1 } }],
  commands: [{ kind: 'inspect', state: 'VERIFIED', task_id: 'task-001-inspect-south-corridor', robot_id: 'scout', effects: { corridor_clear: true } }],
  metrics: { recovery_verified: 1, delivery_completed: 0, unauthorized_executed: null }, expected_policy_epoch: 4,
};
const geom = (id: string, kind: 'plane' | 'box' | 'cylinder', body: string | null, position: [number, number, number], size: [number, number, number], rgba: [number, number, number, number]): SceneSnapshot['geometries'][number] => ({ id, kind, body, position, quaternion: [1, 0, 0, 0], size, rgba });
export const sceneFixture: SceneSnapshot = {
  schema_version: 1, source: 'mujoco_snapshot', world_tick: 84, model_sha256: 'a'.repeat(64), units: 'm', up_axis: 'z',
  geometries: [
    geom('floor', 'plane', null, [0, 0, 0], [12, 8, 0.1], [0.68, 0.72, 0.73, 1]),
    geom('corridor_south_wall', 'box', null, [0, -0.81, 0.6], [8, 0.11, 0.6], [0.35, 0.39, 0.44, 1]),
    geom('corridor_north_wall_west', 'box', null, [-4.7, 0.81, 0.6], [3.3, 0.11, 0.6], [0.35, 0.39, 0.44, 1]),
    geom('corridor_north_wall_east', 'box', null, [4.7, 0.81, 0.6], [3.3, 0.11, 0.6], [0.35, 0.39, 0.44, 1]),
    geom('west_wall', 'box', null, [-8.1, 0, 0.6], [0.1, 1, 0.6], [0.35, 0.39, 0.44, 1]),
    geom('east_wall', 'box', null, [8.1, 0, 0.6], [0.1, 1, 0.6], [0.35, 0.39, 0.44, 1]),
    geom('scenario_occluder', 'box', null, [10, 5, 0.5], [0.08, 0.8, 0.55], [0.18, 0.2, 0.24, 1]),
    geom('scout_chassis', 'cylinder', 'scout', [-4, -0.2, 0.18], [0.11, 0.11, 0.13], [0.15, 0.55, 0.85, 1]),
    geom('recovery_chassis', 'cylinder', 'recovery', [0, -0.2, 0.2], [0.19, 0.19, 0.16], [0.9, 0.4, 0.1, 1]),
    geom('recovery_pusher', 'box', 'recovery', [0.2, -0.2, 0.2], [0.02, 0.34, 0.1], [0.65, 0.25, 0.05, 1]),
    geom('courier_chassis', 'box', 'courier', [0, 0.3, 0.24], [0.25, 0.25, 0.18], [0.35, 0.65, 0.25, 1]),
    geom('carton_geom', 'box', 'carton', [-2, -0.2, 0.18], [0.34, 0.27, 0.18], [0.65, 0.43, 0.2, 1]),
    geom('heavy_box_geom', 'box', 'heavy_box', [3, 0.3, 0.22], [0.34, 0.27, 0.22], [0.25, 0.28, 0.3, 1]),
    geom('parcel_geom', 'box', 'parcel', [-6, 0, 0.48], [0.18, 0.16, 0.12], [0.2, 0.3, 0.9, 1]),
    geom('alternate_block_geom', 'box', 'alternate_route_block', [5, 0, 0.15], [0.5, 0.5, 0.15], [0.5, 0.35, 0.3, 1]),
  ],
  sites: [
    { id: 'south_staging', position: [-4, -2.5, 0.02], size: [0.06, 0.06, 0.06] },
    { id: 'north_staging', position: [4, -2.5, 0.02], size: [0.06, 0.06, 0.06] },
    { id: 'recovery_bay', position: [1.4, -0.2, 0.02], size: [0.06, 0.06, 0.06] },
    { id: 'delivery_zone', position: [4, 0, 0.03], size: [0.45, 0.45, 0.45] },
    { id: 'scout_sensor', position: [-3.8, -0.2, 0.21], size: [0.025, 0.025, 0.025] },
    { id: 'recovery_sensor', position: [0.2, -0.2, 0.23], size: [0.025, 0.025, 0.025] },
    { id: 'courier_sensor', position: [0.3, 0.3, 0.27], size: [0.025, 0.025, 0.025] },
  ],
};
