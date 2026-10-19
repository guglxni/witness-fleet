"""Exercise the real wheel builder without relying on local generated assets."""
from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def source_checkout(tmp_path: Path) -> Path:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    for name in ("pyproject.toml", "LICENSE", ".gitignore"):
        shutil.copy2(ROOT / name, checkout / name)
    shutil.copytree(
        ROOT / "src", checkout / "src",
        ignore=shutil.ignore_patterns("static", "__pycache__", "*.pyc"),
    )
    shutil.copytree(
        ROOT / "services", checkout / "services",
        ignore=shutil.ignore_patterns("corpus", "__pycache__", "*.pyc"),
    )
    return checkout


def build_wheel(checkout: Path, output: Path) -> Path:
    uv = shutil.which("uv")
    assert uv is not None, "uv is required by the locked project build workflow"
    result = subprocess.run(
        [uv, "build", "--wheel", str(checkout), "--out-dir", str(output)],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    wheels = list(output.glob("*.whl"))
    assert len(wheels) == 1
    return wheels[0]


def test_clean_checkout_build_does_not_require_generated_hosted_ui(tmp_path):
    checkout = source_checkout(tmp_path)
    assert not (checkout / "src/witness_fleet/hosting/static").exists()
    wheel = build_wheel(checkout, tmp_path / "wheel")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        assert "witness_fleet/hosting/__init__.py" in names
        assert "services/simulator/assets/facility.xml" in names
        assert not any(name.startswith("services/corpus/") for name in names)


def test_wheel_includes_real_generated_hosted_assets_ignored_by_git(tmp_path):
    checkout = source_checkout(tmp_path)
    generated = ROOT / "src/witness_fleet/hosting/static"
    assert (generated / "index.html").is_file(), "Build the hosted UI before package verification"
    shutil.copytree(generated, checkout / "src/witness_fleet/hosting/static")
    wheel = build_wheel(checkout, tmp_path / "wheel")
    with zipfile.ZipFile(wheel) as archive:
        for source in generated.rglob("*"):
            if source.is_file():
                member = "witness_fleet/hosting/static/" + source.relative_to(generated).as_posix()
                assert member in archive.namelist(), f"Generated asset omitted: {member}"
                assert archive.read(member) == source.read_bytes()
