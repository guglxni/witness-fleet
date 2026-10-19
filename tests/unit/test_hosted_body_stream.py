"""Body limiting must preserve disconnect/backpressure for streamed assets."""
import pytest

from witness_fleet.hosting import _BodyLimitMiddleware


@pytest.mark.asyncio
async def test_body_replay_delivers_body_once_then_delegates_disconnect():
    incoming = iter([
        {'type': 'http.request', 'body': b'{}', 'more_body': False},
        {'type': 'http.disconnect'},
    ])
    async def receive():
        return next(incoming)
    async def send(message):
        pass
    async def downstream(scope, replay, send):
        assert await replay() == {'type': 'http.request', 'body': b'{}', 'more_body': False}
        assert await replay() == {'type': 'http.disconnect'}
    await _BodyLimitMiddleware(downstream)({'type': 'http', 'headers': []}, receive, send)
