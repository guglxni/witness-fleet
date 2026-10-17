"""Loopback-only simulator HTTP transport. Uncertainty never implies effect failure."""
from __future__ import annotations

from urllib.parse import quote, urlsplit

import httpx

from witness_fleet.domain import canonical_json_hash


class SimulatorClient:
    def __init__(self, base_url: str, *, client: httpx.Client | None = None, timeout: float = 5):
        url = urlsplit(base_url)
        if (url.scheme != 'http' or url.hostname not in {'localhost', '127.0.0.1'}
                or url.username or url.password or url.path not in {'', '/'} or url.query or url.fragment
                or isinstance(timeout, bool) or not 0 < timeout <= 5):
            raise ValueError('simulator requires a bounded loopback HTTP endpoint')
        port = url.port  # Access eagerly: urllib rejects malformed/out-of-range ports here.
        if (port is not None and not 1 <= port <= 65535):
            raise ValueError('valid loopback port required')
        self.base_url = base_url.rstrip('/')
        self.client = client or httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False)
        self.timeout = timeout

    def _request(self, method: str, path: str, payload=None, *, missing=None,
                 accepted_statuses=(200, 201, 202, 409, 503)) -> dict:
        try:
            result = self.client.request(method, self.base_url + path, json=payload,
                                         timeout=self.timeout, follow_redirects=False)
        except httpx.TransportError:
            return {'status': 'UNKNOWN_TRANSPORT'}
        if result.status_code == 404:
            return missing or {'status': 'NOT_FOUND'}
        if result.status_code not in accepted_statuses:
            return {'status': 'INVALID_RESPONSE'}
        try:
            data = result.json()
        except ValueError:
            return {'status': 'INVALID_RESPONSE'}
        return data if isinstance(data, dict) else {'status': 'INVALID_RESPONSE'}

    def health(self) -> dict:
        return self._request('GET', '/health')

    def query_receipt(self, command_id: str) -> dict:
        return self._request('GET', '/commands/' + quote(command_id, safe=''),
                             missing={'status': 'NOT_FOUND', 'command_id': command_id})

    def query_event(self, event_id: str) -> dict:
        if not isinstance(event_id, str) or not event_id:
            raise ValueError('non-empty event identifier required')
        encoded_id = quote(event_id, safe='').replace('.', '%2E')
        result = self._request('GET', '/events/' + encoded_id,
                               missing={'status': 'NOT_FOUND', 'event_id': event_id},
                               accepted_statuses=(200,))
        if result == {'status': 'UNKNOWN_TRANSPORT'} or result == {'status': 'INVALID_RESPONSE'}:
            return result
        if result == {'status': 'NOT_FOUND', 'event_id': event_id}:
            return result
        if set(result) != {'status', 'event'} or result.get('status') != 'KNOWN':
            return {'status': 'INVALID_RESPONSE'}
        event = result.get('event')
        fields = {'id', 'sequence', 'payload_hash', 'kind', 'coordinator_epoch',
                  'effective_world_tick', 'payload', 'status'}
        if not isinstance(event, dict) or set(event) != fields:
            return {'status': 'INVALID_RESPONSE'}
        if (event['id'] != event_id or not isinstance(event['id'], str)
                or type(event['sequence']) is not int or event['sequence'] < 1
                or type(event['coordinator_epoch']) is not int or event['coordinator_epoch'] < 0
                or type(event['effective_world_tick']) is not int or event['effective_world_tick'] < 0
                or not isinstance(event['payload_hash'], str) or not event['payload_hash']
                or not isinstance(event['kind'], str)
                or event['kind'] not in {'COMMAND', 'POLICY_ACTIVATION', 'REVOCATION',
                                         'FENCE_INSTALL', 'EPOCH_BARRIER'}
                or not isinstance(event['status'], str)
                or event['status'] not in {'RECEIVED', 'APPLIED', 'CANCELLED'}
                or not isinstance(event['payload'], dict)):
            return {'status': 'INVALID_RESPONSE'}
        try:
            if canonical_json_hash(event['payload']) != event['payload_hash']:
                return {'status': 'INVALID_RESPONSE'}
        except (TypeError, ValueError, OverflowError):
            return {'status': 'INVALID_RESPONSE'}
        return result

    def observations(self) -> dict:
        return self._request('GET', '/observations')

    def create_episode(self, episode_id: str, scenario: str, seed: int) -> dict:
        return self._request('POST', '/episodes', {'episode_id': episode_id, 'scenario': scenario, 'seed': seed})

    def send_event(self, event) -> dict:
        return self._request('POST', '/events', event.model_dump(mode='json'))

    def advance(self, ticks: int) -> dict:
        if type(ticks) is not int or not 1 <= ticks <= 100000:
            raise ValueError('bounded integer ticks required')
        return self._request('POST', '/advance', {'ticks': ticks})

    def close(self) -> None:
        self.client.close()
