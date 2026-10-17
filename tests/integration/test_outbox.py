from __future__ import annotations

import uuid

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from witness_fleet.domain import canonical_json_hash
from witness_fleet.runtime.storage import TransitionStore

pytestmark = pytest.mark.integration


@pytest.fixture
def transitions(isolated_console_graph) -> TransitionStore:  # noqa: F811
    graph = isolated_console_graph
    return TransitionStore(graph)


def control_event(kind: str = "REVOCATION") -> dict:
    payload = {"reason": "test", "subject": f"it-{uuid.uuid4().hex}"}
    return {
        "id": f"it-control-{uuid.uuid4().hex}",
        "kind": kind,
        "payload": payload,
        "payload_hash": canonical_json_hash(payload),
        "subject_ids": [payload["subject"]],
        "effective_world_tick": 7,
    }


def test_control_events_share_one_ordered_durable_outbox(transitions: TransitionStore) -> None:
    root = transitions.graph.read_version_root()
    assert root is not None
    expected = root["graph_version"]
    first = transitions.append_control_event(event=control_event(), expected_graph_version=expected)
    second = transitions.append_control_event(
        event=control_event("FENCE_INSTALL"), expected_graph_version=first["graph_version"],
    )
    assert second["sequence"] == first["sequence"] + 1
    assert second["graph_version"] == first["graph_version"] + 1
    assert second["sequence"] == second["dispatch_sequence"]
    assert second["payload_json"]
    rows = transitions.read_outbox(after_sequence=first["sequence"] - 1)
    assert [row["sequence"] for row in rows] == [first["sequence"], second["sequence"]]
    assert rows[0]["payload_hash"] == canonical_json_hash(rows[0]["payload"])
    assert rows[1]["payload_hash"] == canonical_json_hash(rows[1]["payload"])


def test_control_event_rejects_stale_graph_version_without_advancing_sequence(
    transitions: TransitionStore,
) -> None:
    root = transitions.graph.read_version_root()
    assert root is not None
    first = transitions.append_control_event(event=control_event(), expected_graph_version=root["graph_version"])
    stale = transitions.append_control_event(event=control_event(), expected_graph_version=root["graph_version"])
    assert stale is None
    after = transitions.graph.read_version_root()
    assert after is not None
    assert after["dispatch_sequence"] == first["sequence"]
