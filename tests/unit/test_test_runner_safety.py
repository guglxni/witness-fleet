"""Regression coverage for full-suite preflight; all graph probes stay offline."""
from pathlib import Path

import scripts.test_all as test_all


def test_preflight_rejects_graph_constructors_using_defaults_or_retained_ports():
    source = """
from witness_fleet.graph import GraphStore as Store
legacy_default = Store()
legacy_retained = Store(port=6381)
legacy_positional = Store('127.0.0.1', 6380)
"""

    findings = test_all.find_unsafe_graph_constructors(source, "unsafe_test.py")

    assert len(findings) == 3
    assert all("unsafe_test.py:" in finding for finding in findings)
    assert all("GraphStore" in finding for finding in findings)


def test_preflight_allows_dynamic_isolated_port_and_offline_config_delete_probes():
    source = """
from witness_fleet.graph import GraphStore

def connect(isolated_runtime_graph):
    return GraphStore(host=isolated_runtime_graph.host,
                      port=isolated_runtime_graph.port, username='default')

def docker_fixture_connection():
    details = json.loads(subprocess.check_output(['docker', 'inspect', name]))[0]
    port = int(details['NetworkSettings']['Ports']['6379/tcp'][0]['HostPort'])
    return GraphStore(host='127.0.0.1', port=port, username='default')

# These are assertions / query recording, not live graph connections.
assert Settings().graph_port == 6380
store = GraphStore.__new__(GraphStore)
store._query = lambda cypher, params: recorded.append((cypher, params))
store.delete_test_records('offline-fixture')
"""

    assert test_all.find_unsafe_graph_constructors(source, "safe_test.py") == []


def test_suite_preflight_checks_both_interpreters_and_every_test_file(tmp_path):
    main_python = tmp_path / ".venv/bin/python"
    corpus_python = tmp_path / "services/corpus/.venv/bin/python"
    main_python.parent.mkdir(parents=True)
    corpus_python.parent.mkdir(parents=True)
    main_python.write_text("python")
    corpus_python.write_text("python")
    main_python.chmod(0o755)
    corpus_python.chmod(0o755)
    good = tmp_path / "tests/unit/test_good.py"
    bad = tmp_path / "tests/e2e/test_bad.py"
    good.parent.mkdir(parents=True)
    bad.parent.mkdir(parents=True)
    good.write_text("assert Settings().graph_port == 6380\n")
    bad.write_text("from witness_fleet.graph import GraphStore\nGraphStore(port=6381)\n")

    errors = test_all.preflight(
        tmp_path,
        [Path(".venv/bin/python"), Path("services/corpus/.venv/bin/python")],
        [Path("tests/unit/test_good.py"), Path("tests/e2e/test_bad.py")],
    )

    assert len(errors) == 1
    assert "tests/e2e/test_bad.py" in errors[0]
    assert "6381" in errors[0]
    assert main_python.exists() and corpus_python.exists()


def test_suite_preflight_refuses_missing_locked_interpreter_before_running(tmp_path):
    errors = test_all.preflight(
        tmp_path,
        [Path(".venv/bin/python"), Path("services/corpus/.venv/bin/python")],
        [],
    )

    assert any("services/corpus/.venv/bin/python" in error for error in errors)
