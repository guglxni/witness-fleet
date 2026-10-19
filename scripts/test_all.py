"""Run every test file in its owning locked environment, recording real JUnit evidence."""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = {
    'tests/contract/test_sdk_pipeline.py',
    'tests/contract/test_corpus_worker.py',
    'tests/contract/test_corpus_test_isolation.py',
    'tests/adversarial/test_corpus_boundary.py',
}
_GRAPH_MODULES = {'witness_fleet.graph', 'witness_fleet.graph.store'}
_EPHEMERAL_PORT_ROOTS = {
    'graph', 'store', 'runtime_graph', 'isolated_runtime_graph',
    'isolated_console_graph', 'isolated_acl_server',
}


def _graph_store_names(tree: ast.Module) -> tuple[set[str], set[str]]:
    """Return imported GraphStore names and graph-module aliases."""
    constructor_names: set[str] = set()
    module_aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in _GRAPH_MODULES:
            for item in node.names:
                if item.name == 'GraphStore':
                    constructor_names.add(item.asname or item.name)
        elif isinstance(node, ast.Import):
            for item in node.names:
                if item.name in _GRAPH_MODULES:
                    module_aliases.add(item.asname or item.name.split('.')[0])
    return constructor_names, module_aliases


def _is_graph_store_call(node: ast.Call, constructor_names: set[str],
                         module_aliases: set[str]) -> bool:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id in constructor_names
    return (isinstance(func, ast.Attribute) and func.attr == 'GraphStore'
            and isinstance(func.value, ast.Name) and func.value.id in module_aliases)


def _is_constructor_bypass(node: ast.Call, constructor_names: set[str],
                           module_aliases: set[str]) -> bool:
    func = node.func
    return (isinstance(func, ast.Attribute) and func.attr == '__new__'
            and ((isinstance(func.value, ast.Name) and func.value.id in constructor_names)
                 or (isinstance(func.value, ast.Attribute) and func.value.attr == 'GraphStore'
                     and isinstance(func.value.value, ast.Name)
                     and func.value.value.id in module_aliases)))


def _function_assignments(node: ast.AST) -> dict[str, ast.AST]:
    assignments: dict[str, ast.AST] = {}
    for child in ast.walk(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child is not node:
            continue
        if isinstance(child, ast.Assign):
            for target in child.targets:
                if isinstance(target, ast.Name):
                    assignments[target.id] = child.value
                elif isinstance(target, (ast.Tuple, ast.List)) and isinstance(
                    child.value, (ast.Tuple, ast.List)
                ) and len(target.elts) == len(child.value.elts):
                    assignments.update({name.id: value for name, value in zip(
                        target.elts, child.value.elts, strict=True
                    ) if isinstance(name, ast.Name)})
        elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name) and child.value:
            assignments[child.target.id] = child.value
    return assignments


def _dynamic_isolated_port(value: ast.AST, assignments: dict[str, ast.AST],
                           seen: frozenset[str] = frozenset()) -> bool:
    if isinstance(value, ast.Attribute):
        if value.attr != 'port':
            return False
        if isinstance(value.value, ast.Name):
            if value.value.id in _EPHEMERAL_PORT_ROOTS:
                return True
            return value.value.id in assignments and _dynamic_isolated_port(
                assignments[value.value.id], assignments, seen | {value.value.id})
        return False
    if isinstance(value, ast.Name) and value.id not in seen and value.id in assignments:
        return _dynamic_isolated_port(assignments[value.id], assignments, seen | {value.id})
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == 'int':
        if len(value.args) == 1 and _dynamic_isolated_port(value.args[0], assignments, seen):
            return True
        text = ast.unparse(value.args[0]) if value.args else ''
        if 'HostPort' in text and 'NetworkSettings' in text:
            return True
    return False


