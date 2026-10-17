from witness_fleet.planning.assignment import assign


def pair(task, robot, cost, *, capable=True, route_safe=True, policy_allowed=True, resources=()):
    return {"task_id": task, "robot_id": robot, "cost": cost, "capable": capable,
            "route_safe": route_safe, "policy_allowed": policy_allowed, "resource_ids": resources}


def test_assignment_minimizes_cost_with_unique_robots_and_tasks():
    result = assign([pair("a", "r1", 1), pair("a", "r2", 2), pair("b", "r1", 1.1),
                     pair("b", "r2", 9)])
    assert result.pairs == (("a", "r2"), ("b", "r1"))
    assert result.total_cost == 3.1
    assert result.unassigned_task_ids == ()


def test_infeasible_capability_route_and_policy_pairs_are_excluded():
    result = assign([pair("a", "r1", 0, capable=False), pair("b", "r1", 0, route_safe=False),
                     pair("c", "r1", 0, policy_allowed=False)])
    assert result.pairs == ()
    assert result.unassigned_task_ids == ("a", "b", "c")


def test_empty_matching_is_valid_and_does_not_force_fallback():
    assert assign([], task_ids=("task",)).unassigned_task_ids == ("task",)


def test_assignment_is_stable_under_input_permutation_and_respects_resources():
    candidates = [pair("a", "r2", 1), pair("a", "r1", 1), pair("b", "r1", 1),
                  pair("b", "r2", 1)]
    assert assign(candidates).pairs == assign(reversed(candidates)).pairs
    shared = [pair("a", "r1", 1, resources=("lift",)), pair("b", "r2", 1, resources=("lift",))]
    assert len(assign(shared).pairs) == 1
