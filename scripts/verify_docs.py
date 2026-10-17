#!/usr/bin/env python3
"""Validate documentation structure; not an application/runtime test."""
import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = '''README.md prd.md architecture.md REQUIREMENTS.md PLAN.md INTEGRATIONS.md REPOSITORIES.md DESIGN.md PROPOSAL.md DEMO.md RESEARCH.md RESEARCH_SYSTEM_ONE.md MATH.md GRAPH_SCHEMA.md DECISION_CONTRACTS.md EVALUATION.md SECURITY.md FAILURE_MODES.md RUNTIME.md SIMULATION.md API.md ADRS.md PROGRAM_DESIGN.md FIXTURES.md SOURCES.md VALIDATION.md REVIEW.md math/ROBOTICS.md math/GRAPH_AUTHORITY.md math/SYSTEM_ONE.md math/STATISTICS.md research/FALKORDB_AUDIT.md'''.split()
EXCLUDED_MARKDOWN_DIRS = {'.git', '.venv', 'node_modules'}


def project_markdown_files(root: Path) -> list[Path]:
    docs = []
    for current, directories, files in os.walk(root):
        current_path = Path(current)
        relative_parts = current_path.relative_to(root).parts
        directories[:] = [
            name
            for name in directories
            if name not in EXCLUDED_MARKDOWN_DIRS
            and not (relative_parts == ('.research',) and name == 'vendor')
        ]
        docs.extend(current_path / name for name in files if name.endswith('.md'))
    return sorted(docs)


def validate(root: Path) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    for name in REQUIRED:
        if not (root / name).is_file() or (root / name).stat().st_size == 0:
            errors.append(f'Missing/empty required document: {name}')
    ledger = json.loads((root / 'evidence/sources.json').read_text())['sources']
    source_map = {int(s['id']): s['url'] for s in ledger}
    if len(source_map) != len(ledger) or len(set(source_map.values())) != len(ledger):
        errors.append('Citation IDs or canonical URLs duplicated')
    docs = project_markdown_files(root)
    citation_count = 0
    link_count = 0
    for p in docs:
        text = p.read_text()
        # Remove fenced code before citation/link checks, preserving actual prose.
        stripped = re.sub(r'^```[^\n]*\n.*?^```\s*$', '', text, flags=re.S | re.M)
        for ident in re.findall(r'(?<!!)\[(\d+)\]', stripped):
            citation_count += 1
            if int(ident) not in source_map:
                errors.append(f'{p.relative_to(root)}: unknown citation {ident}')
        for href in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)', stripped):
            href = href.split(' "')[0]
            if re.match(r'^(?:https?|mailto|data):', href) or href.startswith('#'):
                continue
            dest = unquote(href.split('#')[0])
            if dest:
                link_count += 1
                if not (p.parent / dest).exists():
                    errors.append(f'{p.relative_to(root)}: missing local link {dest}')
        for ident, href in re.findall(r'^\[(\d+)\]:\s+(https?://\S+)', text, re.M):
            if source_map.get(int(ident)) != href:
                errors.append(f'{p.relative_to(root)}: wrong source mapping {ident}')
        if '[SKILL_PRUNED]' in text or '[source audit]' in text:
            errors.append(f'{p.relative_to(root)}: unresolved context placeholder')
    manifest = json.loads((root / 'evidence/repository-manifest.json').read_text())['repositories']
    full = json.loads((root / 'evidence/repository-manifest-full.json').read_text())['repositories']
    full_by_name = {r['full_name']: r for r in full}
    verification = json.loads((root / 'evidence/parent-repository-verification.json').read_text())
    verified = {r['repository']: r for r in verification}
    recipes = (root / 'REPOSITORIES.md').read_text()
    clone_count = len(re.findall(r'^gh repo clone ', recipes, re.M))
    if clone_count != len(manifest):
        errors.append(f'Clone recipes {clone_count} != repository count {len(manifest)}')
    for repo in manifest:
        name = repo['full_name']
        sha = repo['resolved_pin']
        if not re.fullmatch(r'[0-9a-f]{40}', sha):
            errors.append(f'Invalid literal SHA: {name}')
        rec = verified.get(name, {})
        if rec.get('expected') != sha or rec.get('verified') is not True:
            errors.append(f'Missing independent exact-commit verification: {name}')
        if repo.get('recursive_tree_truncated') is not False:
            errors.append(f'Tree completeness unverified: {name}')
        paths = set(full_by_name.get(name, {}).get('tree_blob_paths', []))
        for path in repo['meaningful_source_entrypoints_verified']:
            if path not in paths:
                errors.append(f'Entrypoint absent from pinned tree: {name}:{path}')
        if f'gh repo clone {name} ' not in recipes or sha not in recipes:
            errors.append(f'Missing exact clone/pin recipe: {name}')
    requirement_text = (root / 'REQUIREMENTS.md').read_text()
    ids = re.findall(r'^\| (R-\d{3}) \|', requirement_text, re.M)
    if len(ids) != len(set(ids)):
        errors.append('Duplicate requirement ID')
    expected_ids = [f'R-{i:03d}' for i in range(1, 39)]
    if ids != expected_ids:
        errors.append('Requirement inventory is not exact R-001..R-038')
    blocked = [name for name in ['AGENTS.md', 'CLAUDE.md', 'SKILL.md'] if not (root / name).exists()]
    if blocked:
        if 'protected-file consent timeout' not in (root / 'README.md').read_text():
            errors.append('Missing disclosure of protected instruction-file block')
        warnings.append('Known incomplete user deliverable: protected instruction files absent pending approval: ' + ', '.join(blocked))
    return {
        'status': 'passed_with_disclosed_blocker' if not errors and blocked else 'passed' if not errors else 'failed',
        'scope': 'Documentation integrity only; not semantic truth, application execution, inference, or robot safety validation',
        'markdown_files': len(docs), 'required_documents': len(REQUIRED),
        'registered_sources': len(source_map), 'citation_occurrences_checked': citation_count,
        'local_links_checked': link_count, 'repository_pins_checked': len(manifest),
        'gh_clone_recipes_checked': clone_count, 'requirements_checked': len(ids),
        'errors': errors, 'warnings': warnings,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    result = validate(args.root)
    print(json.dumps(result, indent=2))
    sys.exit(1 if result['errors'] else 0)
