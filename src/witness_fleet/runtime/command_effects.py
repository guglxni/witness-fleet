"""Command-bound native measurements, distinct from clearance/authority."""
import math
from collections.abc import Mapping
from datetime import UTC, datetime

from services.simulator.stability import StabilityWindow, validate_stability_window
from witness_fleet.domain import CommandIntent, Observation, Pose, canonical_json_hash


def _number(value):
    return type(value) in {int, float} and math.isfinite(value)


def _sample_valid(sample, robot_id, tick, *, require_visible=False):
    if not isinstance(sample, Mapping) or sample.get('robot_id') != robot_id or sample.get('world_tick') != tick:
        return False
    sensor, visibility, ranges = sample.get('sensor'), sample.get('visibility'), sample.get('ranges_m')
    if not isinstance(sensor, Mapping) or not isinstance(visibility, Mapping):
        return False
    maximum, expiry = sensor.get('max_range_m'), sensor.get('expires_tick')
    fraction, state = visibility.get('fraction'), visibility.get('state')
    if (not _number(maximum) or maximum <= 0 or type(expiry) is not int or expiry <= tick
            or not isinstance(sensor.get('config_hash'), str) or not sensor['config_hash']
            or state not in {'visible', 'insufficient'} or not _number(fraction) or not 0 <= fraction <= 1
            or not isinstance(ranges, list) or not ranges
            or not all(_number(value) and 0 <= value <= maximum for value in ranges)):
        return False
    return not require_visible or (state == 'visible' and fraction >= .5)


def _delivery_postcondition(native):
    if not isinstance(native, Mapping):
        return None
    result = native.get('result')
    if not isinstance(result, Mapping):
        return None
    measured = result.get('postcondition')
    if not isinstance(measured, Mapping):
        return None
    position, center = measured.get('payload_pose'), measured.get('zone_center')
    radius, height = measured.get('zone_radius_m'), measured.get('relative_height_m')
    if (measured.get('payload_in_delivery_zone') is not True
            or not isinstance(position, list) or len(position) != 3
            or not isinstance(center, list) or len(center) != 3
            or not all(_number(value) for value in position + center)
            or not _number(radius) or radius <= 0 or not _number(height)
            or math.hypot(position[0] - center[0], position[1] - center[1]) > radius
            or abs(height - .30) > .12):
        return None
    return measured


def _event_matches(service, receipt, command):
    response = service.event(receipt.get('event_id', ''))
    if not isinstance(response, Mapping) or response.get('status') != 'KNOWN':
        return False
    event = response.get('event')
    if not isinstance(event, Mapping):
        return False
    expected = command.model_dump(mode='json')
    return (event.get('id') == receipt.get('event_id') == command.command_id
            and event.get('kind') == 'COMMAND'
            and event.get('payload_hash') == canonical_json_hash(expected)
            and event.get('payload') == expected)


