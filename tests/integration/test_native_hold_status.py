"""Native-owned HOLD must be visible even when journal identity is unheld."""
from services.simulator.service import SimulatorService


def test_service_reports_native_hold_and_preserves_it_on_restart(tmp_path):
    service = SimulatorService(tmp_path)
    try:
        service.create_episode('native-hold-status', 'SC-001', 3)
        assert service.world is not None
        # Fault injection: the watchdog owns this HOLD, not the dispatch journal.
        service.world.heartbeat(0.0, timeout_s=1.0)
        assert service.world.watchdog_check(2.0)['status'] == 'held'
        assert service.journal.identity()['held'] is False
        status = service.status()
        assert status['held'] is True
        assert status['hold_reason'] == 'heartbeat_timeout'
        assert status['started_commands'] == 0
    finally:
        service.close()
    restored = SimulatorService(tmp_path)
    try:
        assert restored.status()['held'] is True
        assert restored.status()['hold_reason'] == 'heartbeat_timeout'
        assert restored.journal.identity()['held'] is False
    finally:
        restored.close()
