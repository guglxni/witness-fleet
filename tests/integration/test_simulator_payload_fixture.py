"""Payload fixture setup is simulation-owned and cannot replace retained identity."""

import pytest

from services.simulator.service import SimulatorService


def test_payload_setup_stays_behind_simulator_boundary_and_is_idempotent(tmp_path):
    service = SimulatorService(tmp_path)
    try:
        service.create_episode("fixture-payload", "SC-001", 3)
        result = service.load_payload("courier", "parcel-fixture")
        assert result["payload_id"] == "parcel-fixture"
        assert result["robot_id"] == "courier"
        assert result["world_tick"] == 0
        assert service.load_payload("courier", "parcel-fixture") == result
        with pytest.raises(ValueError):
            service.load_payload("courier", "replacement")
        assert service.status()["started_commands"] == 0
    finally:
        service.close()


def test_payload_setup_replay_survives_simulator_restart(tmp_path):
    service = SimulatorService(tmp_path)
    service.create_episode("persistent-payload", "SC-001", 3)
    expected = service.load_payload("courier", "retained-parcel")
    service.close()
    restored = SimulatorService(tmp_path)
    try:
        assert restored.load_payload("courier", "retained-parcel") == expected
        assert restored.observations()["robots"]["courier"]["payload"]["payload_id"] == "retained-parcel"
    finally:
        restored.close()


@pytest.mark.parametrize("robot,payload", [("scout", "parcel"), ("courier", ""), ("courier", None)])
def test_payload_setup_invalid_identity_rejected_without_mutation(tmp_path, robot, payload):
    service = SimulatorService(tmp_path)
    try:
        with pytest.raises(ValueError, match="episode"):
            service.load_payload(robot, payload)
        service.create_episode("invalid-payload", "SC-001", 3)
        with pytest.raises(ValueError):
            service.load_payload(robot, payload)
        assert "payload" not in service.observations()["robots"]["courier"]
        assert service.status()["world_tick"] == 0
    finally:
        service.close()


def test_payload_setup_cannot_teleport_a_parcel_after_physics_advanced(tmp_path):
    service = SimulatorService(tmp_path)
    try:
        service.create_episode("late-payload", "SC-001", 3)
        service.advance(1)
        with pytest.raises(ValueError, match="before execution"):
            service.load_payload("courier", "late-parcel")
        assert "payload" not in service.observations()["robots"]["courier"]
        assert service.status()["world_tick"] == 1
    finally:
        service.close()
