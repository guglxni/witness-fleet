"""Regression for a transient connection failure during client construction."""
from types import SimpleNamespace

import isolated_runtime_fixture as fixture
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError


def test_fixture_retries_constructor_before_graph_initialization(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    attempts = []
    initialized = []
    graph = SimpleNamespace(initialize=lambda: initialized.append(True))

    def connect(**kwargs):
        attempts.append(kwargs)
        if len(attempts) == 1:
            raise RedisConnectionError("server is starting")
        return graph

    monkeypatch.setattr(fixture, "GraphStore", connect)
    commands = []
    monkeypatch.setattr(fixture.subprocess, "run", lambda command, **kw: commands.append(command))
    monkeypatch.setattr(fixture.subprocess, "check_output", lambda *a, **kw:
        '[{"NetworkSettings":{"Ports":{"6379/tcp":[{"HostPort":"65001"}]}}}]')
    monkeypatch.setattr(fixture.time, "sleep", lambda _: None)
    generator = fixture.isolated_runtime_graph.__wrapped__()
    assert next(generator) is graph
    assert len(attempts) == 2
    assert initialized == [True]
    with pytest.raises(StopIteration):
        next(generator)
    assert any(command[:3] == ['docker', 'stop', '--timeout'] for command in commands)
    assert all('rm' not in command and 'prune' not in command for command in commands)
