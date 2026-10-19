"""Installed hosted UI is a self-contained same-origin application."""
import re
from pathlib import Path

from fastapi.testclient import TestClient

from witness_fleet.hosting import create_hosted_app

ROOT = Path(__file__).resolve().parents[2]


def test_demo_serves_built_same_origin_assets_with_strict_csp(tmp_path):
    app = create_hosted_app(tmp_path, origin='https://demo.example.test')
    with TestClient(app, base_url='https://demo.example.test') as client:
        response = client.get('/demo')
        assert response.status_code == 200
        scripts = re.findall(r'<script[^>]+src="([^"]+)"', response.text)
        styles = re.findall(r'<link[^>]+href="([^"]+\.css)"', response.text)
        assert scripts, 'production JS bundle must be served, not inline legacy UI'
        assert styles, 'production CSS bundle must be served'
        for path in scripts + styles:
            assert path.startswith('/demo/assets/')
            asset = client.get(path)
            assert asset.status_code == 200
            assert len(asset.content) > 50
            assert '<html' not in asset.text[:100].lower()
        csp = response.headers['content-security-policy']
        assert "script-src 'self'" in csp
        assert "script-src 'unsafe-inline'" not in csp
        assert "font-src 'self'" in csp
        assert "object-src 'none'" in csp
        assert client.get('/demo/assets/../scene.py').status_code == 404
        assert client.get('/api/state').status_code == 404
