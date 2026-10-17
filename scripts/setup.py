"""Safe idempotent dependency setup; no system services or output cleanup."""
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = "35e67a0b27fdcc7f2c28508b09e86169851a8187"


def run(*args, cwd=ROOT):
    subprocess.run(args, cwd=cwd, check=True)


def main():
    for tool in ("uv", "git", "gh", "node", "npm", "docker"):
        if not shutil.which(tool):
            raise SystemExit(f"Required executable missing: {tool}")
    vendor = ROOT / ".research/vendor/FalkorDB--GraphRAG-SDK"
    if not vendor.exists():
        run("gh", "repo", "clone", "FalkorDB/GraphRAG-SDK", str(vendor), "--", "--filter=blob:none", "--no-checkout")
        run("git", "-C", str(vendor), "fetch", "origin", PIN)
        run("git", "-C", str(vendor), "checkout", "--detach", PIN)
    actual = subprocess.check_output(["git", "-C", str(vendor), "rev-parse", "HEAD"], text=True).strip()
    if actual != PIN:
        raise SystemExit("Existing vendor checkout differs from pinned SDK; refusing to reset it")
    run("uv", "sync", "--frozen", "--extra", "dev", "--extra", "simulator")
    run("uv", "sync", "--frozen", "--project", "services/corpus")
    run("npm", "install", "--no-fund", "--no-audit", cwd=ROOT / "web")
    run("npx", "playwright", "install", "chromium", cwd=ROOT / "web")
    run("docker", "compose", "up", "-d", "--wait")
    run(str(ROOT / ".venv/bin/witness-fleet"), "doctor")
    run(str(ROOT / ".venv/bin/mjpython"), "scripts/smoke_native.py")
    print("Installed dependency smoke checks passed; fleet behavior is separately tested.")

if __name__ == "__main__":
    main()
