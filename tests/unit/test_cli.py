import json

from typer.testing import CliRunner

from witness_fleet.cli import app


def test_doctor_cli_checks_installed_toolchain():
    result = CliRunner().invoke(app, ["doctor"])
    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["status"] == "ok"
    assert report["motion_authorized"] is False
    assert {p["name"] for p in report["packages"]} >= {"mujoco", "networkx", "scipy"}
