from fastapi.testclient import TestClient

from witness_fleet.api.app import create_app


def test_health_reports_installed_dependencies_but_no_false_dispatch_ready():
    client = TestClient(create_app())
    result = client.get('/api/health')
    assert result.status_code == 200
    body = result.json()
    assert body['process'] == 'healthy'
    assert body['dispatch_ready'] is False
    assert body['dependencies']['status'] == 'ok'
