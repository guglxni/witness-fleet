import httpx

from witness_fleet.domain import DispatchEvent, canonical_json_hash
from witness_fleet.simulation.client import SimulatorClient


def test_client_sends_explicit_typed_episode_dispatch_and_steps():
    received = []
    def respond(request):
        received.append((request.method, request.url.path, request.content))
        return httpx.Response(200, json={'status': 'ACCEPTED'})
    client = SimulatorClient('http://127.0.0.1:8091', client=httpx.Client(transport=httpx.MockTransport(respond)))
    client.create_episode('e1', 'SC-001', 3)
    payload = {'coordinator_epoch': 1}
    event = DispatchEvent(id='b1', sequence=1, coordinator_epoch=1, kind='EPOCH_BARRIER',
                          effective_world_tick=0, payload=payload, payload_hash=canonical_json_hash(payload))
    client.send_event(event)
    client.advance(3)
    assert [path for _, path, _ in received] == ['/episodes', '/events', '/advance']
    assert b'"episode_id":"e1"' in received[0][2]
    assert b'"ticks":3' in received[-1][2]
