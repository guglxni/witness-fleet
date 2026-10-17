"""Real loopback process verification for exact, read-only event lookup."""
from __future__ import annotations

import socket
import subprocess
import sys
import time

import httpx

from services.simulator.service import SimulatorService
from witness_fleet.domain import canonical_json_hash
from witness_fleet.simulation.client import SimulatorClient


def test_event_ids_roundtrip_through_real_uvicorn_process(tmp_path):
    root = tmp_path / 'native-service'
    identifiers = ['literal%2F', 'literal%25', '.', '..', '../x', 'a/../b',
                   'evt/% snow-λ', 'a//b', '/leading', 'a?b#c', '%', '雪']
    service = SimulatorService(root)
    try:
        service.create_episode('real-http-lookup', 'SC-001', 3)
        payload = {'task_id': 'task', 'task_fence': 1, 'resource_fences': {'corridor': 1}}
        for sequence, identifier in enumerate(identifiers, 1):
            service.journal.register({
                'id': identifier, 'sequence': sequence, 'kind': 'FENCE_INSTALL',
                'coordinator_epoch': 0, 'effective_world_tick': 0,
                'payload': payload, 'payload_hash': canonical_json_hash(payload),
            })
        originals = {identifier: service.journal.event(identifier) for identifier in identifiers}
    finally:
        service.close()

    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen()
    port = listener.getsockname()[1]
    code = ('import sys,uvicorn; from services.simulator.http import create_app; '
            'uvicorn.run(create_app(root=sys.argv[1]), fd=int(sys.argv[2]), log_level="warning")')
    with (tmp_path / 'uvicorn.log').open('w+') as log:
        process = subprocess.Popen(
            [sys.executable, '-c', code, str(root), str(listener.fileno())],
            pass_fds=(listener.fileno(),), stdout=log, stderr=log,
        )
        listener.close()
        transport = httpx.Client(timeout=1, trust_env=False, follow_redirects=False)
        client = SimulatorClient(f'http://127.0.0.1:{port}', client=transport, timeout=1)
        try:
            deadline = time.monotonic() + 15
            while True:
                if process.poll() is not None:
                    log.seek(0)
                    raise AssertionError(f'HTTP process exited: {log.read()}')
                try:
                    if client.health().get('status') == 'ok':
                        break
                except httpx.TransportError:
                    pass
                assert time.monotonic() < deadline, 'HTTP process never became healthy'
                time.sleep(0.02)

            state = transport.get(client.base_url + '/state').json()
            snapshot = (root / 'snapshot.json').read_bytes()
            for identifier in identifiers:
                assert client.query_event(identifier) == {'status': 'KNOWN', 'event': originals[identifier]}
            for identifier in ['missing%2F', 'missing%25', 'missing/../雪']:
                assert client.query_event(identifier) == {'status': 'NOT_FOUND', 'event_id': identifier}
            assert transport.get(client.base_url + '/state').json() == state
            assert (root / 'snapshot.json').read_bytes() == snapshot
        finally:
            client.close()
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    resumed = SimulatorService(root)
    try:
        assert {identifier: resumed.journal.event(identifier) for identifier in identifiers} == originals
        assert resumed.journal.applied_cursor == 0
        assert resumed.journal._db.execute('SELECT COUNT(*) FROM commands').fetchone()[0] == 0
        assert resumed.journal._db.execute('SELECT COUNT(*) FROM events').fetchone()[0] == len(identifiers)
        assert resumed.status()['last_sequence'] == 0
    finally:
        resumed.close()
