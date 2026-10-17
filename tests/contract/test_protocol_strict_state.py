import pytest
from test_protocol_commands import command_event

from witness_fleet.simulation.protocol import preflight


@pytest.mark.parametrize('changes', [
    {'policy_epoch': True}, {'coordinator_epoch': False}, {'last_sequence': False},
    {'current_tick': True}, {'task_fences': {'task': True}},
    {'resource_fences': {'corridor': 1.0}},
])
def test_receiver_installed_state_requires_exact_nonboolean_integers(changes):
    state = dict(last_sequence=0, coordinator_epoch=0, policy_epoch=0,
                 task_fences={'task': 1}, resource_fences={'corridor': 1}, current_tick=1)
    state.update(changes)
    result = preflight(command_event(), **state)
    assert result['status'] == 'REJECTED'
    assert result['reason_codes'] == ['INVALID_RECEIVER_STATE']
