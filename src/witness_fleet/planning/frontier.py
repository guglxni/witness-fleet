"""Deterministic DAG validation and task frontier calculation."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from witness_fleet.domain import VersionVector


@dataclass(frozen=True)
class FrontierResult:
    task_ids: tuple[str, ...]
    blocked_reasons: Mapping[str, tuple[str, ...]]
    topological_order: tuple[str, ...]


def _fact_current(fact: Mapping[str, Any], observations: Mapping[str, Any], now_tick: int | None) -> bool:
    if fact.get("status") != "verified" or fact.get("kind") in {"hypothesis", "predicted_effect"}:
        return False
    ids = fact.get("observation_ids", ())
    if not ids:
        return False
    for observation_id in ids:
        obs = observations.get(observation_id)
        if obs is None:
            return False
        if isinstance(obs, Mapping):
            expiry = obs.get("expires_tick")
            world_tick = obs.get("world_tick")
        else:
            expiry = getattr(obs, "expires_tick", None)
            world_tick = getattr(obs, "world_tick", None)
        if expiry is None or world_tick is None or (now_tick is not None and (now_tick >= expiry or world_tick > now_tick)):
            return False
    return True


def ready_tasks(
    tasks: Sequence[Mapping[str, Any]],
    *,
    facts: Sequence[Mapping[str, Any]] = (),
    observations: Mapping[str, Any] | None = None,
    now_tick: int | None = None,
    truncated: bool = False,
    expected_versions: VersionVector | None = None,
) -> FrontierResult:
    """Return pending tasks whose prerequisites are verified and required facts current.

    Edge direction is task -> prerequisite (`depends_on`). Any cyclic or dangling
    dependency invalidates the snapshot rather than yielding a partial frontier.
    When `expected_versions` is supplied, every task and required fact must carry
    the exact corresponding version in its dependency_versions map; missing or
    changed versions block that task. Callers evaluating a live snapshot should
    always provide this vector. Omission retains compatibility for offline callers.
    """
    if truncated:
        raise ValueError("truncated task snapshot cannot produce a complete frontier")
    by_id: dict[str, Mapping[str, Any]] = {}
    for task in tasks:
        identifier = task.get("id")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("task IDs must be non-empty strings")
        if identifier in by_id:
            raise ValueError(f"duplicate task ID: {identifier}")
        by_id[identifier] = task
    dependencies: dict[str, tuple[str, ...]] = {}
    dependents: dict[str, list[str]] = defaultdict(list)
    indegree: dict[str, int] = {}
    for identifier, task in by_id.items():
        deps = tuple(sorted(set(task.get("depends_on", task.get("dependencies", ())))))
        unknown = sorted(set(deps) - by_id.keys())
        if unknown:
            raise ValueError(f"unknown dependency for {identifier}: {unknown[0]}")
        dependencies[identifier] = deps
        indegree[identifier] = len(deps)
        for dependency in deps:
            dependents[dependency].append(identifier)
    ready = deque(sorted(identifier for identifier, count in indegree.items() if count == 0))
    ordered: list[str] = []
    while ready:
        current = ready.popleft()
        ordered.append(current)
        for dependent in sorted(dependents[current]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
    if len(ordered) != len(by_id):
        raise ValueError("task dependency cycle detected")

    fact_by_id: dict[str, Mapping[str, Any]] = {}
    for fact in facts:
        fact_id = fact.get("id")
        if not isinstance(fact_id, str):
            continue
        if fact_id in fact_by_id:
            raise ValueError(f"duplicate fact ID: {fact_id}")
        fact_by_id[fact_id] = fact
    stale_task_versions: set[str] = set()
    if expected_versions is not None:
        for identifier, task in by_id.items():
            expected_task_version = expected_versions.dependency_versions.get(identifier)
            if (expected_task_version is None
                    or task.get("task_version") != expected_task_version):
                stale_task_versions.add(identifier)

    def has_stale_task_ancestry(identifier: str) -> bool:
        """A stale prerequisite invalidates descendants relying on that snapshot."""
        pending = list(dependencies[identifier])
        visited: set[str] = set()
        while pending:
            dependency = pending.pop()
            if dependency in visited:
                continue
            visited.add(dependency)
            if dependency in stale_task_versions:
                return True
            pending.extend(dependencies[dependency])
        return False

    observation_map = observations or {}
    frontier: list[str] = []
    blocked: dict[str, tuple[str, ...]] = {}
    terminal = {"verified", "completed", "failed", "cancelled", "terminal"}
    for identifier in sorted(by_id):
        task = by_id[identifier]
        state = str(task.get("state", "pending")).lower()
        if state in terminal:
            continue
        reasons: set[str] = set()
        if expected_versions is not None:
            expected_task_version = expected_versions.dependency_versions.get(identifier)
            if (expected_task_version is None
                    or task.get("task_version") != expected_task_version
                    or has_stale_task_ancestry(identifier)):
                reasons.add("SNAPSHOT_VERSION_MISMATCH")
        for dependency in dependencies[identifier]:
            prerequisite_state = str(by_id[dependency].get("state", "pending")).lower()
            if prerequisite_state != "verified":
                reasons.add("DEPENDENCY_NOT_VERIFIED")
        for fact_id in task.get("required_facts", ()):
            fact = fact_by_id.get(fact_id)
            if fact is None:
                reasons.add("MISSING_FACT")
            elif not _fact_current(fact, observation_map, now_tick):
                reasons.add("STALE_FACT")
            if expected_versions is not None and fact is not None:
                expected_fact_version = expected_versions.dependency_versions.get(fact_id)
                if (expected_fact_version is None
                        or fact.get("derivation_version") != expected_fact_version):
                    reasons.add("SNAPSHOT_VERSION_MISMATCH")
        if reasons:
            blocked[identifier] = tuple(sorted(reasons))
        elif state in {"pending", "ready"}:
            frontier.append(identifier)
        else:
            blocked[identifier] = ("TASK_NOT_PENDING",)
    return FrontierResult(tuple(frontier), blocked, tuple(ordered))