def find_unsafe_graph_constructors(source: str, filename: str) -> list[str]:
    """Find test-time live GraphStore calls that can target retained/default ports.

    Constructor calls must pass a dynamically sourced isolated fixture port. Bare,
    numeric, configuration-derived, and otherwise unproven endpoints fail closed.
    Offline ``GraphStore.__new__`` query-recording probes are not connections.
    """
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        return [f'{filename}:{exc.lineno or 1}: cannot statically preflight test source: {exc.msg}']
    constructors, modules = _graph_store_names(tree)
    functions = [node for node in ast.walk(tree)
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    findings: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_graph_store_call(node, constructors, modules):
            continue
        if _is_constructor_bypass(node, constructors, modules):
            continue
        owner = next((fn for fn in functions if node in ast.walk(fn)), tree)
        assignments = _function_assignments(owner)
        port = next((kw.value for kw in node.keywords if kw.arg == 'port'), None)
        if port is None and len(node.args) >= 2:
            port = node.args[1]
        if port is None:
            reason = 'omits port and would use the retained GraphStore default'
        elif not _dynamic_isolated_port(port, assignments):
            reason = f'port is not proven to come from an isolated fixture ({ast.unparse(port)})'
        else:
            continue
        findings.append(f'{filename}:{node.lineno}: unsafe GraphStore constructor: {reason}')
    return findings


def preflight(root: Path, interpreters: list[Path], test_files: list[Path]) -> list[str]:
    """Validate both locked runtimes and statically inspect every manifest file."""
    errors: list[str] = []
    for interpreter in interpreters:
        candidate = root / interpreter
        if not candidate.is_file() or not os.access(candidate, os.X_OK):
            errors.append(f'missing or non-executable locked interpreter: {interpreter.as_posix()}')
    for test_file in test_files:
        candidate = root / test_file
        try:
            source = candidate.read_text()
        except OSError as exc:
            errors.append(f'{test_file.as_posix()}: cannot read test source: {exc}')
            continue
        errors.extend(find_unsafe_graph_constructors(source, test_file.as_posix()))
    return errors


def main() -> int:
    all_files = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / 'tests').rglob('test_*.py'))
    missing = CORPUS - set(all_files)
    if missing:
        print(f'ERROR: corpus test manifest references absent files: {sorted(missing)}', file=sys.stderr)
        return 2
    interpreters = [Path('.venv/bin/python'), Path('services/corpus/.venv/bin/python')]
    errors = preflight(ROOT, interpreters, [Path(path) for path in all_files])
    if errors:
        print('SAFE SUITE PREFLIGHT FAILED; no tests were started:', file=sys.stderr)
        for error in errors:
            print(f' - {error}', file=sys.stderr)
        return 2

    run_id = str(time.time_ns())
    output = ROOT / 'artifacts' / 'verification' / run_id
    output.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join(str(ROOT / p) for p in ('.', 'src', 'tests/unit', 'tests/integration', 'services/corpus'))
    phases = [
        ('main', ROOT / interpreters[0], [p for p in all_files if p not in CORPUS]),
        ('corpus', ROOT / interpreters[1], sorted(CORPUS)),
    ]
    reports = []
    for name, interpreter, paths in phases:
        command = [str(interpreter), '-m', 'pytest', *paths, '-q', '--tb=short', f'--junitxml={output / (name + ".xml")}']
        with (output / (name + '.log')).open('w') as log:
            proc = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            assert proc.stdout is not None
            for line in proc.stdout:
                print(line, end='', flush=True)
                log.write(line)
            code = proc.wait()
        xml_path = output / (name + '.xml')
        suites = ET.parse(xml_path).getroot().iter('testsuite') if xml_path.exists() else ()
        totals = {key: 0 for key in ('tests', 'failures', 'errors', 'skipped')}
        for suite in suites:
            for key in totals:
                totals[key] += int(suite.get(key, '0'))
        reports.append({'phase': name, 'interpreter': str(interpreter), 'files': paths, 'command': command,
                        'exit_code': code, 'junit': str(xml_path), 'counts': totals})
    covered = [p for report in reports for p in report['files']]
    if sorted(covered) != all_files or len(covered) != len(set(covered)):
        raise RuntimeError('test manifest coverage is incomplete or duplicated')
    manifest = {'run_id': run_id, 'status': 'passed' if all(r['exit_code'] == 0 and r['counts']['tests'] > 0 for r in reports) else 'failed',
                'all_test_files': all_files, 'phases': reports, 'artifact_dir': str(output)}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))
    return 0 if manifest['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
