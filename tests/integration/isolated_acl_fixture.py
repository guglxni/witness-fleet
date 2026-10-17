"""Dedicated local ACL server; stop the container and retain its evidence."""
from __future__ import annotations

import json
import subprocess
import time
import uuid
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path

import pytest
from isolated_runtime_fixture import IMAGE

from witness_fleet.graph import GraphStore


@dataclass(frozen=True)
class IsolatedAclServer:
    host: str
    port: int
    container: str
    volume: str


@pytest.fixture(scope="module")
def isolated_acl_server() -> Generator[IsolatedAclServer, None, None]:
    """Run one bounded loopback container with the repository's synthetic role ACL."""
    name = "wf-acl-test-" + uuid.uuid4().hex[:12]
    volume = name
    acl_file = Path(__file__).resolve().parents[2] / "config" / "roles.acl"
    if not acl_file.is_file():
        raise FileNotFoundError("expected local test role ACL config/roles.acl")

    command = [
        "docker", "run", "-d", "--name", name,
        "--memory", "512m", "--cpus", "1", "--restart", "no",
        "-p", "127.0.0.1::6379",
        "-e", "BROWSER=0",
        "-e", "REDIS_ARGS=--appendonly yes --appendfsync always --aclfile /tmp/roles.acl",
        "-v", f"{volume}:/var/lib/falkordb/data",
        "-v", f"{acl_file}:/tmp/roles.acl:ro",
        IMAGE,
    ]
    report = Path("artifacts/integration-20261017/test-containers.jsonl")
    report.parent.mkdir(parents=True, exist_ok=True)
    # Register the container and persistent volume before Docker can create either.
    with report.open("a") as stream:
        stream.write(json.dumps({"container": name, "port": None, "volume": volume}) + "\n")

    try:
        subprocess.run(command, capture_output=True, text=True, check=True, timeout=60)
        details = json.loads(subprocess.check_output(
            ["docker", "inspect", name], text=True, timeout=15
        ))[0]
        port = int(details["NetworkSettings"]["Ports"]["6379/tcp"][0]["HostPort"])
        with report.open("a") as stream:
            stream.write(json.dumps({"container": name, "port": port, "volume": volume}) + "\n")

        deadline = time.monotonic() + 20
        while True:
            store = GraphStore(host="127.0.0.1", port=port, username="wf_ops",
                               socket_timeout=1)
            try:
                store.initialize()
                break
            except Exception:
                if time.monotonic() >= deadline:
                    raise RuntimeError("dedicated ACL FalkorDB server did not become ready") from None
                time.sleep(0.1)
        yield IsolatedAclServer(host="127.0.0.1", port=port, container=name, volume=volume)
    finally:
        # Stop to flush persistence; never remove the container or named volume.
        subprocess.run(["docker", "stop", "--timeout", "20", name],
                       capture_output=True, text=True, check=True, timeout=30)
