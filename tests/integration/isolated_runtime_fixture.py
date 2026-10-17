"""Isolated additive FalkorDB fixture: stop servers, retain all evidence."""
import json
import subprocess
import time
import uuid
from pathlib import Path

import pytest

from witness_fleet.graph import GraphStore

IMAGE = 'falkordb/falkordb@sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6'


@pytest.fixture(scope='module')
def isolated_runtime_graph():
    """One bounded module server; teardown stops it but NEVER removes data."""
    name = 'wf-runtime-test-' + uuid.uuid4().hex[:12]
    command = ['docker', 'run', '-d', '--name', name, '--memory', '512m',
               '--cpus', '1', '--restart', 'no', '-p', '127.0.0.1::6379',
               '-e', 'BROWSER=0', '-e', 'REDIS_ARGS=--appendonly yes --appendfsync always',
               '-v', name + ':/var/lib/falkordb/data', IMAGE]
    report = Path('artifacts/integration-20261017/test-containers.jsonl')
    report.parent.mkdir(parents=True, exist_ok=True)
    # Record before startup as even a timed-out docker run may create the server.
    with report.open('a') as stream:
        stream.write(json.dumps({'container': name, 'port': None, 'volume': name}) + '\n')
    try:
        subprocess.run(command, capture_output=True, text=True, check=True, timeout=60)
        details = json.loads(subprocess.check_output(
            ['docker', 'inspect', name], text=True, timeout=15))[0]
        port = int(details['NetworkSettings']['Ports']['6379/tcp'][0]['HostPort'])
        with report.open('a') as stream:
            stream.write(json.dumps({'container': name, 'port': port, 'volume': name}) + '\n')
        deadline = time.monotonic() + 15
        while True:
            try:
                graph = GraphStore(port=port, username='default')
                graph.initialize()
                break
            except Exception:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(.1)
        yield graph
    finally:
        # SIGTERM lets Redis persist; container + named volume remain inspectable.
        subprocess.run(['docker', 'stop', '--timeout', '20', name],
                       capture_output=True, text=True, check=True, timeout=30)
