"""Operator commands for a local-only, synthetic robotics laboratory."""
import typer

app = typer.Typer(no_args_is_help=True)

@app.command()
def doctor():
    import json

    from witness_fleet.doctor import dependency_report
    report = dependency_report()
    report["motion_authorized"] = False
    typer.echo(json.dumps(report, indent=2))
    if report["status"] != "ok":
        raise typer.Exit(1)

@app.command()
def serve(run_dir: str = typer.Option(..., help='Dedicated retained run directory'),
          graph_port: int = typer.Option(6382, min=1, max=65535),
          port: int = typer.Option(8094, min=1024, max=65535),
          graph_user: str = typer.Option('wf_ops')):
    """Serve the current inspection-only console API on loopback."""
    from pathlib import Path

    import uvicorn

    from witness_fleet.api.local import create_local_app

    ui_dir = Path(__file__).resolve().parents[2] / 'web' / 'dist'
    application = create_local_app(Path(run_dir), graph_port=graph_port, graph_user=graph_user,
                                   ui_dir=ui_dir if ui_dir.is_dir() else None, port=port)
    typer.echo('Inspection-only local API; runtime integration is incomplete, motion is unavailable.')
    uvicorn.run(application, host='127.0.0.1', port=port)


@app.command()
def mission(run_dir: str = typer.Option(..., help='Dedicated new retained mission directory'),
            graph_port: int = typer.Option(6383, min=1, max=65535),
            port: int = typer.Option(8095, min=1024, max=65535),
            graph_user: str = typer.Option('default'),
            ui_dir: str | None = typer.Option(None, help='Explicit built web/dist directory')):
    """Opt in to SC-001 simulation; start and owner release remain explicit UI actions."""
    from pathlib import Path

    import uvicorn

    from witness_fleet.api.mission import create_mission_app

    assets = Path(ui_dir).resolve() if ui_dir else Path(__file__).resolve().parents[2] / 'web' / 'dist'
    application = create_mission_app(Path(run_dir), graph_port=graph_port, graph_user=graph_user,
        ui_dir=assets if assets.is_dir() else None, port=port)
    typer.echo('Local simulation mission. Start and demo-owner release require explicit actions.')
    uvicorn.run(application, host='127.0.0.1', port=port)


@app.command()
def version():
    from witness_fleet import __version__
    typer.echo(__version__)
