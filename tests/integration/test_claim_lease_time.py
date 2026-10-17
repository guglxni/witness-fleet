from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from witness_fleet.graph import GraphStore


class _OfflineGraph:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def query(self, cypher: str, params: dict[str, Any]) -> SimpleNamespace:
        self.calls.append((cypher, params))
        return SimpleNamespace(header=[], result_set=[])


def _store() -> tuple[GraphStore, _OfflineGraph]:
    graph = _OfflineGraph()
    store = GraphStore.__new__(GraphStore)
    store.tenant_id = "demo"
    store.__dict__["_graph"] = graph
    store.query_count = 0
    store.cas_query_count = 0
    return store, graph


def _claim(store: GraphStore, lease: str, now: str) -> dict[str, Any] | None:
    return store.claim_task(
        task_id="task", robot_id="robot", expected_task_version=0,
        coordinator_epoch=1, resource_ids=["resource"],
        lease_expires_at_utc=lease, now_utc=now,
    )


@pytest.mark.parametrize(
    ("lease", "now"),
    [
        ("2026-10-15T11:00:00Z", "2026-10-15T11:00:00.500000Z"),
        ("2026-10-15T11:00:00Z", "2026-10-15T11:00:00Z"),
        ("2026-10-15T11:00:00.500000Z", "2026-10-15T11:00:00.500000Z"),
        ("2026-10-15T11:00:00+00:00", "2026-10-15T11:00:00Z"),
    ],
)
def test_expired_or_equal_lease_does_not_query(
    lease: str, now: str,
) -> None:
    store, graph = _store()

    assert _claim(store, lease, now) is None
    assert graph.calls == []
    assert store.query_count == 0
    assert store.cas_query_count == 0


@pytest.mark.parametrize(
    ("lease", "now", "normalized_lease", "normalized_now"),
    [
        (
            "2026-10-15T11:00:00.500000Z", "2026-10-15T11:00:00Z",
            "2026-10-15T11:00:00.500000Z", "2026-10-15T11:00:00Z",
        ),
        (
            "2026-10-15T11:00:00+00:00", "2026-10-15T10:59:59.500000Z",
            "2026-10-15T11:00:00Z", "2026-10-15T10:59:59.500000Z",
        ),
    ],
)
def test_future_lease_reaches_query_with_normalized_stored_timestamps(
    lease: str, now: str, normalized_lease: str, normalized_now: str,
) -> None:
    store, graph = _store()

    assert _claim(store, lease, now) is None
    assert len(graph.calls) == 1
    assert graph.calls[0][1]["lease"] == normalized_lease
    assert graph.calls[0][1]["now"] == normalized_now
    assert store.query_count == 1
    assert store.cas_query_count == 1


@pytest.mark.parametrize(
    ("lease", "now"),
    [
        ("2026-10-15T11:00:00", "2026-10-15T10:00:00Z"),
        ("2026-10-15T11:00:00+01:00", "2026-10-15T10:00:00Z"),
        ("2026-10-15T12:00:00Z", "2026-10-15T11:00:00"),
        ("2026-10-15T12:00:00Z", "2026-10-15T11:00:00+01:00"),
    ],
)
def test_invalid_non_utc_timestamps_still_raise_without_query(
    lease: str, now: str,
) -> None:
    store, graph = _store()

    with pytest.raises(ValueError, match="timestamps must be explicit UTC ISO-8601"):
        _claim(store, lease, now)
    assert graph.calls == []
    assert store.query_count == 0
    assert store.cas_query_count == 0
