"""Guard corpus tests against successful SDK requests using the default endpoint."""
from __future__ import annotations

import ast
from pathlib import Path

TEST_FILES = ("test_sdk_pipeline.py", "test_corpus_worker.py")
NETWORK_METHODS = {"ingest_source", "ingest_path", "search"}
ALLOWLISTED_SOURCES = {
    "facility_manual_r1",
    "owner_roster_r1",
    "maintenance_ticket_r1",
    "restriction_decision_r1",
    "unsigned_chat_r1",
    "release_decision_r1",
    "blanket_ban_r1",
    "conflicting_owner_r1",
}


def _is_inside_pytest_raises(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> bool:
    parent = parents.get(node)
    while parent is not None:
        if isinstance(parent, ast.With):
            if any(
                isinstance(item.context_expr, ast.Call)
                and isinstance(item.context_expr.func, ast.Attribute)
                and isinstance(item.context_expr.func.value, ast.Name)
                and item.context_expr.func.value.id == "pytest"
                and item.context_expr.func.attr == "raises"
                for item in parent.items
            ):
                return True
        parent = parents.get(parent)
    return False


def _has_success_assertion(call: ast.Call, function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    assigned_names = {
        target.id
        for assignment in ast.walk(function)
        if isinstance(assignment, ast.Assign) and call in ast.walk(assignment.value)
        for target in assignment.targets
        if isinstance(target, ast.Name)
    }
    for assertion in (node for node in ast.walk(function) if isinstance(node, ast.Assert)):
        test = assertion.test
        if not isinstance(test, ast.Compare) or not any(
            isinstance(operator, ast.Eq) for operator in test.ops
        ):
            continue
        if not any(isinstance(value, ast.Constant) and value.value == 200
                   for value in test.comparators):
            continue
        left = test.left
        if (isinstance(left, ast.Attribute) and left.attr == "status_code"
                and isinstance(left.value, ast.Name) and left.value.id in assigned_names):
            return True
        if (isinstance(left, ast.Attribute) and left.attr == "status_code"
                and call in ast.walk(left.value)):
            return True
    return False


def _successful_network_request(
    call: ast.Call, function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    if isinstance(call.func, ast.Attribute) and call.func.attr in NETWORK_METHODS:
        return isinstance(call.func.value, ast.Name) and call.func.value.id == "adapter"
    if not isinstance(call.func, ast.Attribute) or call.func.attr != "post":
        return False
    if not call.args or not isinstance(call.args[0], ast.Constant):
        return False
    route = call.args[0].value
    payload = next((item.value for item in call.keywords if item.arg == "json"), None)
    if not isinstance(payload, ast.Dict):
        return False
    values = {
        key.value: value.value
        for key, value in zip(payload.keys, payload.values, strict=True)
        if isinstance(key, ast.Constant) and isinstance(value, ast.Constant)
    }
    is_candidate = (
        route == "/ingest" and values.get("source_id") in ALLOWLISTED_SOURCES
    ) or (route == "/search" and "cypher" not in values)
    return is_candidate and _has_success_assertion(call, function)


def _is_fixture_attribute(node: ast.AST | None, attribute: str) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == attribute
        and isinstance(node.value, ast.Name)
        and node.value.id == "isolated_acl_server"
    )


def _has_isolated_fixture_binding(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    args = function.args.posonlyargs + function.args.args + function.args.kwonlyargs
    if not any(arg.arg == "isolated_acl_server" for arg in args):
        return False
    constructors = [
        node for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "CorpusSDKAdapter"
    ]
    return bool(constructors) and all(
        _is_fixture_attribute(
            next((keyword.value for keyword in constructor.keywords if keyword.arg == "host"), None),
            "host",
        )
        and _is_fixture_attribute(
            next((keyword.value for keyword in constructor.keywords if keyword.arg == "port"), None),
            "port",
        )
        for constructor in constructors
    )


def test_successful_corpus_network_requests_bind_only_to_the_isolated_acl_server():
    contract_dir = Path(__file__).resolve().parent
    violations = []
    for filename in TEST_FILES:
        tree = ast.parse((contract_dir / filename).read_text(encoding="utf-8"))
        for function in (node for node in ast.walk(tree)
                         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
            parents = {
                child: parent
                for parent in ast.walk(function)
                for child in ast.iter_child_nodes(parent)
            }
            has_successful_network_call = any(
                _successful_network_request(call, function)
                and not _is_inside_pytest_raises(call, parents)
                for call in ast.walk(function) if isinstance(call, ast.Call)
            )
            if has_successful_network_call and not _has_isolated_fixture_binding(function):
                violations.append(f"{filename}:{function.name}")

    assert not violations, (
        "Successful corpus SDK/worker requests must explicitly use isolated_acl_server host/port; "
        f"default-endpoint candidates: {', '.join(violations)}"
    )
