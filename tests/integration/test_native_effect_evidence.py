"""Physical effect projection uses measured native receipts AND fresh scoped rays."""
from datetime import UTC, datetime

from test_native_execution_window import recovery_command
from test_service_admission import control

from services.simulator.service import SimulatorService
from witness_fleet.runtime.effects import capture_recovery_verification


def test_recovery_verification_requires_measured_displacement_and_fresh_rays(tmp_path):
    service = SimulatorService(tmp_path)
    try:
        service.create_episode('effect-evidence', 'SC-001', 3)
        service.load_payload('courier', 'parcel')
        service.receive(control('fence', 1, 'FENCE_INSTALL', {
            'task_id': 'task', 'task_fence': 1, 'resource_fences': {'corridor': 1}}))
        event = recovery_command(service)
        assert service.receive(event)['command_state'] == 'RUNNING'
        assert capture_recovery_verification(service, command_id=event.id, tenant_id='demo',
            corridor_id='corridor', release_id='release', now_utc=datetime.now(UTC)) == ()
        # Allow the native recovery controller to finish within its authorized
        # 2000-tick execution window (the physics outcome remains measured).
        service.advance(2000)
        observations = capture_recovery_verification(service, command_id=event.id,
            tenant_id='demo', corridor_id='corridor', release_id='release', now_utc=datetime.now(UTC))
        assert observations
        assert all(o.predicate == 'recovery_verified' and o.value is True for o in observations)
        assert all(o.scope['release_id'] == 'release' and o.world_tick == 2000 for o in observations)
        assert all(o.quality['recovery_command_id'] == event.id and o.quality['contact_count'] > 0
                   and o.quality['measured_displacement_m'] >= .75 for o in observations)
        assert {o.robot_id for o in observations} == {'scout'}
    finally:
        service.close()


def test_unknown_receipt_cannot_become_recovery_evidence(tmp_path):
    service = SimulatorService(tmp_path)
    try:
        service.create_episode('unknown-effect', 'SC-001', 3)
        service.load_payload('courier', 'parcel')
        assert capture_recovery_verification(service, command_id='missing', tenant_id='demo',
            corridor_id='corridor', release_id='release', now_utc=datetime.now(UTC)) == ()
    finally:
        service.close()
