from __future__ import annotations

from typing import Final

from falkordb import FalkorDB

GRAPH_SCHEMA_VERSION: Final[int] = 1
NODE_LABELS: Final[tuple[str, ...]] = (
    "FleetState", "Robot", "Capability", "Map", "HazardClass", "Location", "Corridor",
    "Task", "Resource", "Claim", "Command", "AuthorizationReceipt", "DispatchEvent",
    "DeliveryReceipt", "CancellationDisposition", "Observation", "Hypothesis", "PlanningFact",
    "Episode", "Procedure", "Source", "Revision", "EvidenceSpan", "Owner", "Decision",
    "Restriction", "Release", "Permission", "Assessment", "ApprovalEvent",
)


class MigrationError(RuntimeError):
    """The pinned database could not be made schema-ready."""


def migrate(graph_name: str, client: FalkorDB) -> int:
    """Provision stable-id uniqueness invariants and verify readiness on the pinned engine."""
    graph = client.select_graph(graph_name)
    existing = graph.ro_query("CALL db.constraints()")
    constraints = [
        {"type": row[0], "label": row[1], "properties": row[2],
         "entitytype": row[3], "status": row[4]}
        for row in existing.result_set
    ]
    calls = 1
    for label in NODE_LABELS:
        operational = any(
            c["type"] == "UNIQUE" and c["entitytype"] == "NODE" and c["label"] == label
            and c["properties"] == ["id"] and c["status"] == "OPERATIONAL"
            for c in constraints
        )
        if operational:
            continue
        try:
            graph.create_node_unique_constraint(label, "id")
            calls += 2  # wrapper issues the supporting range-index and constraint commands
        except Exception as exc:
            if "already exists" not in str(exc).lower():
                raise MigrationError(f"could not create {label}.id uniqueness: {exc}") from exc
            calls += 2
    final = graph.ro_query("CALL db.constraints()")
    calls += 1
    constraints = [
        {"type": row[0], "label": row[1], "properties": row[2],
         "entitytype": row[3], "status": row[4]}
        for row in final.result_set
    ]
    for label in NODE_LABELS:
        if not any(
            c["type"] == "UNIQUE" and c["entitytype"] == "NODE" and c["label"] == label
            and c["properties"] == ["id"] and c["status"] == "OPERATIONAL"
            for c in constraints
        ):
            raise MigrationError(f"unique constraint for {label}.id is not operational")
    return calls
