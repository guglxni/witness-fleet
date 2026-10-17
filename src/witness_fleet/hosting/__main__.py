"""Run the independent hosted simulation gateway."""
from __future__ import annotations

import argparse
import os

import uvicorn

from witness_fleet.hosting import create_hosted_app


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Witness Fleet hosted simulation demo")
    parser.add_argument("--host", default="127.0.0.1", help="private listener address")
    parser.add_argument("--port", type=int, default=8080, help="private listener port")
    args = parser.parse_args(argv)
    origin = os.environ.get("WITNESS_DEMO_ORIGIN", "https://witness-fleet-guglxni.eastus.cloudapp.azure.com")
    revision = os.environ.get("WITNESS_REVISION", "development")
    data = os.environ.get("WITNESS_DATA_DIR", "/data")
    graph_port = int(os.environ.get("WITNESS_GRAPH_PORT", "6379"))
    app = create_hosted_app(data, origin=origin, graph_port=graph_port, revision=revision)
    uvicorn.run(app, host=args.host, port=args.port, proxy_headers=True,
                forwarded_allow_ips="127.0.0.1", access_log=False, server_header=False)


if __name__ == "__main__":
    main()
