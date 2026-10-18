"""ACL fixture retries startup errors from client construction too."""
from types import SimpleNamespace

import isolated_acl_fixture as fixture
import pytest
from redis.exceptions import ConnectionError


def test_acl_fixture_retries_connect_before_initialize(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    attempts = []
    def connect(**kwargs):
        attempts.append(kwargs)
        if len(attempts) == 1:
            raise ConnectionError('server starting')
        return SimpleNamespace(initialize=lambda: None)
    monkeypatch.setattr(fixture, 'GraphStore', connect)
    calls = []
    monkeypatch.setattr(fixture.subprocess, 'run', lambda command, **kw: calls.append(command))
    monkeypatch.setattr(fixture.subprocess, 'check_output', lambda *a, **kw:
        '[{"NetworkSettings":{"Ports":{"6379/tcp":[{"HostPort":"65001"}]}}}]')
    monkeypatch.setattr(fixture.time, 'sleep', lambda _: None)
    generator = fixture.isolated_acl_server.__wrapped__()
    assert next(generator).port == 65001
    assert len(attempts) == 2
    with pytest.raises(StopIteration):
        next(generator)
    assert all('rm' not in command and 'prune' not in command for command in calls)