def capture_command_effects(service, *, command, now_utc, tenant_id="demo",
                            stability_window: StabilityWindow | None = None):
    """Project exact-command measurements; never infer permission or advance physics.

    Travel/delivery arrival requires the current, collector-sealed ten-tick window.
    Stability uses the native 0.01 s physics timestep, N=10 consecutive public
    samples, max target error < 0.05 m, speed <= 0.01 m/s and drift <= 0.01 m.
    Malformed nested transport evidence fails closed as no observation.
    """
    if not isinstance(command, CommandIntent):
        raise ValueError('typed retained command required')
    command = CommandIntent.model_validate(command.model_dump(mode='json'))
    if (not isinstance(now_utc, datetime) or now_utc.tzinfo is None
            or now_utc.utcoffset() != UTC.utcoffset(now_utc)):
        raise ValueError('explicit UTC observation time required')
    with service._lock:
        try:
            status = service.status()
            receipt = service.command(command.command_id)
            if not isinstance(status, Mapping) or not isinstance(receipt, Mapping):
                return ()
            native = receipt.get('native')
            kind, robot = command.proposal.kind.value, command.proposal.robot_id
            command_hash = canonical_json_hash(command)
            if (not isinstance(native, Mapping) or status.get('held') is not False
                    or receipt.get('status') != 'KNOWN'
                    or receipt.get('state') not in {'CONTROLLER_DONE', 'OUTCOME_VERIFIED'}
                    or receipt.get('command_id') != command.command_id
                    or receipt.get('payload_hash') != command_hash
                    or native.get('status') != 'done' or native.get('robot_id') != robot
                    or native.get('kind') != kind
                    or native.get('accepted_tick') != command.effective_world_tick
                    or (kind in {'travel', 'deliver'} and native.get('target') != [
                        command.proposal.parameters.get('target_x', 0.0),
                        command.proposal.parameters.get('target_y', 0.0)])
                    or not _event_matches(service, receipt, command)):
                return ()
            tick = status.get('world_tick')
            if type(tick) is not int or tick < 0:
                return ()
            obs = service.observations()
            robots = obs.get('robots') if isinstance(obs, Mapping) else None
            sample = robots.get(robot) if isinstance(robots, Mapping) else None
            if not _sample_valid(sample, robot, tick):
                return ()
            sensor, visibility = sample['sensor'], sample['visibility']
            params = command.proposal.parameters
            quality = {'source': 'native_command_measurement', 'command_id': command.command_id,
                        'receipt_payload_hash': command_hash, 'native_kind': kind,
                        'sample_visibility': dict(visibility)}
            if kind == 'recover':
                displacement, target = native.get('measured_displacement_m'), native.get('target_displacement_m')
                contacts, commanded = native.get('contact_count'), params.get('target_displacement_m', .75)
                if (type(contacts) is not int or contacts <= 0 or not _number(displacement)
                        or not _number(target) or target <= 0 or displacement < target
                        or not _number(commanded) or target != commanded):
                    return ()
                predicate = 'obstruction_moved'
                quality.update(contact_count=contacts, measured_displacement_m=displacement,
                               target_displacement_m=target)
            elif kind in {'travel', 'deliver'}:
                target = (params.get('target_x', 0.0), params.get('target_y', 0.0))
                if not all(_number(value) for value in target) or native.get('target') != list(target):
                    return ()
                poses = status.get('poses')
                chassis = poses.get(robot) if isinstance(poses, Mapping) else None
                if not isinstance(chassis, Mapping) or not all(_number(chassis.get(a)) for a in ('x', 'y')):
                    return ()
                error = math.hypot(chassis['x'] - target[0], chassis['y'] - target[1])
                episode = status.get('episode_id')
                window = stability_window
                if (error >= .05 or not isinstance(episode, str)
                        or not validate_stability_window(service, command, window,
                                                        episode_id=episode, world_tick=tick)):
                    return ()
                if window is None:
                    return ()
                if (kind == 'deliver' and
                        (window.visibility_state != visibility.get('state')
                         or abs(window.visibility_fraction - visibility.get('fraction', -1)) > 1e-12)):
                    return ()
                predicate = 'arrived'
                quality.update(distance_to_target_m=error, target=list(target), chassis_pose=dict(chassis),
                    measured_frame='chassis_map', stability_window={
                        'schema': window.schema, 'start_tick': window.start_tick,
                        'end_tick': window.end_tick, 'sample_count': window.sample_count,
                        'max_target_error_m': window.max_target_error_m,
                        'max_speed_m_s': window.max_speed_m_s, 'max_drift_m': window.max_drift_m,
                        'tick_seconds': window.tick_seconds,
                        'sensor_config_hash': window.sensor_config_hash})
                if kind == 'deliver':
                    # Delivery's parcel return is independently observed by the simulator;
                    # preserve overall ray visibility, never upgrade it to visible.
                    post = _delivery_postcondition(native)
                    payload = sample.get('payload')
                    if (post is None or not isinstance(payload, Mapping)
                            or payload.get('state') != 'observed'
                            or not isinstance(payload.get('payload_id'), str)
                            or not payload['payload_id'].strip() or payload.get('delivery_zone') is not True):
                        return ()
                    observed = payload.get('observed_pose')
                    position = post['payload_pose']
                    if (not isinstance(observed, Mapping)
                            or not all(_number(observed.get(a)) for a in ('x', 'y', 'z'))
                            or math.dist([observed['x'], observed['y'], observed['z']], position) > .005):
                        return ()
                    payload_id = payload['payload_id']
                    predicate = 'delivered'
                    quality.update(payload_id=payload_id, payload_observation=dict(payload),
                        delivery_postcondition=dict(post), delivery_identity_binding={
                            'payload_id': payload_id,
                            'observed_payload_pose_m': [observed['x'], observed['y'], observed['z']],
                            'native_payload_pose_m': list(position), 'pose_match_tolerance_m': .005})
            elif kind in {'inspect', 'verify'}:
                measured = native.get('result')
                if (not isinstance(measured, Mapping) or type(measured.get('world_tick')) is not int
                        or not command.effective_world_tick <= measured['world_tick'] <= tick
                        or not _sample_valid(measured, robot, measured['world_tick'], require_visible=True)
                        or measured['sensor']['expires_tick'] <= tick):
                    return ()
                predicate = 'inspected'
                quality.update(sample_world_tick=measured['world_tick'],
                               sample_hash=canonical_json_hash(measured),
                               measured_visibility=dict(measured['visibility']))
            else:
                return ()
            if command.proposal.expected_effects and predicate not in command.proposal.expected_effects:
                return ()
            pose = sample.get('pose')
            if not isinstance(pose, Mapping):
                return ()
            record = dict(tenant_id=tenant_id, episode_id=status['episode_id'], robot_id=robot,
                occurred_at=now_utc.isoformat(), recorded_at=now_utc.isoformat(), world_tick=tick,
                expires_tick=sensor['expires_tick'], predicate=predicate, value=True,
                pose=Pose.model_validate(pose).model_dump(mode='json'), frame='map',
                visibility=visibility['state'], scope={'corridor_id': command.proposal.corridor_id},
                quality=quality, sensor_config_hash=sensor['config_hash'],
                subject_id=command.proposal.corridor_id)
            record['id'] = 'native-effect-' + canonical_json_hash(record)
            return (Observation.model_validate(record),)
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
            return ()
