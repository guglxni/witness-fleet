"""Feasible deterministic minimum-cost assignment; infeasible edges are excluded."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Any


@dataclass(frozen=True)
class Assignment:
    pairs: tuple[tuple[str, str], ...]
    total_cost: float
    unassigned_task_ids: tuple[str, ...]
    rejected: Mapping[tuple[str, str], tuple[str, ...]]


def _get(pair: Any, key: str, default: Any = None) -> Any:
    if isinstance(pair, Mapping):
        if key in pair:
            return pair[key]
        aliases = {"resource_ids": ("resources", "required_resource_ids"), "cost": ("assignment_cost",)}
        for alias in aliases.get(key, ()):
            if alias in pair:
                return pair[alias]
        return default
    return getattr(pair, key, default)


def assign(eligible_pairs: Iterable[Any], *, task_ids: Iterable[str] | None = None,
           resource_conflicts: Iterable[Iterable[str]] = ()) -> Assignment:
    """Max-cardinality minimum-cost deterministic assignment under resource conflicts.

    Mapping/object candidates expose task_id, robot_id, cost, optional capable,
    route_safe, policy_allowed, and resource_ids (also `resources` or
    `required_resource_ids`). Shared resource IDs are exclusive by default.
    """
    candidates = list(eligible_pairs)
    tasks = set(task_ids or ())
    pair_costs: dict[tuple[str, str], tuple[float, frozenset[str]]] = {}
    rejected: dict[tuple[str, str], tuple[str, ...]] = {}
    for item in candidates:
        task, robot = _get(item, "task_id"), _get(item, "robot_id")
        if not isinstance(task, str) or not task or not isinstance(robot, str) or not robot:
            raise ValueError("assignment pair task_id and robot_id must be non-empty strings")
        tasks.add(task)
        reasons: set[str] = set()
        for field, code in (("capable", "INCAPABLE"), ("route_safe", "UNSAFE_ROUTE"),
                            ("policy_allowed", "POLICY_DENIED")):
            if _get(item, field, True) is not True:
                reasons.add(code)
        cost = _get(item, "cost")
        if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not isfinite(float(cost)):
            reasons.add("INVALID_COST")
        resources = tuple(_get(item, "resource_ids", ()) or ())
        if any(not isinstance(resource, str) or not resource for resource in resources):
            reasons.add("INVALID_RESOURCE")
        key = (task, robot)
        if reasons:
            rejected[key] = tuple(sorted(reasons))
            continue
        normalized = float(cost), frozenset(resources)
        if key not in pair_costs or normalized[0] < pair_costs[key][0]:
            pair_costs[key] = normalized

    conflict_groups = tuple(frozenset(group) for group in resource_conflicts)
    if any(len(group) < 2 for group in conflict_groups):
        raise ValueError("each resource conflict group must contain at least two IDs")
    task_list = sorted(tasks)
    options: dict[str, list[tuple[str, float, frozenset[str]]]] = {task: [] for task in task_list}
    for (task, robot), (cost, resources) in sorted(pair_costs.items()):
        options[task].append((robot, cost, resources))
    for task in task_list:
        options[task].sort(key=lambda row: (row[1], row[0]))

    best: tuple[tuple[str, str], ...] = ()
    best_cost = 0.0
    best_count = -1
    selected: list[tuple[str, str]] = []
    used_robots: set[str] = set()
    used_resources: set[str] = set()

    def conflicts(resources: frozenset[str]) -> bool:
        if resources & used_resources:
            return True
        return any(resources & group and used_resources & group for group in conflict_groups)

    def visit(index: int, total: float) -> None:
        nonlocal best, best_cost, best_count
        if len(selected) + len(task_list) - index < best_count:
            return
        if index == len(task_list):
            pairs = tuple(sorted(selected))
            count = len(pairs)
            if count > best_count or (count == best_count and
                    (total < best_cost or (total == best_cost and pairs < best))):
                best, best_cost, best_count = pairs, total, count
            return
        task = task_list[index]
        for robot, cost, resources in options[task]:
            if robot in used_robots or conflicts(resources):
                continue
            used_robots.add(robot)
            used_resources.update(resources)
            selected.append((task, robot))
            visit(index + 1, total + cost)
            selected.pop()
            used_robots.remove(robot)
            used_resources.difference_update(resources)
        visit(index + 1, total)

    visit(0, 0.0)
    matched = {task for task, _ in best}
    return Assignment(best, best_cost, tuple(task for task in task_list if task not in matched), rejected)
