"""Historical sensor-reference validation; not an authorization grant."""

import json
from datetime import UTC, datetime

from witness_fleet.domain import Observation, canonical_json_hash


def validate_release_verification(observation_nodes, verification_json, *, tenant_id,
                                  corridor_id, release_id, approved_at, effective_tick):
    """Verify the two physical predicates at the original approval time only."""
    try:
        if (type(effective_tick) is not int or effective_tick < 0
                or not isinstance(approved_at, datetime) or approved_at.tzinfo is None
                or approved_at.utcoffset() != UTC.utcoffset(approved_at)):
            return False
        retained = list(observation_nodes)
        retained_ids = [node.get('id') for node in retained]
        if (any(not isinstance(identifier, str) or not identifier for identifier in retained_ids)
                or len(set(retained_ids)) != len(retained_ids)):
            return False
        by_id = dict(zip(retained_ids, retained, strict=True))
        refs = json.loads(verification_json)
        if not isinstance(refs, list) or not refs:
            return False
        verified = []
        identifiers = set()
        scope = {'corridor_id': corridor_id, 'release_id': release_id,
                 'robot_type': 'courier', 'payload_class': 'loaded'}
        for ref in refs:
            if not isinstance(ref, dict) or set(ref) != {'observation_id', 'payload_hash'}:
                return False
            identifier = ref['observation_id']
            if not isinstance(identifier, str) or not identifier or identifier in identifiers:
                return False
            identifiers.add(identifier)
            node = by_id.get(identifier)
            if node is None:
                return False
            labels = node.get('labels')
            if (not isinstance(labels, (list, tuple))
                    or not all(isinstance(label, str) for label in labels)
                    or 'Observation' not in labels):
                return False
            obs = Observation.model_validate_json(node['payload_json'])
            if (obs.id != identifier or obs.tenant_id != tenant_id
                    or canonical_json_hash(obs) != ref['payload_hash']
                    or obs.subject_id != corridor_id or dict(obs.scope) != scope
                    or obs.value is not True or obs.visibility != 'visible' or not obs.sensor_config_hash
                    or not obs.world_tick <= effective_tick < obs.expires_tick
                    or obs.occurred_at > approved_at or obs.recorded_at > approved_at):
                return False
            if node.get('predicate') != obs.predicate or node.get('value') is not True:
                return False
            for field in ('tenant_id', 'robot_id', 'episode_id', 'visibility', 'expires_tick',
                          'world_tick', 'sensor_config_hash', 'subject_id'):
                if field in node and (type(node[field]) is not type(getattr(obs, field))
                                      or node[field] != getattr(obs, field)):
                    return False
            if 'scope_json' in node and json.loads(node['scope_json']) != scope:
                return False
            verified.append(obs)
        return ({obs.predicate for obs in verified} == {'recovery_verified', 'courier_fit'}
                and len({obs.episode_id for obs in verified}) == 1)
    except (KeyError, TypeError, ValueError, AttributeError):
        return False
