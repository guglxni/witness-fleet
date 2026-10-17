import type { FleetProjection } from '../api-contract';

export function acceptSnapshot(
  current: FleetProjection | null,
  incoming: FleetProjection,
  allowEpisodeChange = false,
): FleetProjection {
  if (!current) return incoming;
  if (current.episode_id !== incoming.episode_id) return allowEpisodeChange ? incoming : current;
  return incoming.revision <= current.revision ? current : incoming;
}

export function decisionStateTone(value: string): 'verified' | 'unresolved' | 'in-progress' | 'neutral' {
  const state = value.toLowerCase().replaceAll('_', ' ');
  // Positive evidence is an exact state, never a substring of an unknown label.
  if (['verified', 'outcome verified'].includes(state)) return 'verified';
  if (['unverified', 'not verified', 'outcome verified unknown', 'denied', 'failed', 'unknown', 'unresolved'].includes(state)) return 'unresolved';
  if (['running', 'accepted', 'controller done', 'completed'].includes(state)) return 'in-progress';
  return 'neutral';
}

export type MissionControlCapabilities = { stepTask: boolean; run: boolean; ownerRelease: boolean; hold: boolean };

export function missionControlCapabilities(state: FleetProjection | null, writeEnabled: boolean): MissionControlCapabilities {
  const disabled: MissionControlCapabilities = { stepTask: false, run: false, ownerRelease: false, hold: false };
  const phase = state?.mission_phase;
  const validPhase = ['recovery_and_verification', 'awaiting_owner_release', 'courier_delivery', 'complete', 'held'].includes(String(phase));
  if (!state || !writeEnabled || state.operator_mode !== 'local_mission' || !validPhase || state.tasks.length !== 7
    || phase === 'complete' || phase === 'held') return disabled;

  const noHold = state.hold_reason === null;
  const initialRecovery = phase === 'recovery_and_verification' && state.commands.length === 0 && noHold;
  const recoveryAllowed = phase === 'recovery_and_verification' && (noHold && (state.dispatch_ready || initialRecovery));
  const courierAllowed = phase === 'courier_delivery' && state.dispatch_ready && noHold;
  const verifiedPrerequisites = state.tasks.slice(0, 4).every((task) => task.state === 'VERIFIED');
  return {
    stepTask: recoveryAllowed || courierAllowed,
    run: recoveryAllowed || courierAllowed,
    ownerRelease: phase === 'awaiting_owner_release' && noHold && verifiedPrerequisites && state.approval_required
      && Boolean(state.release_id) && Boolean(state.local_owner_id?.trim()),
    hold: noHold && (phase === 'recovery_and_verification' || phase === 'courier_delivery'),
  };
}

export function isFleetProjection(value: unknown): value is FleetProjection {
  if (!value || typeof value !== 'object') return false;
  const state = value as Partial<FleetProjection>;
  if (state.schema_version !== 1
    || !(state.episode_id === null || (typeof state.episode_id === 'string' && state.episode_id.trim().length > 0))
    || !nonNegativeInteger(state.revision)
    || !nonNegativeInteger(state.world_tick)
    || !nonNegativeInteger(state.graph_version)
    || !nonNegativeInteger(state.policy_epoch)
    || !nonNegativeInteger(state.coordinator_epoch)
    || !nonNegativeInteger(state.dispatch_sequence)
    || typeof state.dispatch_ready !== 'boolean'
    || !['disabled', 'shadow', 'advisory'].includes(String(state.model_mode))
    || state.sensor_mode !== 'S0'
    || typeof state.approval_required !== 'boolean'
    || (state.operator_mode !== undefined && !['inspection_only', 'local_mission'].includes(state.operator_mode))
    || (state.mission_phase !== undefined && !['recovery_and_verification', 'awaiting_owner_release', 'courier_delivery', 'complete', 'held'].includes(state.mission_phase))
    || (state.local_owner_id !== undefined && state.local_owner_id !== null && typeof state.local_owner_id !== 'string')
    || !Array.isArray(state.robots)
    || !Array.isArray(state.tasks)
    || !Array.isArray(state.commands)
    || !Array.isArray(state.observations)
    || !Array.isArray(state.restrictions)
    || !Array.isArray(state.sources)
    || !Array.isArray(state.events)) return false;

  const metrics = state.metrics;
  return Boolean(metrics && typeof metrics === 'object' && Object.values(metrics).every((metric) => metric === null || (typeof metric === 'number' && Number.isFinite(metric))))
    && state.tasks.every((task) => {
      if (!task || typeof task !== 'object') return false;
      const item = task as FleetProjection['tasks'][number];
      return typeof item.id === 'string' && typeof item.kind === 'string' && typeof item.state === 'string'
        && (item.robot_id === null || typeof item.robot_id === 'string')
        && Array.isArray(item.depends_on) && item.depends_on.every((id) => typeof id === 'string')
        && Array.isArray(item.reason_codes) && item.reason_codes.every((code) => typeof code === 'string')
        && (item.last_command_id === null || typeof item.last_command_id === 'string');
    })
    && state.commands.every((command) => {
      if (!command || typeof command !== 'object') return false;
      const item = command as FleetProjection['commands'][number];
      return typeof item.command_id === 'string' && typeof item.robot_id === 'string'
        && typeof item.kind === 'string' && typeof item.state === 'string'
        && (item.last_known_state === null || typeof item.last_known_state === 'string')
        && typeof item.reconciliation_state === 'string' && nonNegativeInteger(item.world_tick)
        && Array.isArray(item.reason_codes) && item.reason_codes.every((code) => typeof code === 'string');
    })
    && state.robots.every((robot) => {
    if (!robot || typeof robot !== 'object') return false;
    const item = robot as FleetProjection['robots'][number];
    return typeof item.id === 'string'
      && ['scout', 'recovery', 'courier'].includes(item.role)
      && typeof item.state === 'string'
      && typeof item.footprint_m === 'number'
      && Number.isFinite(item.footprint_m)
      && typeof item.pose === 'object'
      && item.pose !== null
      && Number.isFinite(item.pose.x)
      && Number.isFinite(item.pose.y)
      && Number.isFinite(item.pose.yaw);
  });
}

function nonNegativeInteger(value: unknown): value is number {
  return Number.isSafeInteger(value) && Number(value) >= 0;
}
