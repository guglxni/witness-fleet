"""Local inspection-server composition; not fleet motion authority."""
from contextlib import asynccontextmanager
from pathlib import Path

from services.simulator.service import SimulatorService
from witness_fleet.api.app import create_app
from witness_fleet.graph import GraphStore
from witness_fleet.ingestion.source_store import SourceStore
from witness_fleet.runtime.coordinator import Coordinator


def create_local_app(run_dir, *, graph_port=6382, graph_user='wf_ops', ui_dir=None, port=8094):
    root = Path(run_dir).expanduser().resolve()
    graph = GraphStore(host='127.0.0.1', port=graph_port, username=graph_user)
    controller = Coordinator(graph, SourceStore(root / 'sources'), SimulatorService(root / 'sim'))
    app = create_app(controller, local_port=port)
    if ui_dir is not None:
        from starlette.staticfiles import StaticFiles

        app.mount('/', StaticFiles(directory=Path(ui_dir).resolve(), html=True), name='operator-ui')

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            controller.close()

    app.router.lifespan_context = lifespan
    return app
