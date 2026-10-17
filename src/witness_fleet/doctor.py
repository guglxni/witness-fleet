"""Readiness reporting, separate from motion authorization."""
from importlib.metadata import PackageNotFoundError, version

PACKAGES = ("fastapi", "uvicorn", "pydantic", "httpx", "falkordb", "numpy",
            "networkx", "scipy", "mujoco", "Pillow", "imageio", "imageio-ffmpeg",
            "pytest", "pytest-asyncio", "ruff", "mypy", "hypothesis", "typer")


def dependency_report(*, packages=None):
    rows = []
    for name in PACKAGES if packages is None else packages:
        try:
            rows.append({"name": name, "status": "ok", "version": version(name)})
        except PackageNotFoundError:
            rows.append({"name": name, "status": "missing", "version": None})
    return {"status": "blocked" if any(row["status"] != "ok" for row in rows) else "ok", "packages": rows}
