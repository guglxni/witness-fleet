"""Client event lookup accepts only verified local journal identities."""

import httpx
import pytest

from witness_fleet.domain import canonical_json_hash
from witness_fleet.simulation.client import SimulatorClient


def _known_event(event_id):
    payload = {"nested": {"unicode": "λ", "spaced key": "%2F"}, "number": 1}
    return {
        "id": event_id,
        "sequence": 2,
        "payload_hash": canonical_json_hash(payload),
        "kind": "FENCE_INSTALL",
        "coordinator_epoch": 1,
        "effective_world_tick": 0,
        "payload": payload,
        "status": "RECEIVED",
    }


def _client(handler):
    return SimulatorClient(
        "http://127.0.0.1:8091",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_query_event_preserves_exact_identifier_and_original_identity():
    event_id = "evt/% snow-λ"
    event = _known_event(event_id)
    received = []

    def respond(request):
        received.append(request)
        return httpx.Response(200, json={"status": "KNOWN", "event": event})

    client = _client(respond)
    assert client.query_event(event_id) == {"status": "KNOWN", "event": event}
    assert len(received) == 1
    assert received[0].method == "GET"
    assert received[0].url.raw_path == b"/events/evt%2F%25%20snow-%CE%BB"


@pytest.mark.parametrize("kind", [[], {}, None, True, 1])
def test_query_event_rejects_non_string_kind_without_raising(kind):
    event = {**_known_event("evt-1"), "kind": kind}
    client = _client(lambda request: httpx.Response(200, json={"status": "KNOWN", "event": event}))
    assert client.query_event("evt-1") == {"status": "INVALID_RESPONSE"}


@pytest.mark.parametrize("status_code", [201, 202, 409, 503])
def test_query_event_rejects_known_identity_from_non_success_http_status(status_code):
    event = _known_event("evt-1")
    client = _client(lambda request: httpx.Response(status_code, json={"status": "KNOWN", "event": event}))
    assert client.query_event("evt-1") == {"status": "INVALID_RESPONSE"}


def test_query_event_returns_not_found_with_the_exact_requested_identifier():
    event_id = "missing/%雪"
    client = _client(lambda request: httpx.Response(404))
    assert client.query_event(event_id) == {"status": "NOT_FOUND", "event_id": event_id}


@pytest.mark.parametrize("error", [httpx.ReadTimeout, httpx.RemoteProtocolError])
def test_query_event_transport_uncertainty_remains_unknown(error):
    def dropped(request):
        raise error("response uncertain", request=request)

    assert _client(dropped).query_event("evt-1") == {"status": "UNKNOWN_TRANSPORT"}


def test_query_event_rejects_invalid_ids_before_transport():
    seen = []
    client = _client(lambda request: seen.append(request) or httpx.Response(200, json={}))
    for event_id in ("", None, 1, True):
        with pytest.raises(ValueError):
            client.query_event(event_id)
    assert seen == []


def test_query_event_fails_closed_on_mismatched_or_malformed_journal_identity():
    event_id = "evt-1"
    original = _known_event(event_id)
    invalid_events = [
        {**original, "id": "different-id"},
        {**original, "payload_hash": "wrong-hash"},
        {**original, "status": "NEVER_ADMITTED"},
        {**original, "status": []},
        {**original, "kind": "UNKNOWN_KIND"},
        {**original, "sequence": True},
        {key: value for key, value in original.items() if key != "payload"},
    ]
    for event in invalid_events:
        client = _client(lambda request, event=event: httpx.Response(200, json={"status": "KNOWN", "event": event}))
        assert client.query_event(event_id) == {"status": "INVALID_RESPONSE"}

    for envelope in ({"status": "KNOWN"}, {"status": "KNOWN", "event": original, "extra": True},
                     {"status": "NOT_FOUND", "event_id": "different-id"}):
        client = _client(lambda request, envelope=envelope: httpx.Response(200, json=envelope))
        assert client.query_event(event_id) == {"status": "INVALID_RESPONSE"}
