"""Contact/pose evidence is distinct from optical clearance, never a blanket bypass."""
from datetime import UTC, datetime

from test_command_effects import native_event
from test_service_admission import control

from services.simulator.service import SimulatorService
from witness_fleet.domain import CommandIntent, Observation


def test_contact_effect_is_eligible_when_ray_view_is_insufficient(tmp_path):
    from witness_fleet.runtime.command_effects import capture_command_effects
    from witness_fleet.runtime.measurement_validation import measured_effect_valid
    service = SimulatorService(tmp_path)
    try:
        service.create_episode('modality', 'SC-001', 3)
        service.load_payload('courier', 'parcel')
        service.receive(control('fence', 1, 'FENCE_INSTALL', {
            'task_id': 'task', 'task_fence': 1, 'resource_fences': {'corridor': 1}}))
        event = native_event(service, kind='recover', robot='recovery', parameters={
            'target_displacement_m': .75, 'timeout_ticks': 2000, 'execution_until_tick': 2000},
            effects=['obstruction_moved'])
        command = CommandIntent.model_validate(event.payload)
        service.receive(event)
        while service.command(command.command_id)['state'] == 'RUNNING':
            service.advance(1)
        obs, = capture_command_effects(service, command=command, now_utc=datetime.now(UTC))
        assert obs.visibility == 'insufficient'
        assert measured_effect_valid(command, obs)
        for field, value in [('contact_count', 0), ('measured_displacement_m', 0),
                             ('receipt_payload_hash', 'wrong'), ('command_id', 'wrong')]:
            data = obs.model_dump(mode='json')
            data['quality'][field] = value
            assert not measured_effect_valid(command, Observation.model_validate(data))
    finally:
        service.close()


def test_stable_native_delivery_has_independent_payload_evidence(tmp_path):
    from test_effect_measurement_bounds import _collect_window, _delivery_fixture

    from witness_fleet.runtime.command_effects import capture_command_effects
    from witness_fleet.runtime.measurement_validation import measured_effect_valid
    service, command, receipt = _delivery_fixture(tmp_path, 'modality-delivery')
    try:
        window = _collect_window(service, command)
        obs, = capture_command_effects(service, command=command, now_utc=datetime.now(UTC),
                                       stability_window=window)
        assert measured_effect_valid(command, obs)
        for field, value in [('payload_id', ''), ('delivery_postcondition', {}),
                             ('stability_window', {}), ('receipt_payload_hash', 'wrong')]:
            data = obs.model_dump(mode='json')
            data['quality'][field] = value
            assert not measured_effect_valid(command, Observation.model_validate(data))
    finally:
        service.close()

