import pytest
from fastapi.testclient import TestClient

from witness_fleet.api.app import create_app


def test_state_without_integrated_controller_is_explicitly_unavailable():
    response = TestClient(create_app()).get('/api/state')
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'NOT_READY'


def test_foreign_browser_origin_cannot_create_incident():
    response = TestClient(create_app()).post('/api/incidents', json={'scenario':'SC-001','seed':0,'event_id':'test'}, headers={'origin':'https://evil.example'})
    assert response.status_code == 403


def test_browser_host_rebinding_is_rejected():
    response = TestClient(create_app(), base_url='http://evil.example').get('/api/health')
    assert response.status_code == 400


@pytest.mark.parametrize('field', ['actor_id', 'approved', 'graph_name'])
def test_caller_cannot_smuggle_authority_or_graph_key(field):
    response = TestClient(create_app()).post('/api/incidents', json={'scenario':'SC-001','seed':0,'event_id':'test',field:True})
    assert response.status_code == 422
