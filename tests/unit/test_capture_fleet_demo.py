import argparse
import json
from pathlib import Path

import pytest

import scripts.capture_fleet_demo as capture_fleet_demo
from scripts.capture_fleet_demo import (
    build_parser,
    is_complete_mission,
    project_state,
    validate_args,
)


def parse(run_dir: Path, *extra: str) -> argparse.Namespace:
    return build_parser().parse_args([
        "--run-dir", str(run_dir), "--graph-port", "6394", "--output", "fleet-demo.mp4",
        "--approve-demo-owner", *extra,
    ])


def test_requires_a_new_empty_retained_run_directory(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "keep.txt").write_text("retained data")

    with pytest.raises(ValueError, match="empty"):
        validate_args(parse(run_dir))


def test_accepts_output_inside_empty_run_directory(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    options = validate_args(parse(run_dir))

    assert options.run_dir == run_dir.resolve()
    assert options.output == run_dir / "fleet-demo.mp4"
    assert options.graph_port == 6394
    assert options.approve_demo_owner is True


def test_rejects_output_outside_retained_run_directory(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    outside = tmp_path / "outside.mp4"

    with pytest.raises(ValueError, match="inside the run directory"):
        validate_args(parse(run_dir, "--output", str(outside)))


def test_rejects_existing_video_output(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "fleet-demo.mp4").write_bytes(b"existing")

    with pytest.raises(ValueError, match="empty"):
        validate_args(parse(run_dir))


def _successful_mission():
    return {
        "tasks": [{"id": f"task-{i}", "state": "VERIFIED"} for i in range(7)],
        "commands": [{"command_id": f"command-{i}", "task_id": f"task-{i}",
                       "state": "OUTCOME_VERIFIED",
                       "native_receipt": {"status": "done"},
                       "local_receipt": {"status": "KNOWN", "state": "OUTCOME_VERIFIED"}}
                      for i in range(7)],
        "approval_required": False, "mission_phase": "complete",
        "metrics": {"recovery_verified": 1, "delivery_completed": 1},
        "dispatch_ready": True, "held": False,
    }


def test_completion_requires_verified_task_receipts_and_no_hold():
    successful = _successful_mission()

    assert is_complete_mission(successful, held=False)
    assert not is_complete_mission(successful, held=True)
    for field, value in (("tasks", [{"id": f"task-{i}", "state": "VERIFIED"}
                                    for i in range(6)] + [{"id": "task-6", "state": "FAILED"}]),
                         ("approval_required", True), ("dispatch_ready", False), ("held", True)):
        assert not is_complete_mission({**successful, field: value}, held=False)


def test_mission_completion_requires_unique_task_and_command_identity():
    successful = _successful_mission()
    duplicate_task = {**successful, "tasks": [{"id": f"task-{i}", "state": "VERIFIED"}
                                               for i in range(6)] + [{"id": "task-0", "state": "VERIFIED"}]}
    duplicate_command = {**successful, "commands": successful["commands"][:-1]
                         + [{**successful["commands"][-1], "task_id": "task-0"}]}

    assert not is_complete_mission(duplicate_task, held=False)
    assert not is_complete_mission(duplicate_command, held=False)


def test_state_provenance_keeps_receipts_and_graph_events_without_private_poses():
    manifest = {"task_ids": ["task-1"], "release_id": "release-1"}
    observation = {
        "id": "obs-1", "predicate": "recovery_verified", "value": True,
        "robot_id": "scout", "world_tick": 12, "visibility": "visible",
        "quality": 0.9, "sensor_config_hash": "sensor-hash", "expires_tick": 60,
        "scope": {"corridor_id": "corridor-1"}, "pose": {"x": 1.2, "y": -0.3},
    }
    state = {
        "episode_id": "episode-1", "scenario": "SC-001", "world_tick": 13,
        "graph_version": 55, "policy_epoch": 2, "coordinator_epoch": 1,
        "dispatch_sequence": 11, "dispatch_ready": True, "held": False,
        "mission_phase": "complete", "approval_required": False,
        "metrics": {"recovery_verified": 1, "delivery_completed": 1,
                    "unauthorized_executed": None},
        "tasks": [{"id": "task-1", "state": "VERIFIED"}],
        "commands": [{"command_id": "command-1", "task_id": "task-1",
                       "state": "OUTCOME_VERIFIED", "native": {
                           "status": "done", "world_tick": 12,
                           "result": {"pose": {"x": 2.3, "y": 0.1}},
                       }, "local_receipt": {
                           "status": "KNOWN", "state": "OUTCOME_VERIFIED",
                           "payload_hash": "receipt-hash",
                       }}],
        "events": [{"event_id": "event-1", "subject_ids_json": json.dumps(
            ["task-1", "release-1"])}],
        "sources": [{"source_id": "source-1", "revision_id": "source-1:hash",
                      "normalized_hash": "normalized-hash"}],
        "observations": [observation],
        "robots": [{"id": "scout", "pose": {"x": 3.4, "y": 0.2}}],
    }

    projected = project_state(state, manifest)

    assert [event["event_id"] for event in projected["events"]] == ["event-1"]
    assert projected["commands"][0]["native_receipt"]["status"] == "done"
    assert projected["commands"][0]["local_receipt"]["payload_hash"] == "receipt-hash"
    assert "pose" not in json.dumps(projected)
    assert projected["observations"][0]["payload_sha256"]
    assert projected["observations"][0]["predicate"] == "recovery_verified"
    assert projected["metrics"]["unauthorized_executed"] is None
    # Finalization passes already projected command receipts; preserve them on replay.
    reprojected = project_state(projected, manifest)
    assert reprojected["commands"][0]["native_receipt"] == projected["commands"][0]["native_receipt"]
    assert reprojected["commands"][0]["local_receipt"] == projected["commands"][0]["local_receipt"]


def test_invalid_run_directory_never_gets_a_failure_report_written(tmp_path, capsys):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    retained = run_dir / "keep.txt"
    retained.write_text("retained data")

    status = capture_fleet_demo.main([
        "--run-dir", str(run_dir), "--graph-port", "6394", "--output", "fleet-demo.mp4",
        "--approve-demo-owner",
    ])

    assert status != 0
    assert retained.read_text() == "retained data"
    assert not (run_dir / "failure-report.json").exists()
    assert json.loads(capsys.readouterr().out)["status"] == "failed"


def test_missing_graph_service_writes_only_an_explicit_failure_report(tmp_path, capsys):
    run_dir = tmp_path / "run"
    status = capture_fleet_demo.main([
        "--run-dir", str(run_dir), "--graph-port", "6399", "--output", "fleet-demo.mp4",
        "--approve-demo-owner",
    ])

    assert status != 0
    failure = json.loads((run_dir / "failure-report.json").read_text())
    assert failure["status"] == "failed"
    assert not (run_dir / "manifest.json").exists()
    assert not (run_dir / "mission-state.json").exists()
    assert json.loads(capsys.readouterr().out)["status"] == "failed"


def test_capture_closes_falkordb_public_client_without_masking_failure(tmp_path, monkeypatch):
    """FalkorDB exposes close(), not Redis.connection_pool."""
    import witness_fleet.graph
    import witness_fleet.runtime.bootstrap

    closed = []

    class Client:
        def select_graph(self, name):
            return object()

        def close(self):
            closed.append("graph")

    class Graph:
        def __init__(self, **kwargs):
            self._client = Client()

        def initialize(self):
            raise ValueError("intentional bootstrap failure")

    class Simulator:
        def __init__(self, root):
            pass

        def status(self):
            return {"held": True}

        def close(self):
            closed.append("simulator")

    monkeypatch.setattr(capture_fleet_demo, "_graph_port_is_listening", lambda port: True)
    monkeypatch.setattr(capture_fleet_demo, "RecordingSimulatorService", Simulator)
    monkeypatch.setattr(witness_fleet.graph, "GraphStore", Graph)
    result = capture_fleet_demo.capture(parse(tmp_path / "run"))
    assert result["status"] == "failed"
    assert result["error"] == "ValueError: intentional bootstrap failure"
    assert closed == ["simulator", "graph"]


def test_demo_owner_action_requires_explicit_opt_in(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    args = build_parser().parse_args([
        "--run-dir", str(run_dir), "--graph-port", "6394", "--output", "fleet-demo.mp4",
    ])

    with pytest.raises(SystemExit):
        validate_args(args)
