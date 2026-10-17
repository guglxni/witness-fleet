import { describe, expect, it } from 'vitest';
import type { FleetProjection } from '../api-contract';
import { acceptSnapshot, isFleetProjection, missionControlCapabilities } from '../src/state';

const valid: FleetProjection = {
  schema_version: 1, revision: 1, episode_id: null, scenario: null, world_tick: 0,
  graph_version: 0, policy_epoch: 0, coordinator_epoch: 0, dispatch_sequence: 0, dispatch_ready: false,
  hold_reason: null, model_mode: 'disabled', sensor_mode: 'S0', robots: [], tasks: [], commands: [],
  observations: [], restrictions: [], sources: [], events: [], approval_required: false, release_id: null, metrics: {},
};

describe('fleet projection validation', () => {
  it('accepts the pinned schema with required fields and arrays', () => {
    expect(isFleetProjection(valid)).toBe(true);
  });

  it('does not treat a different episode ID as freshness authority', () => {
    const previous: FleetProjection = { ...valid, episode_id: 'episode-new', revision: 1 };
    const delayed: FleetProjection = { ...valid, episode_id: 'episode-old', revision: 99 };
    expect(acceptSnapshot(previous, delayed)).toBe(previous);
  });

  it('keeps an older revision of the same episode out of the current snapshot', () => {
    const previous: FleetProjection = { ...valid, episode_id: 'episode-same', revision: 8 };
    const next: FleetProjection = { ...valid, episode_id: 'episode-same', revision: 7 };
    expect(acceptSnapshot(previous, next)).toBe(previous);
  });

  it('rejects partial health objects and malformed top-level state payloads', () => {
    expect(isFleetProjection({ process: 'healthy', dispatch_ready: false })).toBe(false);
    expect(isFleetProjection({ ...valid, robots: null })).toBe(false);
    expect(isFleetProjection({ ...valid, revision: 1.5 })).toBe(false);
    expect(isFleetProjection({ ...valid, dispatch_ready: undefined })).toBe(false);
  });

  it.each([undefined, 1, {}, '', '   '])('rejects malformed episode identity %s', (episode_id) => {
    expect(isFleetProjection({ ...valid, episode_id })).toBe(false);
  });

  it('rejects projected robots that cannot be positioned safely', () => {
    expect(isFleetProjection({ ...valid, robots: [{ id: 'r1', role: 'scout', pose: { x: 'east', y: 1, yaw: 0 }, state: 'idle', footprint_m: 0.5, last_observation_tick: 0 }] })).toBe(false);
    expect(isFleetProjection({ ...valid, robots: [{ id: 'r1', role: 'scout', pose: { x: Number.NaN, y: 1, yaw: 0 }, state: 'idle', footprint_m: 0.5, last_observation_tick: 0 }] })).toBe(false);
  });

  it('rejects non-finite metric values and negative revision counters', () => {
    expect(isFleetProjection({ ...valid, metrics: { completion: Number.POSITIVE_INFINITY } })).toBe(false);
    expect(isFleetProjection({ ...valid, revision: -1 })).toBe(false);
    expect(isFleetProjection({ ...valid, world_tick: -1 })).toBe(false);
  });

  it('rejects incomplete task and command rows that would break the operator tables', () => {
    expect(isFleetProjection({ ...valid, tasks: [{ id: 't1', kind: 'repair', state: 'READY', depends_on: null, reason_codes: [] }] })).toBe(false);
    expect(isFleetProjection({ ...valid, commands: [{ command_id: 'c1', robot_id: 'r1', kind: 'move', state: 'ACCEPTED', world_tick: Number.NaN }] })).toBe(false);
  });
  it('rejects invalid optional mission mode, phase, and owner values', () => {
    expect(isFleetProjection({ ...valid, operator_mode: 'automatic' })).toBe(false);
    expect(isFleetProjection({ ...valid, mission_phase: 'moving' })).toBe(false);
    expect(isFleetProjection({ ...valid, local_owner_id: 42 })).toBe(false);
  });
});

