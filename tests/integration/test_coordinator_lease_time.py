from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from typing import Any

import pytest

from witness_fleet.runtime.storage import TransitionStore

NOW = "2026-10-15T11:00:00Z"
EXPIRED = "2026-10-15T10:59:59Z"
LIVE_FRACTION = "2026-10-15T11:00:00.100000Z"
PROPOSED_FRACTION = "2026-10-15T11:00:00.100000Z"


class _OfflineGraph:
    tenant_id = "demo"

    def __init__(
        self,
        root: dict[str, Any] | None = None,
        *,
        interleave: dict[str, Any] | None = None,
    ) -> None:
        self.root = deepcopy(root if root is not None else {
            "graph_version": 5,
            "coordinator_epoch": 0,
            "coordinator_lease_expires_at_utc": EXPIRED,
        })
        self.missing_root = False
        self.interleave = interleave
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.query_count = 0
        self.cas_query_count = 0
        self._graph = self

    def read_version_root(self) -> dict[str, Any] | None:
        self.query_count += 1
        return None if self.missing_root else deepcopy(self.root)

    def query(self, cypher: str, params: dict[str, Any]) -> SimpleNamespace:
        self.calls.append((cypher, params))
        if self.interleave is not None:
            self.root.update(self.interleave)
        lease_matches = (
            self.root.get("coordinator_lease_expires_at_utc")
            == params.get("retained_lease")
        )
        if "coordinator_lease_expires_at_utc IS NULL" in cypher:
            lease_matches = self.root.get("coordinator_lease_expires_at_utc") is None
        cas_matches = (
            self.root.get("graph_version") == params.get("expected_version")
            and self.root.get("coordinator_epoch") == params.get("expected_epoch")
            and lease_matches
        )
        if not cas_matches:
            return SimpleNamespace(header=[], result_set=[])
        self.root.update({
            "coordinator_epoch": params["epoch"],
            "coordinator_holder_id": params["holder_id"],
            "coordinator_lease_expires_at_utc": params["expires"],
            "dispatch_sequence": self.root.get("dispatch_sequence", 0) + 1,
            "graph_version": params["expected_version"] + 1,
        })
        event = {
            "kind": "EPOCH_BARRIER",
            "sequence": self.root["dispatch_sequence"],
            "coordinator_epoch": params["epoch"],
            "payload_hash": params["payload_hash"],
            "payload_json": params["payload_json"],
            "effective_world_tick": params["tick"],
        }
        return SimpleNamespace(
            header=[[None, "state"], [None, "event"]],
            result_set=[[deepcopy(self.root), event]],
        )


def _acquire(
    graph: _OfflineGraph,
    *,
    now: str = NOW,
    expires: str = PROPOSED_FRACTION,
) -> dict[str, Any] | None:
    return TransitionStore(graph).acquire_coordinator(
        expected_epoch=0,
        holder_id="holder",
        now_utc=now,
        lease_expires_at_utc=expires,
        event_id="barrier",
        effective_world_tick=0,
    )


def test_proposed_fractional_expiry_after_whole_second_is_accepted() -> None:
    graph = _OfflineGraph()

    result = _acquire(graph)

    assert result is not None
    assert result["coordinator_lease_expires_at_utc"] == PROPOSED_FRACTION
    assert result["coordinator_epoch"] == 1
    assert result["graph_version"] == 6
    assert result["dispatch_sequence"] == 1
    assert result["event"]["kind"] == "EPOCH_BARRIER"
    assert result["event"]["sequence"] == 1
    assert len(graph.calls) == 1
    assert graph.calls[0][1]["expires"] == PROPOSED_FRACTION
    assert graph.query_count == 2
    assert graph.cas_query_count == 1


def test_live_fractional_retained_lease_after_whole_second_blocks_cas() -> None:
    graph = _OfflineGraph({
        "graph_version": 5,
        "coordinator_epoch": 0,
        "coordinator_lease_expires_at_utc": LIVE_FRACTION,
    })

    assert _acquire(graph) is None

    assert graph.calls == []
    assert graph.query_count == 1
    assert graph.cas_query_count == 0


