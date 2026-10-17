from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from witness_fleet.domain import canonical_json_hash
from witness_fleet.graph import GraphStore
from witness_fleet.runtime.storage import TransitionStore

pytestmark = pytest.mark.integration


@pytest.fixture
def store(isolated_console_graph) -> GraphStore:  # noqa: F811
    return isolated_console_graph


def _after_current_lease(root: dict) -> datetime:
    lease_expiry = root.get("coordinator_lease_expires_at_utc")
    if not lease_expiry:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(lease_expiry.replace("Z", "+00:00"))
    return parsed + timedelta(seconds=1)


def _utc_text(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def test_coordinator_epoch_is_acquired_by_one_compare_and_swap_only(store: GraphStore) -> None:
    transitions = TransitionStore(store)
    expected = store.read_version_root()
    assert expected is not None
    now = _utc_text(_after_current_lease(expected))
    lease_until = _utc_text(datetime.fromisoformat(now.replace("Z", "+00:00")) + timedelta(hours=1))
    first_id = f"it-barrier-{uuid.uuid4().hex}"
    first = transitions.acquire_coordinator(
        expected_epoch=expected["coordinator_epoch"], holder_id=f"it-holder-{uuid.uuid4().hex}",
        now_utc=now, lease_expires_at_utc=lease_until, event_id=first_id,
        effective_world_tick=42,
    )
    assert first is not None
    assert first["coordinator_epoch"] == expected["coordinator_epoch"] + 1
    assert first["graph_version"] == expected["graph_version"] + 1
    assert first["dispatch_sequence"] == expected["dispatch_sequence"] + 1
    assert first["event"]["kind"] == "EPOCH_BARRIER"
    assert first["event"]["sequence"] == first["dispatch_sequence"]
    payload = json.loads(first["event"]["payload_json"])
    assert first["event"]["payload_hash"] == canonical_json_hash(payload)
    assert payload["coordinator_epoch"] == first["coordinator_epoch"]
    assert first["coordinator_holder_id"]
    assert first["coordinator_lease_expires_at_utc"] == lease_until

    loser = transitions.acquire_coordinator(
        expected_epoch=expected["coordinator_epoch"], holder_id=f"it-holder-{uuid.uuid4().hex}",
        now_utc=now, lease_expires_at_utc=lease_until,
        event_id=f"it-barrier-{uuid.uuid4().hex}", effective_world_tick=43,
    )
    assert loser is None
    after = store.read_version_root()
    assert after is not None
    assert after["coordinator_epoch"] == first["coordinator_epoch"]
    assert after["dispatch_sequence"] == first["dispatch_sequence"]


def test_live_coordinator_lease_cannot_be_stolen_with_same_epoch(store: GraphStore) -> None:
    transitions = TransitionStore(store)
    root = store.read_version_root()
    assert root is not None
    now = _after_current_lease(root)
    now_utc = _utc_text(now)
    acquired = transitions.acquire_coordinator(
        expected_epoch=root["coordinator_epoch"], holder_id=f"it-holder-{uuid.uuid4().hex}",
        now_utc=now_utc, lease_expires_at_utc=_utc_text(now + timedelta(minutes=5)),
        event_id=f"it-barrier-{uuid.uuid4().hex}", effective_world_tick=1,
    )
    assert acquired is not None
    stolen = transitions.acquire_coordinator(
        expected_epoch=root["coordinator_epoch"], holder_id=f"it-holder-{uuid.uuid4().hex}",
        now_utc=now_utc, lease_expires_at_utc=_utc_text(now + timedelta(minutes=8)),
        event_id=f"it-barrier-{uuid.uuid4().hex}", effective_world_tick=2,
    )
    assert stolen is None
    current = store.read_version_root()
    assert current["coordinator_epoch"] == acquired["coordinator_epoch"]
    assert current["dispatch_sequence"] == acquired["dispatch_sequence"]
