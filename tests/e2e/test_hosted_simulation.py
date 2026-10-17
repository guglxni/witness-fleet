"""Real hosted HTTP gateway over fresh FalkorDB graph and MuJoCo episode."""
from fastapi.testclient import TestClient
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from witness_fleet.hosting import create_hosted_app

ORIGIN = "https://demo.example.test"


def test_hosted_simulation_executes_real_seven_task_chain(isolated_runtime_graph, tmp_path):  # noqa: F811
    graph = isolated_runtime_graph
    app = create_hosted_app(tmp_path / "hosted", origin=ORIGIN, graph_port=graph.port,
                            revision="test-revision")
    with TestClient(app, base_url=ORIGIN) as client:
        assert client.get("/healthz").json() == {
            "process": "healthy", "simulation_only": True, "revision": "test-revision"}
        assert "Simulation floor" in client.get("/demo").text
        boot = client.get("/demo/v1/bootstrap")
        assert boot.status_code == 200
        bootstrap_csrf = boot.json()["csrf_token"]
        created = client.post("/demo/v1/sessions", json={"request_id": "hosted-create-1"},
            headers={"Origin": ORIGIN, "X-CSRF-Token": bootstrap_csrf})
        assert created.status_code == 201, created.text
        session_csrf = created.json()["csrf_token"]
        initial = created.json()["state"]
        assert initial["mission_phase"] == "recovery_and_verification"
        assert initial["revision_tick"] >= 0
        assert len(initial["tasks"]) == 7
        assert {robot["robot_id"] for robot in initial["robots"]} == {"scout", "recovery", "courier"}

        def post(path, payload):
            response = client.post("/demo/v1/" + path, json=payload,
                headers={"Origin": ORIGIN, "X-CSRF-Token": session_csrf})
            assert response.status_code == 200, response.text
            return response.json()

        paused = post("run", {"request_id": "hosted-seven-run-initial"})
        assert paused["mission_phase"] == "awaiting_owner_release"
        assert len(paused["commands"]) == 4
        assert paused["metrics"]["recovery_verified"] == 1
        assert paused["metrics"]["delivery_completed"] == 0
        assert not any(command.get("robot_id") == "courier" for command in paused["commands"])
        released = post("confirm-release", {
            "request_id": "hosted-explicit-release", "expected_policy_epoch": paused["expected_policy_epoch"],
            "confirmed": True})
        assert released["mission_phase"] == "courier_delivery"
        final = post("run", {"request_id": "hosted-seven-run-final"})
        assert final["mission_phase"] == "complete"
        assert len(final["tasks"]) == 7
        assert all(task["state"] == "VERIFIED" for task in final["tasks"])
        assert len(final["commands"]) == 7
        assert all(command["state"] == "OUTCOME_VERIFIED" for command in final["commands"])
        assert final["metrics"]["delivery_completed"] == 1
        assert all(set(robot["pose"]) == {"x", "y", "yaw"} for robot in final["robots"])
        assert not any(key in str(final).lower() for key in (
            "local_owner_id", "tenant_id", "sources", "payload_json", "native", "traceback"))

        controller = next(iter(app.state.controllers.values()))
        delivered = next(command for command in controller.state()["commands"] if command["kind"] == "deliver")
        receipt = controller.simulator.command(delivered["command_id"])
        assert receipt["state"] == "OUTCOME_VERIFIED"
        assert receipt["native"]["result"]["postcondition"]["payload_in_delivery_zone"] is True
        assert client.get("/api/state").status_code == 404