@pytest.mark.parametrize(
    ("retained", "now"),
    [
        (EXPIRED, "2026-10-15T11:00:00Z"),
        ("2026-10-15T11:00:00Z", "2026-10-15T11:00:00Z"),
    ],
)
def test_expired_or_equal_retained_lease_attempts_one_exact_cas(
    retained: str, now: str,
) -> None:
    graph = _OfflineGraph({
        "graph_version": 5,
        "coordinator_epoch": 0,
        "coordinator_lease_expires_at_utc": retained,
    })

    result = _acquire(
        graph,
        now=now,
        expires="2026-10-15T11:00:01Z",
    )

    assert result is not None
    assert result["coordinator_epoch"] == 1
    assert result["graph_version"] == 6
    assert result["dispatch_sequence"] == 1
    assert result["event"]["kind"] == "EPOCH_BARRIER"
    assert len(graph.calls) == 1
    cypher, params = graph.calls[0]
    assert "s.graph_version=$expected_version" in cypher
    assert "s.coordinator_epoch=$expected_epoch" in cypher
    assert "s.coordinator_lease_expires_at_utc=$retained_lease" in cypher
    assert params["expected_version"] == 5
    assert params["expected_epoch"] == 0
    assert params["retained_lease"] == retained
    assert params["expires"] == "2026-10-15T11:00:01Z"
    assert "<=$now" not in cypher
    assert "<$now" not in cypher
    assert graph.query_count == 2
    assert graph.cas_query_count == 1


@pytest.mark.parametrize("lease", [None, "missing"])
def test_absent_or_null_retained_lease_uses_null_cas_guard(lease: str | None) -> None:
    root: dict[str, Any] = {"graph_version": 5, "coordinator_epoch": 0}
    if lease != "missing":
        root["coordinator_lease_expires_at_utc"] = lease
    graph = _OfflineGraph(root)

    result = _acquire(graph)

    assert result is not None
    assert result["coordinator_epoch"] == 1
    assert result["graph_version"] == 6
    assert result["event"]["sequence"] == 1
    assert len(graph.calls) == 1
    cypher, params = graph.calls[0]
    assert "s.coordinator_lease_expires_at_utc IS NULL" in cypher
    assert "retained_lease" not in params
    assert graph.query_count == 2
    assert graph.cas_query_count == 1


@pytest.mark.parametrize("lease", ["not-a-timestamp", "2026-10-15T11:00:00+01:00", 7])
def test_malformed_or_non_utc_retained_lease_fails_closed(lease: Any) -> None:
    graph = _OfflineGraph({
        "graph_version": 5,
        "coordinator_epoch": 0,
        "coordinator_lease_expires_at_utc": lease,
    })

    assert _acquire(graph) is None

    assert graph.calls == []
    assert graph.query_count == 1
    assert graph.cas_query_count == 0


@pytest.mark.parametrize(
    "root",
    [
        None,
        {"graph_version": True, "coordinator_epoch": 0},
        {"graph_version": 5.0, "coordinator_epoch": 0},
        {"graph_version": 5, "coordinator_epoch": True},
        {"graph_version": 5, "coordinator_epoch": -1},
        {"coordinator_epoch": 0},
    ],
)
def test_missing_or_invalid_version_root_fails_closed(root: dict[str, Any] | None) -> None:
    graph = _OfflineGraph(root)
    if root is None:
        graph.missing_root = True

    assert _acquire(graph) is None

    assert graph.calls == []
    assert graph.query_count == 1
    assert graph.cas_query_count == 0


@pytest.mark.parametrize(
    "interleave",
    [
        {"graph_version": 6},
        {"coordinator_epoch": 1},
        {"coordinator_lease_expires_at_utc": "2026-10-15T10:59:59+00:00"},
        {"coordinator_lease_expires_at_utc": None},
        {"coordinator_lease_expires_at_utc": "2026-10-15T10:59:59.000000Z"},
    ],
)
def test_cas_loses_if_version_epoch_or_exact_lease_changes_after_read(
    interleave: dict[str, Any],
) -> None:
    graph = _OfflineGraph(interleave=interleave)

    assert _acquire(graph) is None

    assert len(graph.calls) == 1
    cypher, params = graph.calls[0]
    assert "s.graph_version=$expected_version" in cypher
    assert "s.coordinator_epoch=$expected_epoch" in cypher
    assert "s.coordinator_lease_expires_at_utc=$retained_lease" in cypher
    assert params["expected_version"] == 5
    assert params["expected_epoch"] == 0
    assert params["retained_lease"] == EXPIRED
    assert graph.query_count == 2
    assert graph.cas_query_count == 1