describe('opt-in mission control capabilities', () => {
  const missionTasks = Array.from({ length: 7 }, (_, index) => ({
    id: `task-${index + 1}`, kind: index === 6 ? 'deliver' : 'verify',
    state: index < 4 ? 'VERIFIED' : 'PENDING', robot_id: null, depends_on: [], reason_codes: [], last_command_id: null,
  }));
  const mission = (overrides: Partial<FleetProjection> = {}): FleetProjection => ({
    ...valid, episode_id: 'mission-1', tasks: missionTasks, operator_mode: 'local_mission',
    mission_phase: 'recovery_and_verification', local_owner_id: 'demo-owner', ...overrides,
  });

  it('keeps legacy and explicit inspection projections inert, even when dispatch is ready', () => {
    expect(missionControlCapabilities({ ...valid, operator_mode: 'inspection_only', dispatch_ready: true }, true)).toEqual({ stepTask: false, run: false, ownerRelease: false, hold: false });
  });

  it('allows initial recovery tasks with a closed dispatch gate only before any command and with no hold', () => {
    const command = { command_id: 'cmd-1', robot_id: 'scout', kind: 'inspect', state: 'DONE', last_known_state: null, reconciliation_state: 'complete', world_tick: 1, reason_codes: [] };
    expect(missionControlCapabilities(mission(), true)).toMatchObject({ stepTask: true, run: true });
    expect(missionControlCapabilities(mission({ commands: [command] }), true)).toMatchObject({ stepTask: false, run: false });
    expect(missionControlCapabilities(mission({ hold_reason: 'operator hold' }), true)).toMatchObject({ stepTask: false, run: false, hold: false });
  });

  it('requires dispatch readiness for recovery work after start and for courier delivery', () => {
    const command = { command_id: 'cmd-1', robot_id: 'scout', kind: 'inspect', state: 'DONE', last_known_state: null, reconciliation_state: 'complete', world_tick: 1, reason_codes: [] };
    expect(missionControlCapabilities(mission({ dispatch_ready: false, commands: [command] }), true).run).toBe(false);
    expect(missionControlCapabilities(mission({ mission_phase: 'courier_delivery', dispatch_ready: false }), true)).toMatchObject({ stepTask: false, run: false });
    expect(missionControlCapabilities(mission({ mission_phase: 'courier_delivery', dispatch_ready: true }), true)).toMatchObject({ stepTask: true, run: true });
  });

  it('allows only the configured local demo owner to submit an awaiting-release request', () => {
    const waiting = { mission_phase: 'awaiting_owner_release' as const, approval_required: true, release_id: 'release-1' };
    expect(missionControlCapabilities(mission(waiting), true)).toEqual({ stepTask: false, run: false, ownerRelease: true, hold: false });
    expect(missionControlCapabilities(mission({ ...waiting, operator_mode: 'inspection_only' }), true).ownerRelease).toBe(false);
    expect(missionControlCapabilities(mission({ ...waiting, local_owner_id: null }), true).ownerRelease).toBe(false);
    expect(missionControlCapabilities(mission({ ...waiting, tasks: [] }), true).ownerRelease).toBe(false);
  });

  it.each(['complete', 'held'] as const)('disables all mission actions during %s', (mission_phase) => {
    expect(missionControlCapabilities(mission({ mission_phase, dispatch_ready: true }), true)).toEqual({ stepTask: false, run: false, ownerRelease: false, hold: false });
  });

  it('disables every mission action when the projection is stale, offline, busy, or incomplete', () => {
    const active = mission({ dispatch_ready: true });
    expect(missionControlCapabilities(active, false)).toEqual({ stepTask: false, run: false, ownerRelease: false, hold: false });
    expect(missionControlCapabilities(mission({ mission_phase: undefined }), true)).toEqual({ stepTask: false, run: false, ownerRelease: false, hold: false });
    expect(missionControlCapabilities(mission({ tasks: [] }), true)).toEqual({ stepTask: false, run: false, ownerRelease: false, hold: false });
  });
});
