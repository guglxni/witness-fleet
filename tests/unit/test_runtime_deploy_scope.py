"""Regression tests for the guarded runtime deployment decision."""

from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path
from urllib.error import URLError

import pytest

from scripts.runtime_deploy_scope import (
    ScopeError,
    fetch_health_revision,
    paths_require_runtime_deploy,
    should_deploy,
)

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/deploy-azure.yml"
REVISION_A = "a" * 40
REVISION_B = "b" * 40


def test_runtime_inputs_trigger_deployment_but_site_docs_and_retained_corpus_do_not():
    assert paths_require_runtime_deploy(
        ["src/witness_fleet/hosting/__init__.py"]
    ) is True
    assert paths_require_runtime_deploy(["services/simulator/runner.py"]) is True
    assert paths_require_runtime_deploy(["deploy/Dockerfile", ".dockerignore"]) is True
    assert paths_require_runtime_deploy(["deploy/azure/deploy-runtime.sh"]) is True
    assert paths_require_runtime_deploy(["demo/src/App.tsx"]) is True
    assert paths_require_runtime_deploy(["demo/package-lock.json"]) is True
    assert paths_require_runtime_deploy(["services/corpus/incident.jsonl"]) is False
    assert paths_require_runtime_deploy(
        ["site/src/LaunchSite.tsx", "docs/guide/deployment.md"]
    ) is False
    assert paths_require_runtime_deploy(
        [".github/workflows/deploy-azure.yml", "scripts/runtime_deploy_scope.py"]
    ) is False


def test_unchanged_runtime_commit_skips_even_if_non_runtime_paths_changed():
    assert should_deploy(REVISION_A, REVISION_A, ["site/index.html"]) is False


def test_new_commit_deploys_only_when_runtime_inputs_changed():
    assert should_deploy(REVISION_B, REVISION_A, ["docs/readme.md"]) is False
    assert should_deploy(REVISION_B, REVISION_A, ["src/witness_fleet/app.py"]) is True
    assert should_deploy(REVISION_B, REVISION_A, []) is False


def test_invalid_commit_ids_are_rejected_before_comparison():
    with pytest.raises(ScopeError, match="40-character lowercase hexadecimal"):
        should_deploy("not-a-commit", REVISION_A, ["src/main.py"])
    with pytest.raises(ScopeError, match="40-character lowercase hexadecimal"):
        should_deploy(REVISION_B, "f" * 39, [])


def test_invalid_health_payload_is_not_treated_as_a_deploy_decision():
    for payload in (
        b"not-json",
        json.dumps({"revision": REVISION_A, "simulation_only": False}).encode(),
        json.dumps({"revision": "development", "simulation_only": True}).encode(),
        json.dumps({"revision": REVISION_A.upper(), "simulation_only": True}).encode(),
        json.dumps({"revision": REVISION_A}).encode(),
    ):
        def response_opener(payload: bytes):
            return lambda *_args, **_kwargs: io.BytesIO(payload)

        with pytest.raises(ScopeError):
            fetch_health_revision("demo.example.test", opener=response_opener(payload))


def test_unavailable_health_is_a_hard_scope_error():
    def unavailable(*_args, **_kwargs):
        raise URLError("connection refused")

    with pytest.raises(ScopeError, match="health check unavailable"):
        fetch_health_revision("demo.example.test", opener=unavailable)


def test_git_revision_comparison_returns_only_paths_changed_between_commits(tmp_path):
    from scripts.runtime_deploy_scope import changed_paths_between_revisions

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    git_config = ["-c", "user.name=Test", "-c", "user.email=test@example.test", "-c", "commit.gpgsign=false"]
    subprocess.run(
        ["git", "-C", str(tmp_path), *git_config, "commit", "--allow-empty", "-qm", "base"],
        check=True,
    )
    base = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    (tmp_path / "site").mkdir()
    (tmp_path / "site/index.html").write_text("site\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src/app.py").write_text("print('runtime')\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "site/index.html", "src/app.py"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), *git_config, "commit", "-qm", "site and runtime"],
        check=True,
    )
    current = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert changed_paths_between_revisions(tmp_path, base, current) == {
        "site/index.html",
        "src/app.py",
    }


def test_renamed_runtime_file_to_docs_still_requires_deployment(tmp_path):
    from scripts.runtime_deploy_scope import changed_paths_between_revisions

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    git_config = [
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.test",
        "-c",
        "commit.gpgsign=false",
        "-c",
        "core.hooksPath=/dev/null",
    ]
    source = tmp_path / "src/runtime.py"
    source.parent.mkdir()
    source.write_text("print('runtime')\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "src/runtime.py"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), *git_config, "commit", "-qm", "runtime source"],
        check=True,
    )
    before = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    destination = tmp_path / "docs/runtime.py"
    destination.parent.mkdir()
    source.rename(destination)
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), *git_config, "commit", "-qm", "move runtime source to docs"],
        check=True,
    )
    after = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    changed_paths = changed_paths_between_revisions(tmp_path, before, after)
    assert changed_paths == {"src/runtime.py", "docs/runtime.py"}
    assert should_deploy(after, before, changed_paths) is True


def test_workflow_only_gates_deployment_side_effects_and_keeps_full_checkout():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "workflows: [Verification]" in workflow
    assert "github.event.workflow_run.conclusion == 'success'" in workflow
    assert "fetch-depth: 0" in workflow
    assert "id: scope" in workflow
    assert workflow.count("if: steps.scope.outputs.deploy == 'true'") == 4
    assert "python scripts/runtime_deploy_scope.py" in workflow
    assert "assert body['revision'] == os.environ['WITNESS_REVISION']" in workflow
    assert "assert body['simulation_only'] is True" in workflow
    assert "GITHUB_STEP_SUMMARY" in (ROOT / "scripts/runtime_deploy_scope.py").read_text(encoding="utf-8")
