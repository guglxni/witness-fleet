"""Observer selection is explicit before native sampling and preserves all values."""
from datetime import UTC, datetime

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from services.simulator.service import SimulatorService
from witness_fleet.runtime.effects import capture_recovery_verification
from witness_fleet.runtime.sensing import capture_evidence


def _service(tmp_path, episode_id):
    service = SimulatorService(tmp_path)
    service.create_episode(episode_id, "SC-001", 3)
    service.load_payload("courier", episode_id + "-parcel")
    return service


def test_capture_evidence_selects_observers_before_sampling_and_keeps_unknown(
        tmp_path, monkeypatch, isolated_runtime_graph, isolated_console_graph):  # noqa: F811
    graph_version = isolated_runtime_graph.read_version_root()
    console_version = isolated_console_graph.read_version_root()
    service = _service(tmp_path, "observer-selected")
    try:
        original = service.observations
        requested = []

        def observations():
            requested.append(True)
            return original()

        monkeypatch.setattr(service, "observations", observations)
        evidence = capture_evidence(service, tenant_id="demo", corridor_id="corridor",
                                    release_id="release", now_utc=datetime.now(UTC),
                                    observer_ids=("courier", "scout"))

        assert requested == [True]
        assert {item.robot_id for item in evidence} == {"scout", "courier"}
        fits = {item.robot_id: item for item in evidence if item.predicate == "courier_fit"}
        assert set(fits) == {"scout", "courier"}
        assert fits["scout"].value is False
        courier_fit = fits["courier"]
        assert courier_fit.value is None
        assert courier_fit.visibility == "insufficient"
        assert {item.robot_id for item in evidence if item.predicate == "obstacle_assessed"} == {
            "scout", "courier"
        }
        assert isolated_runtime_graph.read_version_root() == graph_version
        assert isolated_console_graph.read_version_root() == console_version
    finally:
        service.close()


def test_capture_evidence_rejects_invalid_or_duplicate_observer_ids_before_capture(tmp_path, monkeypatch):
    service = _service(tmp_path, "invalid-observers")
    try:
        monkeypatch.setattr(service, "observations", lambda: pytest.fail("capture must not run"))
        for observer_ids in (("scout", "scout"), ("scout", "unknown"), (), "scout", (1,)):
            with pytest.raises(ValueError, match="observer"):
                capture_evidence(service, tenant_id="demo", corridor_id="corridor",
                                 release_id="release", now_utc=datetime.now(UTC),
                                 observer_ids=observer_ids)
    finally:
        service.close()


def test_capture_evidence_rejects_incomplete_selected_observer_frame(tmp_path, monkeypatch):
    service = _service(tmp_path, "incomplete-observers")
    try:
        frame = service.observations()
        del frame["robots"]["scout"]
        monkeypatch.setattr(service, "observations", lambda: frame)
        with pytest.raises(ValueError, match="selected observer"):
            capture_evidence(service, tenant_id="demo", corridor_id="corridor",
                             release_id="release", now_utc=datetime.now(UTC),
                             observer_ids=("scout",))
    finally:
        service.close()


def test_capture_evidence_default_still_captures_every_native_observer(tmp_path):
    service = _service(tmp_path, "default-observers")
    try:
        evidence = capture_evidence(service, tenant_id="demo", corridor_id="corridor",
                                    release_id="release", now_utc=datetime.now(UTC))
        assert {item.robot_id for item in evidence} == {"scout", "recovery", "courier"}
    finally:
        service.close()


def test_recovery_verification_observer_selection_preserves_nonpositive_selected_records(
        tmp_path, monkeypatch, isolated_runtime_graph, isolated_console_graph):  # noqa: F811
    graph_version = isolated_runtime_graph.read_version_root()
    console_version = isolated_console_graph.read_version_root()
    service = _service(tmp_path, "selected-recovery-proof")
    try:
        receipt = {
            "status": "KNOWN", "state": "CONTROLLER_DONE", "payload_hash": "measured-hash",
            "native": {"kind": "recover", "status": "done", "contact_count": 2,
                       "measured_displacement_m": 0.8, "target_displacement_m": 0.75},
        }
        command_id = "recovery-event"
        # The service command reader expects native receipt output; no simulator action occurs.
        monkeypatch.setattr(service, "command", lambda requested_id: receipt)
        original = service.observations
        calls = []

        def observations():
            calls.append(True)
            frame = original()
            scout = frame["robots"]["scout"]
            scout["visibility"] = {"state": "visible", "fraction": 1.0}
            scout["gap"] = {"fits": {"courier": True}, "visibility": "visible"}
            return frame

        monkeypatch.setattr(service, "observations", observations)
        proofs = capture_recovery_verification(
            service, command_id=command_id, tenant_id="demo", corridor_id="corridor",
            release_id="release", now_utc=datetime.now(UTC), observer_ids=("courier", "scout"),
        )
        assert calls == [True]
        assert {proof.robot_id for proof in proofs} == {"scout"}
        assert all(proof.predicate == "recovery_verified" and proof.value is True for proof in proofs)
        assert isolated_runtime_graph.read_version_root() == graph_version
        assert isolated_console_graph.read_version_root() == console_version
    finally:
        service.close()


def test_recovery_verification_rejects_invalid_observer_ids_before_receipt_or_capture(tmp_path, monkeypatch):
    service = _service(tmp_path, "invalid-recovery-observers")
    try:
        monkeypatch.setattr(service, "command", lambda requested_id: pytest.fail("receipt must not be read"))
        monkeypatch.setattr(service, "observations", lambda: pytest.fail("capture must not run"))
        with pytest.raises(ValueError, match="observer"):
            capture_recovery_verification(
                service, command_id="missing", tenant_id="demo", corridor_id="corridor",
                release_id="release", now_utc=datetime.now(UTC), observer_ids=("scout", "scout"),
            )
    finally:
        service.close()


def test_recovery_verification_default_observer_selection_remains_all_observers(tmp_path, monkeypatch):
    service = _service(tmp_path, "default-recovery-proof")
    try:
        receipt = {
            "status": "KNOWN", "state": "CONTROLLER_DONE", "payload_hash": "measured-hash",
            "native": {"kind": "recover", "status": "done", "contact_count": 2,
                       "measured_displacement_m": 0.8, "target_displacement_m": 0.75},
        }
        monkeypatch.setattr(service, "command", lambda requested_id: receipt)
        calls = []
        original = service.observations

        def observations():
            calls.append(True)
            return original()

        monkeypatch.setattr(service, "observations", observations)
        capture_recovery_verification(service, command_id="recovery-event", tenant_id="demo",
                                      corridor_id="corridor", release_id="release",
                                      now_utc=datetime.now(UTC))
        assert calls == [True]
    finally:
        service.close()
