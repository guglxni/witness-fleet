"""Native physical effect observations; never controller status alone."""

import math

from witness_fleet.domain import Observation, canonical_json_hash
from witness_fleet.runtime.sensing import _selected_observers, capture_evidence


def capture_recovery_verification(service, *, command_id, tenant_id, corridor_id,
                                  release_id, now_utc, observer_ids=None):
    """Bind measured contact/displacement to fresh visible connected-lane samples.

    The caller is the trusted local integration owner. This function is not a
    policy grant. It preserves the observer's identity, sensor expiry and native
    episode; a peer's clear ray is not silently relabeled as courier perception.
    """
    _selected_observers(observer_ids)
    with service._lock:
        receipt = service.command(command_id)
        native = receipt.get('native', {})
        displacement = native.get('measured_displacement_m')
        target = native.get('target_displacement_m')
        contacts = native.get('contact_count')
        if (receipt.get('status') != 'KNOWN'
                or receipt.get('state') not in {'CONTROLLER_DONE', 'OUTCOME_VERIFIED'}
                or native.get('kind') != 'recover' or native.get('status') != 'done'
                or type(contacts) is not int or contacts <= 0
                or type(displacement) not in {float, int} or not math.isfinite(displacement)
                or type(target) not in {float, int} or not math.isfinite(target)
                or target <= 0 or displacement < target):
            return ()
        fit = capture_evidence(service, tenant_id=tenant_id, corridor_id=corridor_id,
                               release_id=release_id, now_utc=now_utc,
                               observer_ids=observer_ids)
        result = []
        for observation in fit:
            if (observation.predicate != 'courier_fit' or observation.value is not True
                    or observation.visibility != 'visible'):
                continue
            value = observation.model_dump(mode='json')
            value.update(predicate='recovery_verified', quality={
                **value['quality'], 'recovery_command_id': command_id,
                'receipt_payload_hash': receipt['payload_hash'], 'contact_count': contacts,
                'measured_displacement_m': displacement, 'target_displacement_m': target,
                'clearance_observation_id': observation.id,
            })
            value['id'] = 'recovery-proof-' + canonical_json_hash(value)
            result.append(Observation.model_validate(value))
        return tuple(result)
