"""A durably received but unadmitted command requires explicit reconciliation HOLD."""

from test_protocol_commands import command_event
from test_service_admission import control

from services.simulator.service import SimulatorService


def test_stale_fence_rejection_latches_durable_hold_and_retry_is_not_applied_replay(tmp_path):
    with_service = SimulatorService(tmp_path)
    try:
        with_service.create_episode("stale-admission", "SC-001", 3)
        with_service.receive(control("install", 1, "FENCE_INSTALL", {
            "task_id": "task", "task_fence": 2, "resource_fences": {"corridor": 2},
        }))
        event = command_event(sequence=2, fence=1)
        first = with_service.receive(event)
        assert first["status"] == "HOLD"
        assert set(first["reason_codes"]) == {"STALE_TASK_FENCE", "STALE_RESOURCE_FENCE"}
        assert with_service.status()["held"] is True
        assert with_service.status()["hold_reason"] == "admission_rejected"
        assert with_service.world.checkpoint()["held"] is True
        assert with_service.status()["coordinator_epoch"] == 0
        assert with_service.status()["last_sequence"] == 1
        assert with_service.journal.event(event.id)["status"] == "RECEIVED"
        assert with_service.command("cmd")["state"] == "PREPARED"
        assert with_service.receive(event)["status"] == "HOLD"
        assert with_service.status()["started_commands"] == 0
        trusted_hold = with_service.journal.hold_for_reconciliation(1, reason="trusted proof fence")
        assert trusted_hold["status"] == "HELD"
        assert with_service.journal.prove_never_admitted(event.model_dump(mode="json"))["status"] == "NEVER_ADMITTED"
    finally:
        with_service.close()
    resumed = SimulatorService(tmp_path)
    try:
        assert resumed.status()["held"] is True
        assert resumed.receive(event)["status"] == "HOLD"
        assert resumed.command("cmd")["state"] == "PREPARED"
        assert resumed.status()["last_sequence"] == 1
    finally:
        resumed.close()


def test_applied_event_replay_remains_replay_and_does_not_hold(tmp_path):
    service = SimulatorService(tmp_path)
    try:
        service.create_episode("applied-replay", "SC-001", 3)
        fence = control("install", 1, "FENCE_INSTALL", {
            "task_id": "task", "task_fence": 1, "resource_fences": {"corridor": 1},
        })
        assert service.receive(fence)["status"] == "ACCEPTED"
        assert service.receive(fence)["status"] == "REPLAY"
        assert service.status()["held"] is False
        assert service.world.checkpoint()["held"] is False
        assert service.status()["last_sequence"] == 1
    finally:
        service.close()


def test_legacy_unadmitted_replay_latches_hold_before_checkpoint_and_never_admits(tmp_path):
    service = SimulatorService(tmp_path)
    try:
        service.create_episode("legacy-unadmitted", "SC-001", 3)
        fence = control("install", 1, "FENCE_INSTALL", {
            "task_id": "task", "task_fence": 2, "resource_fences": {"corridor": 2},
        })
        assert service.receive(fence)["status"] == "ACCEPTED"
        event = command_event(sequence=2, fence=1)

        # Reproduce the old default journal contract: it leaves a rejected receipt RECEIVED.
        wire = event.model_dump(mode="json")
        assert service.journal.register(wire)["status"] == "ACCEPTED"
        assert service.journal.record_command(
            "cmd", event.payload_hash, "PREPARED", event_id=event.id
        )["status"] == "RECORDED"
        assert service.journal.admit_next(event.id, current_tick=service.world.world_tick)["status"] == "REJECTED"
        assert service.journal.identity()["held"] is False
        assert service.journal.event(event.id)["status"] == "RECEIVED"

        assert service.receive(event)["status"] == "HOLD"
        assert service.journal.identity()["held"] is True
        assert service.world.checkpoint()["held"] is True
        assert service.journal.event(event.id)["status"] == "RECEIVED"
        assert service.command("cmd")["state"] == "PREPARED"
        assert service.status()["started_commands"] == 0
        assert service.status()["last_sequence"] == 1
        checkpoint = service.journal.checkpoint()
        assert checkpoint["last_sequence"] == 1
        assert '"held":true' in checkpoint["state_json"]
    finally:
        service.close()

    resumed = SimulatorService(tmp_path)
    try:
        assert resumed.status()["held"] is True
        assert resumed.world.checkpoint()["held"] is True
        assert resumed.receive(event)["status"] == "HOLD"
        assert resumed.command("cmd")["state"] == "PREPARED"
    finally:
        resumed.close()
