"""Host CLI defaults and environment configuration are explicit."""
from witness_fleet.hosting.__main__ import main


def test_cli_defaults_are_private_and_environment_is_used(monkeypatch):
    seen = {}
    monkeypatch.setenv("WITNESS_DEMO_ORIGIN", "https://configured.example.test")
    monkeypatch.setenv("WITNESS_REVISION", "rev-test")
    monkeypatch.setenv("WITNESS_DATA_DIR", "/tmp/hosted-test-data")
    monkeypatch.setenv("WITNESS_GRAPH_PORT", "6388")

    def create(root, **kwargs):
        seen["root"] = root
        seen.update(kwargs)
        return object()

    def run(app, **kwargs):
        seen["uvicorn"] = kwargs

    import witness_fleet.hosting.__main__ as cli
    monkeypatch.setattr(cli, "create_hosted_app", create)
    monkeypatch.setattr(cli.uvicorn, "run", run)
    main([])
    assert seen["root"] == "/tmp/hosted-test-data"
    assert seen["origin"] == "https://configured.example.test"
    assert seen["revision"] == "rev-test"
    assert seen["graph_port"] == 6388
    assert seen["uvicorn"]["host"] == "127.0.0.1"
    assert seen["uvicorn"]["port"] == 8080
    assert seen["uvicorn"]["forwarded_allow_ips"] == "127.0.0.1"
