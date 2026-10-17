"""CLI composition seam tests, not fleet acceptance."""
from typer.testing import CliRunner

from witness_fleet.cli import app


def test_serve_binds_only_loopback_and_uses_explicit_retained_root(monkeypatch, tmp_path):
    import uvicorn

    from witness_fleet.api import local

    calls = []
    sentinel = object()
    monkeypatch.setattr(local, 'create_local_app', lambda root, **kwargs:
                        calls.append(('compose', root, kwargs)) or sentinel)
    monkeypatch.setattr(uvicorn, 'run', lambda app, **kwargs:
                        calls.append(('serve', app, kwargs)))
    result = CliRunner().invoke(app, ['serve', '--run-dir', str(tmp_path),
        '--graph-port', '6382', '--port', '8094'])
    assert result.exit_code == 0, result.output
    assert calls[0][0:2] == ('compose', tmp_path)
    assert calls[0][2]['graph_port'] == 6382
    assert calls[0][2]['graph_user'] == 'wf_ops'
    assert calls[0][2]['port'] == 8094
    assert calls[1] == ('serve', sentinel, {'host': '127.0.0.1', 'port': 8094})
    assert 'inspection' in result.output.lower()
    assert CliRunner().invoke(app, ['serve', '--host', '0.0.0.0']).exit_code != 0


def test_mission_command_is_explicit_loopback_composition(monkeypatch, tmp_path):
    import uvicorn

    from witness_fleet.api import mission
    calls = []
    sentinel = object()
    monkeypatch.setattr(mission, 'create_mission_app', lambda root, **kwargs:
                        calls.append(('compose', root, kwargs)) or sentinel)
    monkeypatch.setattr(uvicorn, 'run', lambda app, **kwargs:
                        calls.append(('serve', app, kwargs)))
    result = CliRunner().invoke(app, ['mission', '--run-dir', str(tmp_path),
        '--graph-port', '6383', '--port', '8095'])
    assert result.exit_code == 0, result.output
    assert calls[0][0:2] == ('compose', tmp_path)
    assert calls[1] == ('serve', sentinel, {'host': '127.0.0.1', 'port': 8095})
    assert 'explicit' in result.output.lower()

