"""Explicit opt-in loopback mission composition; startup never dispatches."""
import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from services.simulator.service import SimulatorService
from witness_fleet.api.app import create_app
from witness_fleet.graph import GraphStore
from witness_fleet.ingestion.source_store import SourceStore
from witness_fleet.runtime.bootstrap import bootstrap
from witness_fleet.runtime.mission import MissionController


def create_mission_app(run_dir, *, graph=None, graph_port=6383, graph_user='default', ui_dir=None, port=8095):
    root = Path(run_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    identity = root / 'mission-identity.json'
    if identity.exists():
        config = json.loads(identity.read_text())
        if config['graph_port'] != graph_port or config['graph_user'] != graph_user:
            raise ValueError('retained mission connection identity cannot change')
    else:
        token = uuid.uuid4().hex
        config = {'graph_name': 'wf_mission_' + token, 'prefix': 'mission-' + token,
                  'graph_port': graph_port, 'graph_user': graph_user}
        # Never write into the existing default/showcase graph namespace.
        with identity.open('x') as stream:
            json.dump(config, stream, indent=2)
    if graph is None:
        graph = GraphStore(host='127.0.0.1', port=graph_port, username=graph_user)
        graph.graph_name = config['graph_name']
        graph._graph = graph._client.select_graph(graph.graph_name)
    graph.initialize()
    sources = SourceStore(root / 'sources')
    service = SimulatorService(root / 'sim')
    try:
        if not service.status()['episode_id']:
            manifest = bootstrap(graph, sources, prefix=config['prefix'], scenario='SC-001',
                                 seed=3, profile='mission-v2')
            service.create_episode(manifest['episode_id'], 'SC-001', 3)
            service.load_payload('courier', config['prefix'] + '-parcel')
        controller = MissionController(graph, sources, service)
        app = create_app(controller, local_port=port)
        app.state.controller = controller
        if ui_dir is not None:
            from starlette.staticfiles import StaticFiles
            app.mount('/', StaticFiles(directory=Path(ui_dir).resolve(), html=True), name='mission-ui')
    except BaseException:
        service.close()
        raise

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            controller.close()
    app.router.lifespan_context = lifespan
    return app
