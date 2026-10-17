import uuid

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

pytestmark = pytest.mark.integration


def test_claim_cannot_omit_a_canonically_required_resource(isolated_console_graph):  # noqa: F811
    store = isolated_console_graph
    ids = store.seed_claim_fixture(uuid.uuid4().hex)
    root = store.read_version_root()
    assert root is not None
    epoch = root['coordinator_epoch']
    answer = store.claim_task(task_id=ids['task_id'], robot_id=ids['robot_0'],
                              expected_task_version=0, coordinator_epoch=epoch,
                              resource_ids=[ids['resource_ids'][0]],
                              lease_expires_at_utc='2026-10-16T12:00:00Z',
                              now_utc='2026-10-16T11:00:00Z')
    assert answer is None
    assert store.read_task_claims(ids['task_id']) == []
