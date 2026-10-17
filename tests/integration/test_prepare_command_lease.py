"""Server-time UTC lease boundary for the new-command CAS path."""

from datetime import UTC, datetime

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401
from test_command_preparation import prepared_fixture

pytestmark = pytest.mark.integration


def _epoch_milliseconds(value: str) -> int:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    delta = parsed - datetime(1970, 1, 1, tzinfo=UTC)
    return delta.days * 86_400_000 + delta.seconds * 1_000 + delta.microseconds // 1_000


def test_new_command_cas_uses_server_time_against_utc_claim_lease(
    isolated_console_graph, monkeypatch,  # noqa: F811
):
    graph, transitions, command, authorization, expected = prepared_fixture(isolated_console_graph)
    before = graph.read_version_root()
    claim_lease = graph.get_node("Claim", command.claim_id)["lease_expires_at_utc"]
    original_query = graph._graph.query
    captured = []

    def expire_lease_at_cas(query, params=None, **kwargs):
        if "CREATE (c:Command" in query:
            assert "timestamp()<$deadline_ms" in query
            assert "cl.lease_expires_at_utc=$claim_lease" in query
            assert "cl.lease_expires_at_utc>$now" not in query
            captured.append((params["deadline_ms"], params["claim_lease"]))
            # Force expiry at the engine boundary while executing the actual CAS.
            params = {**params, "deadline_ms": 0}
        return original_query(query, params, **kwargs)

    monkeypatch.setattr(graph._graph, "query", expire_lease_at_cas)
    result = transitions.prepare_command(
        command=command, authorization=authorization,
        expected_graph_version=expected,
    )

    assert result is None
    assert captured == [(_epoch_milliseconds(claim_lease), claim_lease)]
    assert graph.read_version_root() == before
    assert transitions.get_command(command.command_id) is None
