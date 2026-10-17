"""Typed local sensor projection; never retags a peer as the acting robot."""

from witness_fleet.domain import Observation, Pose, canonical_json_hash


def _selected_observers(observer_ids):
    if observer_ids is None:
        return None
    if (not isinstance(observer_ids, tuple) or not observer_ids
            or any(not isinstance(observer, str) or not observer for observer in observer_ids)
            or len(set(observer_ids)) != len(observer_ids)
            or any(observer not in {"scout", "recovery", "courier"} for observer in observer_ids)):
        raise ValueError("observer_ids must be a nonempty tuple of unique valid observer IDs")
    return frozenset(observer_ids)


def capture_evidence(service, *, tenant_id, corridor_id, release_id, now_utc,
                     observer_ids=None):
    """Project visible clearance for a loaded courier, preserving its observer.

    The declared corridor/release mapping comes from trusted scenario setup, not
    sensor truth. Samples remain observations, not permissions or recovery proof.
    """
    selected = _selected_observers(observer_ids)
    before = service.status()
    samples = service.observations()['robots']
    after = service.status()
    if (not before['episode_id'] or before['episode_id'] != after['episode_id']
            or before['world_tick'] != after['world_tick']):
        raise ValueError('sensor frame changed during capture')
    payload = samples.get('courier', {}).get('payload', {})
    if payload.get('state') != 'observed' or not payload.get('payload_id'):
        raise ValueError('loaded courier sensor evidence required')
    if selected is not None:
        missing = selected.difference(samples)
        if missing:
            raise ValueError("selected observer is absent from the captured sensor frame")
    result = []
    for observer, sample in sorted(samples.items()):
        if selected is not None and observer not in selected:
            continue
        if sample['robot_id'] != observer or sample['world_tick'] != before['world_tick']:
            raise ValueError('sensor frame identity mismatch')
        gap = sample['gap']
        visible = sample['visibility']['state'] == 'visible'
        value = gap['fits']['courier'] if visible and gap is not None else None
        if value is not None and type(value) is not bool:
            raise ValueError('clearance requires exact boolean or unknown')
        identity = canonical_json_hash({'sample': sample, 'tenant': tenant_id,
            'episode': before['episode_id'], 'corridor': corridor_id, 'release': release_id,
            'recorded_at': now_utc.isoformat()})
        result.append(Observation(
            id='sensor-' + identity, tenant_id=tenant_id, episode_id=before['episode_id'],
            robot_id=observer, occurred_at=now_utc, recorded_at=now_utc,
            world_tick=sample['world_tick'], expires_tick=sample['sensor']['expires_tick'],
            predicate='courier_fit', value=value, pose=Pose.model_validate(sample['pose']),
            visibility=sample['visibility']['state'], scope={'corridor_id': corridor_id,
                'release_id': release_id, 'robot_type': 'courier', 'payload_class': 'loaded'},
            quality={'sensor_mode': sample['sensor']['mode']},
            sensor_config_hash=sample['sensor']['config_hash'], subject_id=corridor_id,
        ))
        # Assessment means locally observed obstruction, never inferred movability.
        base = result[-1].model_dump(mode='json')
        state = sample['obstruction']['state']
        assessed = (state == 'observed') if visible and state in {'observed', 'absent'} else None
        base.update(id='assessed-' + identity, predicate='obstacle_assessed', value=assessed,
                    scope={'corridor_id': corridor_id, 'robot_type': observer})
        result.append(Observation.model_validate(base))
    return tuple(result)
