"""Validate retained native command measurements; never grant optical clearance."""
import math
from collections.abc import Mapping

from witness_fleet.domain import canonical_json_hash


def number(value):
    return type(value) in {int, float} and math.isfinite(value)


def _vector(value, size):
    return isinstance(value, (list, tuple)) and len(value) == size and all(number(v) for v in value)


def _stable(command, observation, q):
    w = q.get('stability_window')
    target = [command.proposal.parameters.get('target_x'), command.proposal.parameters.get('target_y')]
    pose = q.get('chassis_pose')
    return (isinstance(w, Mapping) and w.get('schema') == 'native-public-stability-v1'
        and type(w.get('sample_count')) is int and w['sample_count'] == 10
        and type(w.get('start_tick')) is int and type(w.get('end_tick')) is int
        and w['start_tick'] >= command.effective_world_tick
        and w['end_tick'] == observation.world_tick and w['end_tick'] - w['start_tick'] == 9
        and w.get('sensor_config_hash') == observation.sensor_config_hash
        and all(number(w.get(key)) and 0 <= w[key] <= bound for key, bound in (
            ('max_speed_m_s', .01), ('max_drift_m', .01)))
        and number(w.get('max_target_error_m')) and 0 <= w['max_target_error_m'] < .05
        and _vector(target, 2) and list(q.get('target', ())) == target
        and isinstance(pose, Mapping) and all(number(pose.get(a)) for a in ('x','y'))
        and math.hypot(pose['x']-target[0], pose['y']-target[1]) < .05
        and q.get('measured_frame') == 'chassis_map')


def measured_effect_valid(command, observation):
    """Validate modality-specific proof while preserving measured ray visibility."""
    try:
        q = observation.quality
        kind = command.proposal.kind.value
        if (observation.value is not True or observation.robot_id != command.proposal.robot_id
                or not isinstance(q, Mapping) or q.get('source') != 'native_command_measurement'
                or q.get('command_id') != command.command_id
                or q.get('receipt_payload_hash') != canonical_json_hash(command)
                or q.get('native_kind') != kind):
            return False
        if kind == 'recover':
            return (observation.predicate == 'obstruction_moved'
                and type(q.get('contact_count')) is int and q['contact_count'] > 0
                and number(q.get('measured_displacement_m'))
                and number(q.get('target_displacement_m')) and q['target_displacement_m'] > 0
                and q['target_displacement_m'] == command.proposal.parameters.get('target_displacement_m', .75)
                and q['measured_displacement_m'] >= q['target_displacement_m'])
        if kind in {'inspect', 'verify'}:
            return (observation.predicate == 'inspected' and observation.visibility == 'visible'
                and type(q.get('sample_world_tick')) is int
                and command.effective_world_tick <= q['sample_world_tick'] <= observation.world_tick
                and isinstance(q.get('sample_hash'), str) and len(q['sample_hash']) == 64)
        if kind not in {'travel', 'deliver'} or not _stable(command, observation, q):
            return False
        if kind == 'travel':
            return observation.predicate == 'arrived'
        payload, post, binding = (q.get(k) for k in ('payload_observation', 'delivery_postcondition', 'delivery_identity_binding'))
        if not all(isinstance(value, Mapping) for value in (payload, post, binding)):
            return False
        position, center = post.get('payload_pose'), post.get('zone_center')
        observed = payload.get('observed_pose')
        if not isinstance(observed, Mapping):
            return False
        observed_xyz = [observed.get(a) for a in ('x','y','z')]
        radius, height = post.get('zone_radius_m'), post.get('relative_height_m')
        identity = q.get('payload_id')
        return (observation.predicate == 'delivered' and isinstance(identity, str) and bool(identity.strip())
            and payload.get('payload_id') == binding.get('payload_id') == identity
            and payload.get('state') == 'observed' and payload.get('delivery_zone') is True
            and post.get('payload_in_delivery_zone') is True
            and _vector(position, 3) and _vector(center, 3) and _vector(observed_xyz, 3)
            and number(radius) and radius > 0 and number(height) and abs(height-.3) <= .12
            and math.hypot(position[0]-center[0], position[1]-center[1]) <= radius
            and math.dist(position, observed_xyz) <= .005
            and list(binding.get('observed_payload_pose_m', ())) == observed_xyz
            and list(binding.get('native_payload_pose_m', ())) == list(position)
            and binding.get('pose_match_tolerance_m') == .005)
    except (ValueError, TypeError, KeyError, OverflowError):
        return False
