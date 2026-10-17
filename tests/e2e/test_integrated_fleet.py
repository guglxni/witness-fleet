"""End-to-end opt-in mission against additive isolated graph + native runtime."""
import uuid

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from services.simulator.service import SimulatorService
from witness_fleet.ingestion.source_store import SourceStore
from witness_fleet.runtime.bootstrap import bootstrap
from witness_fleet.runtime.mission import MissionController


@pytest.fixture
def mission_controller(isolated_console_graph, isolated_runtime_graph, tmp_path):  # noqa: F811
    graph = isolated_console_graph
    sources = SourceStore(tmp_path / "sources")
    prefix = "e2e-mission-" + uuid.uuid4().hex[:16]
    manifest = bootstrap(graph, sources, prefix=prefix, scenario="SC-001", seed=3,
                         profile="mission-v2")
    simulator = SimulatorService(tmp_path / "sim")
    simulator.create_episode(manifest["episode_id"], "SC-001", 3)
    simulator.load_payload("courier", prefix + "-parcel")
    controller = MissionController(graph, sources, simulator)
    try:
        yield controller
    finally:
        controller.close()


def test_opt_in_mission_requires_owner_gate_then_verifies_native_delivery(mission_controller):
    controller = mission_controller
    assert controller.manifest["profile"] == "mission-v2"
    assert controller.principal.role == "maintenance_owner"
    assert controller.principal.trust_mode == "configured_local"

    gated = controller.run("e2e-run-" + uuid.uuid4().hex)
    plan = controller.manifest["task_plan"]
    assert gated["approval_required"] is True
    assert gated["mission_phase"] == "awaiting_owner_release"
    assert gated["operator_mode"] == "local_mission"
    assert gated["model_mode"] == "disabled"
    assert gated["metrics"]["recovery_verified"] == 1
    assert gated["metrics"]["delivery_completed"] == 0
    assert gated["metrics"]["unauthorized_executed"] is None
    assert len(gated["tasks"]) == len(plan) == 7
    assert sum(task["state"] == "VERIFIED" for task in gated["tasks"]) == 4
    assert len(gated["commands"]) == 4
    assert all(command["kind"] != "deliver" for command in gated["commands"])
    assert controller.graph.get_node("Release", gated["release_id"])["state"] == "staged"

    recovery = next(command for command in gated["commands"] if command["kind"] == "recover")
    assert recovery["state"] == "OUTCOME_VERIFIED"
    witness = controller.witness(gated["restrictions"][0]["id"])
    assert witness["completeness"] == "complete"
    assert witness["spans"]

    released = controller.approve_release(
        gated["release_id"], gated["policy_epoch"], "e2e-owner-release-" + uuid.uuid4().hex,
    )
    assert released["metrics"]["unauthorized_executed"] is None
    assert controller.graph.get_node("Release", gated["release_id"])["state"] == "released"

    final = controller.run("e2e-delivery-" + uuid.uuid4().hex)
    assert final["mission_phase"] == "complete"
    assert final["approval_required"] is False
    assert final["metrics"]["delivery_completed"] == 1
    assert final["metrics"]["recovery_verified"] == 1
    assert final["metrics"]["unauthorized_executed"] is None
    assert len(final["tasks"]) == len(plan) == 7
    assert all(task["state"] == "VERIFIED" for task in final["tasks"])
    assert len(final["commands"]) == len(plan) == 7
    assert len({command["command_id"] for command in final["commands"]}) == 7
    assert {command["task_id"] for command in final["commands"]} == {
        entry["task_id"] for entry in plan
    }
    assert all(command["state"] == "OUTCOME_VERIFIED" and command["native"]
               for command in final["commands"])

    delivered = next(command for command in final["commands"] if command["kind"] == "deliver")
    receipt = controller.simulator.command(delivered["command_id"])
    assert receipt["state"] == "OUTCOME_VERIFIED"
    assert receipt["native"]["result"]["postcondition"]["payload_in_delivery_zone"] is True
    assert controller.simulator.observations()["robots"]["courier"]["payload"]["delivery_zone"] is True
