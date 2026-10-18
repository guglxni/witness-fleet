"""Fail-closed decision gate for Azure runtime deployments."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_DNS_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
_RUNTIME_FILES = {".dockerignore", "pyproject.toml", "uv.lock", "deploy/Dockerfile"}


class ScopeError(RuntimeError):
    """Raised when deployment scope cannot be determined safely."""


def validate_revision(revision: str) -> str:
    """Return a full lowercase Git SHA or fail closed."""
    if not isinstance(revision, str) or _COMMIT_RE.fullmatch(revision) is None:
        raise ScopeError("revision must be a 40-character lowercase hexadecimal Git commit")
    return revision


def paths_require_runtime_deploy(paths: list[str] | tuple[str, ...] | set[str]) -> bool:
    """Whether changed paths can affect the runtime image or deployment process."""
    for path in paths:
        normalized = path.replace("\\", "/").removeprefix("./")
        if normalized in _RUNTIME_FILES:
            return True
        if normalized.startswith("src/"):
            return True
        if normalized.startswith("services/") and not normalized.startswith("services/corpus/"):
            return True
        if normalized.startswith("deploy/azure/"):
            return True
    return False


def should_deploy(
    tested_revision: str,
    live_revision: str,
    changed_paths: list[str] | tuple[str, ...] | set[str],
) -> bool:
    """Return true only when a different live revision has runtime-input changes."""
    tested = validate_revision(tested_revision)
    live = validate_revision(live_revision)
    if tested == live:
        return False
    return paths_require_runtime_deploy(changed_paths)


def _run_git(repo: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ScopeError(f"git could not resolve the deployment comparison: {exc}") from exc
    return result.stdout.strip()


def _require_commit_object(repo: Path, revision: str) -> str:
    commit = validate_revision(revision)
    _run_git(repo, "cat-file", "-e", f"{commit}^{{commit}}")
    return commit


def changed_paths_between_revisions(repo: Path, before: str, after: str) -> set[str]:
    """Read changed paths from two existing commits without invoking a shell."""
    old_commit = _require_commit_object(repo, before)
    new_commit = _require_commit_object(repo, after)
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "diff", "--no-renames", "--name-only", "-z", old_commit, new_commit, "--"],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ScopeError(f"git could not compare the deployment commits: {exc}") from exc
    return {os.fsdecode(path) for path in result.stdout.split(b"\0") if path}


def _validate_demo_host(demo_host: str) -> str:
    if not isinstance(demo_host, str) or not demo_host or len(demo_host) > 253:
        raise ScopeError("DEMO_HOST is missing or invalid")
    labels = demo_host.rstrip(".").split(".")
    if not labels or any(_DNS_LABEL_RE.fullmatch(label) is None for label in labels):
        raise ScopeError("DEMO_HOST must be a hostname without scheme, port, or path")
    return demo_host


def fetch_health_revision(
    demo_host: str,
    *,
    opener: Callable[..., Any] = urlopen,
) -> str:
    """Fetch strict simulation-only health and return its full Git revision."""
    host = _validate_demo_host(demo_host)
    request = Request(f"https://{host}/healthz", headers={"Accept": "application/json"})
    try:
        response = opener(request, timeout=15)
        with response as health_response:
            status = getattr(health_response, "status", 200)
            if status != 200:
                raise ScopeError(f"health check unavailable (HTTP {status})")
            payload = json.loads(health_response.read())
    except ScopeError:
        raise
    except Exception as exc:
        raise ScopeError(f"health check unavailable or invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise ScopeError("health check returned an invalid payload")
    if payload.get("simulation_only") is not True:
        raise ScopeError("health response is not marked simulation_only")
    health_revision = payload.get("revision")
    if not isinstance(health_revision, str):
        raise ScopeError("health response has an invalid revision: revision must be a string")
    try:
        return validate_revision(health_revision)
    except ScopeError as exc:
        raise ScopeError(f"health response has an invalid revision: {exc}") from exc


def _append(path: str, text: str) -> None:
    if not path:
        raise ScopeError("GitHub Actions output path is unavailable")
    with Path(path).open("a", encoding="utf-8") as output_file:
        output_file.write(text)


def _manual_dispatch(output_path: str, summary_path: str) -> None:
    _append(output_path, "deploy=true\n")
    _append(
        summary_path,
        "Manual dispatch explicitly requested deployment; runtime scope and health were not used.\n",
    )


def evaluate_workflow_run(repo: Path, demo_host: str) -> tuple[bool, str]:
    """Compare the tested checkout with the healthy live runtime commit."""
    tested_revision = _require_commit_object(repo, _run_git(repo, "rev-parse", "HEAD"))
    live_revision = fetch_health_revision(demo_host)
    changed_paths = changed_paths_between_revisions(repo, live_revision, tested_revision)
    deploy = should_deploy(tested_revision, live_revision, changed_paths)
    if deploy:
        detail = (
            f"Runtime-input changes detected between `{live_revision}` and `{tested_revision}`; "
            "deployment and public revision verification will run."
        )
    else:
        detail = (
            f"No runtime-input changes since healthy revision `{live_revision}`; "
            "skipping Azure login, build, deployment, and deployment verification."
        )
    return deploy, detail


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    arguments = parser.parse_args()
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    output_path = os.environ.get("GITHUB_OUTPUT", "")
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
    try:
        if event_name == "workflow_dispatch":
            _manual_dispatch(output_path, summary_path)
            return 0
        if event_name != "workflow_run":
            raise ScopeError(f"unsupported event for deployment scope: {event_name!r}")
        deploy, detail = evaluate_workflow_run(arguments.repo, os.environ.get("DEMO_HOST", ""))
        _append(output_path, f"deploy={'true' if deploy else 'false'}\n")
        _append(summary_path, detail + "\n")
        print(detail)
        return 0
    except (OSError, ScopeError) as exc:
        print(f"Deployment scope could not be determined safely: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
