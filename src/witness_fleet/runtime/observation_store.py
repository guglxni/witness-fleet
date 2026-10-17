"""Retained observation boundary for trusted native adapters, not an HTTP input."""
import json

from witness_fleet.domain import Observation


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def retain_observations(graph, observations, *, episode_id):
    """Retain immutable typed telemetry and exact episode links, never grant policy."""
    if not isinstance(observations, tuple) or any(not isinstance(o, Observation) for o in observations):
        raise ValueError('typed immutable observation tuple required')
    if (not episode_id or graph.get_node('Episode', episode_id) is None
            or len({o.id for o in observations}) != len(observations)):
        raise ValueError('unique observations and retained episode required')
    checked = tuple(Observation.model_validate(o.model_dump(mode='json')) for o in observations)
    if any(o.episode_id != episode_id or o.tenant_id != graph.tenant_id for o in checked):
        raise ValueError('native observation identity mismatches run')
    for observation in checked:
        payload = observation.model_dump(mode='json')
        graph.append_node('Observation', observation.id, {
            'predicate': observation.predicate, 'value': observation.value,
            'robot_id': observation.robot_id, 'pose': _json(payload['pose']),
            'frame': observation.frame, 'visibility': observation.visibility,
            'quality': _json(payload['quality']), 'expires_tick': observation.expires_tick,
            'scope_json': _json(payload['scope']),
            'payload_json': _json(payload),
        })
        graph.append_edge('CONTAINS', 'Episode', episode_id, 'Observation', observation.id)
        retained = graph.get_node('Observation', observation.id)
        if Observation.model_validate_json(retained['payload_json']) != observation:
            raise ValueError('retained native observation differs from captured record')
    return checked
