import pytest

from witness_fleet.domain import VersionVector
from witness_fleet.planning.frontier import ready_tasks


def test_frontier_needs_all_prerequisite_tasks_outcome_verified():
    tasks = [
        {"id": "inspect", "state": "pending", "depends_on": []},
        {"id": "recover", "state": "pending", "depends_on": ["inspect"]},
        {"id": "deliver", "state": "pending", "depends_on": ["recover"]},
    ]
    assert ready_tasks(tasks).task_ids == ("inspect",)
    tasks[0]["state"] = "verified"
    assert ready_tasks(tasks).task_ids == ("recover",)
    tasks[1]["state"] = "unknown"
    assert ready_tasks(tasks).task_ids == ()


def test_frontier_rejects_cycles_and_unknown_dependencies():
    with pytest.raises(ValueError, match="cycle"):
        ready_tasks([{"id": "a", "depends_on": ["b"]}, {"id": "b", "depends_on": ["a"]}])
    with pytest.raises(ValueError, match="unknown dependency"):
        ready_tasks([{"id": "a", "depends_on": ["missing"]}])


def test_required_facts_must_be_current_and_stale_facts_invalidate_frontier():
    tasks = [{"id": "move", "depends_on": [], "required_facts": ["clear"]}]
    facts = [{"id": "clear", "status": "verified", "observation_ids": ["o1"]}]
    result = ready_tasks(tasks, facts=facts, observations={"o1": {"world_tick": 2, "expires_tick": 9}},
                         now_tick=4)
    assert result.task_ids == ("move",)
    stale = ready_tasks(tasks, facts=facts,
        observations={"o1": {"world_tick": 2, "expires_tick": 4}}, now_tick=4)
    assert stale.task_ids == ()
    assert "STALE_FACT" in stale.blocked_reasons["move"]


def test_hold_pending_unknown_and_hypothesis_states_never_complete_dependencies():
    tasks = [{"id": "observe", "state": "hold", "depends_on": []},
             {"id": "deliver", "state": "pending", "depends_on": ["observe"]}]
    assert ready_tasks(tasks).task_ids == ()


def test_expected_snapshot_versions_block_tasks_with_mismatched_task_version():
    tasks = [{"id": "move", "state": "pending", "depends_on": [], "task_version": 4}]
    expected = VersionVector(graph_version=8, policy_epoch=2, coordinator_epoch=1,
                             dependency_versions={"move": 3})
    result = ready_tasks(tasks, expected_versions=expected)
    assert result.task_ids == ()
    assert "SNAPSHOT_VERSION_MISMATCH" in result.blocked_reasons["move"]


def test_expected_snapshot_versions_block_tasks_with_mismatched_fact_version():
    tasks = [{"id": "move", "state": "pending", "depends_on": [], "required_facts": ["clear"],
              "task_version": 4}]
    facts = [{"id": "clear", "status": "verified", "observation_ids": ["o1"], "derivation_version": 6}]
    expected = VersionVector(graph_version=8, policy_epoch=2, coordinator_epoch=1,
                             dependency_versions={"move": 4, "clear": 5})
    result = ready_tasks(tasks, facts=facts,
                         observations={"o1": {"world_tick": 2, "expires_tick": 9}},
                         now_tick=4, expected_versions=expected)
    assert result.task_ids == ()
    assert "SNAPSHOT_VERSION_MISMATCH" in result.blocked_reasons["move"]


def test_expected_snapshot_versions_allow_matching_task_and_fact_versions():
    tasks = [{"id": "move", "state": "pending", "depends_on": [], "required_facts": ["clear"],
              "task_version": 4}]
    facts = [{"id": "clear", "status": "verified", "observation_ids": ["o1"], "derivation_version": 6}]
    expected = VersionVector(graph_version=8, policy_epoch=2, coordinator_epoch=1,
                             dependency_versions={"move": 4, "clear": 6})
    result = ready_tasks(tasks, facts=facts,
                         observations={"o1": {"world_tick": 2, "expires_tick": 9}},
                         now_tick=4, expected_versions=expected)
    assert result.task_ids == ("move",)


def test_mismatched_verified_dependency_version_blocks_dependent_task():
    tasks = [{"id": "inspect", "state": "verified", "depends_on": [], "task_version": 5},
             {"id": "move", "state": "pending", "depends_on": ["inspect"], "task_version": 4}]
    expected = VersionVector(graph_version=8, policy_epoch=2, coordinator_epoch=1,
                             dependency_versions={"inspect": 4, "move": 4})
    result = ready_tasks(tasks, expected_versions=expected)
    assert result.task_ids == ()
    assert "SNAPSHOT_VERSION_MISMATCH" in result.blocked_reasons["move"]
