"""A losing gateway cannot mutate the running owner's session ledger."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from witness_fleet.hosting import create_hosted_app

ORIGIN = 'https://demo.example.test'


def test_second_gateway_does_not_invalidate_active_ledger(tmp_path):
    first = create_hosted_app(tmp_path, origin=ORIGIN)
    with TestClient(first, base_url=ORIGIN):
        db_path = tmp_path / 'hosted-sessions.sqlite3'
        with sqlite3.connect(db_path) as db:
            db.execute('INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?)',
                       ('retained-test', 'hash', 'csrf', 'active', 0, 99999999999, 'key', None))
        with pytest.raises(RuntimeError, match='locked'):
            create_hosted_app(tmp_path, origin=ORIGIN)
        with sqlite3.connect(db_path) as db:
            assert db.execute('SELECT status FROM sessions WHERE sid=?', ('retained-test',)).fetchone()[0] == 'active'
