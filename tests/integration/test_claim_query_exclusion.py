import uuid

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

pytestmark = pytest.mark.integration


def test_same_task_resource_cannot_be_claimed_by_a_second_robot(isolated_console_graph):  # noqa: F811
    graph = isolated_console_graph
    ids = graph.seed_claim_fixture(uuid.uuid4().hex)
    root = graph.read_version_root()
    assert root is not None
    epoch = root['coordinator_epoch']
    args = dict(task_id=ids['task_id'], coordinator_epoch=epoch, resource_ids=ids['resource_ids'],
                lease_expires_at_utc='2026-10-16T12:00:00Z', now_utc='2026-10-16T11:00:00Z')
    first = graph.claim_task(**args, robot_id=ids['robot_0'], expected_task_version=0)
    assert first is not None
    assert graph.claim_task(**args, robot_id=ids['robot_1'], expected_task_version=1) is None
