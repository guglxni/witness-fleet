"""Real FalkorDB/MuJoCo mission through the same HTTP API used by the console."""
from fastapi.testclient import TestClient
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from witness_fleet.api.mission import create_mission_app


def test_operator_http_path_pauses_for_owner_then_delivers(isolated_console_graph, tmp_path):  # noqa: F811
    graph = isolated_console_graph
    app = create_mission_app(tmp_path / 'mission', graph=graph, graph_port=graph.port)
    with TestClient(app) as client:
        initial = client.get('/api/state').json()
        assert initial['operator_mode'] == 'local_mission'
        assert initial['mission_phase'] == 'recovery_and_verification'
        assert initial['world_tick'] == 0 and initial['commands'] == []
        blocked = client.post('/api/run', json={'event_id': 'cross-site'},
                              headers={'Origin': 'https://untrusted.invalid'})
        assert blocked.status_code == 403
        assert client.get('/api/state').json()['world_tick'] == 0
        premature = client.post(f"/api/releases/{initial['release_id']}/approve", json={
            'event_id': 'premature', 'expected_policy_epoch': initial['policy_epoch']})
        assert premature.status_code == 409
        response = client.post('/api/run', json={'event_id': 'recovery-and-inspection'})
        assert response.status_code == 200, response.text
        paused = response.json()
        assert paused['mission_phase'] == 'awaiting_owner_release'
        assert paused['approval_required'] is True
        assert len(paused['commands']) == 4
        assert not any(c['robot_id'] == 'courier' for c in paused['commands'])
        assert paused['metrics']['recovery_verified'] == 1
        assert paused['metrics']['delivery_completed'] == 0
        witness = client.get(f"/api/decisions/{paused['restrictions'][0]['id']}/witness")
        assert witness.status_code == 200
        assert witness.json()['completeness'] == 'complete'
        assert witness.json()['spans']
        source = client.get(f"/api/sources/{paused['sources'][0]['revision_id']}")
        assert source.status_code == 200
        root = graph.read_version_root()
        stale = client.post(f"/api/releases/{paused['release_id']}/approve", json={
            'event_id': 'stale', 'expected_policy_epoch': paused['policy_epoch'] + 1})
        assert stale.status_code == 409
        forged = client.post(f"/api/releases/{paused['release_id']}/approve", json={
            'event_id': 'forged', 'expected_policy_epoch': paused['policy_epoch'],
            'actor_id': 'attacker'})
        assert forged.status_code == 422
        assert graph.read_version_root() == root
        released = client.post(f"/api/releases/{paused['release_id']}/approve", json={
            'event_id': 'explicit-configured-demo-owner',
            'expected_policy_epoch': paused['policy_epoch']})
        assert released.status_code == 200, released.text
        assert released.json()['mission_phase'] == 'courier_delivery'
        response = client.post('/api/run', json={'event_id': 'fresh-courier-delivery'})
        assert response.status_code == 200, response.text
        final = response.json()
        assert final['mission_phase'] == 'complete'
        assert len(final['commands']) == 7
        assert all(t['state'] == 'VERIFIED' for t in final['tasks'])
        assert all(c['state'] == 'OUTCOME_VERIFIED' for c in final['commands'])
        assert final['metrics']['delivery_completed'] == 1
        assert final['approval_required'] is False
        assert final['dispatch_ready'] is True
        delivered = next(c for c in final['commands'] if c['kind'] == 'deliver')
        receipt = client.get(f"/api/commands/{delivered['command_id']}").json()
        assert receipt['native']['result']['postcondition']['payload_in_delivery_zone'] is True
        for command in final['commands']:
            durable = app.state.controller.simulator.journal.receipt(command['command_id'])
            assert durable['status'] == 'KNOWN'
            assert durable['state'] == 'OUTCOME_VERIFIED'
        stream = client.get('/api/events?once=true')
        assert stream.status_code == 200
        assert 'event: snapshot' in stream.text
        assert '"mission_phase":"complete"' in stream.text
