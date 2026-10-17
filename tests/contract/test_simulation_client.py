"""HTTP transport mocks verify adapter semantics, never physics acceptance."""
import httpx
import pytest

from witness_fleet.simulation.client import SimulatorClient


def test_http_timeout_is_unknown_transport_never_effect_failure():
    def timeout(request):
        raise httpx.ReadTimeout('response uncertain', request=request)
    client = SimulatorClient('http://127.0.0.1:8091', client=httpx.Client(transport=httpx.MockTransport(timeout)))
    result = client.health()
    assert result == {'status': 'UNKNOWN_TRANSPORT'}


def test_not_found_receipt_cannot_be_used_as_never_admitted_proof():
    client = SimulatorClient('http://127.0.0.1:8091', client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404))))
    assert client.query_receipt('c1') == {'status': 'NOT_FOUND', 'command_id': 'c1'}


def test_invalid_local_port_is_rejected_before_transport():
    for url in ('http://localhost:garbage', 'http://127.0.0.1:0', 'http://localhost:99999'):
        with pytest.raises(ValueError):
            SimulatorClient(url)


def test_only_loopback_http_endpoint_is_permitted():
    for url in ('http://example.com', 'https://127.0.0.1:8091', 'http://127.0.0.1:8091/private', 'http://user:pass@localhost:8091', 'file:///tmp/x'):
        with pytest.raises(ValueError):
            SimulatorClient(url)


def test_redirect_and_invalid_json_fail_closed():
    for response in (httpx.Response(302, headers={'location': 'http://evil.test'}), httpx.Response(200, text='invalid'), httpx.Response(200, json=[])):
        client = SimulatorClient('http://localhost:8091', client=httpx.Client(transport=httpx.MockTransport(lambda r, response=response: response)))
        assert client.health()['status'] == 'INVALID_RESPONSE'


def test_observations_are_returned_without_authority_enrichment():
    payload = {'world_tick': 4, 'observations': {'scout': {'gap': None}}}
    seen = []
    def handler(request):
        seen.append(request.url.path)
        return httpx.Response(200, json=payload)
    client = SimulatorClient('http://127.0.0.1:8091', client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert client.observations() == payload
    assert seen == ['/observations']
