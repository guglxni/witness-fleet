"""Pure receiver validation. Journal and physics own effects; this module does not."""

from collections.abc import Mapping

from witness_fleet.domain import CommandIntent, DispatchEvent


def preflight(event: DispatchEvent, *, last_sequence, coordinator_epoch, policy_epoch, task_fences, resource_fences, current_tick,
             allow_reconciliation_equal_epoch: bool = False):
    if type(allow_reconciliation_equal_epoch) is not bool:
        return {'status': 'REJECTED', 'reason_codes': ['INVALID_RECEIVER_STATE']}
    counters = (last_sequence, coordinator_epoch, policy_epoch, current_tick)
    def valid_map(mapping):
        return (isinstance(mapping, Mapping)
                and all(isinstance(key, str) and key and type(value) is int and value >= 0
                        for key, value in mapping.items()))
    if (any(type(counter) is not int or counter < 0 for counter in counters)
            or not valid_map(task_fences) or not valid_map(resource_fences)):
        return {'status': 'REJECTED', 'reason_codes': ['INVALID_RECEIVER_STATE']}
    reasons = []
    if event.sequence <= last_sequence:
        return {'status': 'HOLD', 'reason_codes': ['JOURNAL_IDENTITY_CHECK_REQUIRED']}
    if event.sequence != last_sequence + 1:
        return {'status': 'HOLD', 'reason_codes': ['SEQUENCE_GAP']}
    if event.effective_world_tick > current_tick:
        return {'status': 'HOLD', 'reason_codes': ['EVENT_NOT_YET_EFFECTIVE']}
    if event.coordinator_epoch < coordinator_epoch:
        return {'status': 'REJECTED', 'reason_codes': ['STALE_COORDINATOR_EPOCH']}
    if event.kind == 'EPOCH_BARRIER':
        if (type(event.payload.get('coordinator_epoch')) is not int
                or event.payload['coordinator_epoch'] != event.coordinator_epoch):
            reasons.append('INVALID_EPOCH_BARRIER')
        if event.coordinator_epoch <= coordinator_epoch:
            equal_resume = (allow_reconciliation_equal_epoch
                            and event.kind == 'EPOCH_BARRIER'
                            and event.coordinator_epoch == coordinator_epoch)
            if not equal_resume:
                reasons.append('EPOCH_NOT_INCREASING')
    elif event.coordinator_epoch != coordinator_epoch or allow_reconciliation_equal_epoch:
        reasons.append('EPOCH_BARRIER_REQUIRED')

    if event.kind == 'FENCE_INSTALL':
        data = event.payload
        fences = data.get('resource_fences')
        task = data.get('task_id')
        fence = data.get('task_fence')
        if (not isinstance(task, str) or not task or type(fence) is not int or fence < 1
                or not isinstance(fences, Mapping)):
            reasons.append('INVALID_FENCE_INSTALL')
        else:
            if fence < task_fences.get(task, 0):
                reasons.append('FENCE_ROLLBACK')
            for resource, value in fences.items():
                if not isinstance(resource, str) or not resource or type(value) is not int or value < 1:
                    reasons.append('INVALID_FENCE_INSTALL')
                elif value < resource_fences.get(resource, 0):
                    reasons.append('FENCE_ROLLBACK')
    elif event.kind in ('POLICY_ACTIVATION', 'REVOCATION'):
        payload = event.payload
        new_epoch = payload.get('policy_epoch')
        previous_epoch = payload.get('expected_previous_policy_epoch')
        proof = payload.get('policy_proof')
        if (type(new_epoch) is not int or new_epoch < 0 or type(previous_epoch) is not int
                or previous_epoch < 0 or previous_epoch != policy_epoch or new_epoch <= policy_epoch):
            reasons.append('INVALID_POLICY_TRANSITION')
        proof_id = proof.get('proof_id') if isinstance(proof, Mapping) else None
        if (not isinstance(proof, Mapping) or proof.get('coordinator_epoch') != coordinator_epoch
                or type(proof.get('coordinator_epoch')) is not int
                or type(proof_id) is not str or not proof_id):
            reasons.append('UNTRUSTED_POLICY_PROOF')
    elif event.kind == 'COMMAND':
        try:
            command = CommandIntent.model_validate(event.payload)
        except (TypeError, ValueError):
            return {'status': 'REJECTED', 'reason_codes': ['INVALID_COMMAND']}
        if (command.dispatch_sequence != event.sequence or command.coordinator_epoch != coordinator_epoch
                or command.effective_world_tick != event.effective_world_tick):
            reasons.append('COMMAND_ENVELOPE_MISMATCH')
        if command.policy_epoch != policy_epoch:
            reasons.append('STALE_POLICY_EPOCH')
        if task_fences.get(command.proposal.task_id) != command.fence:
            reasons.append('STALE_TASK_FENCE')
        required_resources = set(command.proposal.required_resource_ids)
        if not required_resources.issubset(command.resource_fences):
            reasons.append('INCOMPLETE_RESOURCE_FENCES')
        if any(resource_fences.get(key) != value for key, value in command.resource_fences.items()):
            reasons.append('STALE_RESOURCE_FENCE')
        if not command.effective_world_tick <= current_tick < command.authorization.valid_until_tick:
            reasons.append('EXPIRED_OR_EARLY_AUTHORIZATION')
    return {'status': 'REJECTED' if reasons else 'ACCEPTED', 'reason_codes': sorted(set(reasons))}
