import json
from pathlib import Path

from scripts.verify_docs import REQUIRED, validate


def _project_root(tmp_path: Path) -> Path:
    for name in REQUIRED:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        content = "Documentation.\n"
        if name == "README.md":
            content += "Known protected-file consent timeout is disclosed.\n"
        if name == "REQUIREMENTS.md":
            content = "\n".join(f"| R-{number:03d} | requirement |" for number in range(1, 39))
        path.write_text(content)

    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "sources.json").write_text(json.dumps({"sources": []}))
    (evidence / "repository-manifest.json").write_text(json.dumps({"repositories": []}))
    (evidence / "repository-manifest-full.json").write_text(json.dumps({"repositories": []}))
    (evidence / "parent-repository-verification.json").write_text("[]")
    return tmp_path


def test_dependency_and_vendor_markdown_are_not_project_citation_documents(tmp_path):
    root = _project_root(tmp_path)
    dependency_docs = [
        ".venv/lib/python/site-packages/example/README.md",
        "services/corpus/.venv/lib/python/site-packages/example/README.md",
        ".git/vendor/example/README.md",
        ".research/vendor/example/README.md",
        "web/node_modules/example/README.md",
        "web/node_modules/example/nested/node_modules/other/README.md",
    ]
    for relative_path in dependency_docs:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Upstream doc [9001] with [missing](upstream-absent.md).\n")

    result = validate(root)

    assert result["errors"] == []
    assert result["markdown_files"] == len(REQUIRED)


def test_nested_project_owned_markdown_still_checks_citations_and_links(tmp_path):
    root = _project_root(tmp_path)
    project_docs = {
        ".research/project-notes.md": "Internal research [9001].\n",
        "research/audit-notes.md": "Research note [9002].\n",
        "web/docs/architecture.md": "Web note [9003] and [missing](not-here.md).\n",
    }
    for relative_path, text in project_docs.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    result = validate(root)

    errors = "\n".join(result["errors"])
    for relative_path, text in project_docs.items():
        if "[missing]" in text:
            assert f"{relative_path}: missing local link not-here.md" in errors
        citation = text.split("[")[1].split("]")[0]
        assert f"{relative_path}: unknown citation {citation}" in errors


def test_missing_required_project_document_still_fails(tmp_path):
    root = _project_root(tmp_path)
    (root / "math/ROBOTICS.md").unlink()

    result = validate(root)

    assert "Missing/empty required document: math/ROBOTICS.md" in result["errors"]
