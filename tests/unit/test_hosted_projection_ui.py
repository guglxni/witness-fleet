"""Production scene projection replaces the old illustrative SVG without fake zones."""
from fastapi.testclient import TestClient

from services.simulator.visualization import _GEOMETRY_ALLOWLIST
from witness_fleet.hosting import create_hosted_app


def test_floor_projection_contains_courier_and_native_coordinates(tmp_path):
    assert 'courier_chassis' in _GEOMETRY_ALLOWLIST
    app = create_hosted_app(tmp_path, origin='https://demo.example.test')
    with TestClient(app, base_url='https://demo.example.test') as client:
        page = client.get('/demo')
        assert page.status_code == 200
        assert client.get('/demo/').status_code == 200
        assert '/demo/assets/' in page.text
        assert 'SAFE ZONE' not in page.text
        assert 'Number(p.x)||0' not in page.text
        assert client.get('/demo/v1/scene').status_code == 401
