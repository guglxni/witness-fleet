"""Explicit barrier recovery must retain HOLD when command outcomes are uncertain."""

import json

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401
from test_barrier_resume import HOLDER, _setup

from services.simulator.service import SimulatorService


@pytest.mark.parametrize("command_state", ["SENT", "UNKNOWN"])
def test_recover_refuses_prior_command_history_without_mutation(
        isolated_console_graph, tmp_path, command_state):  # noqa: F811
    from witness_fleet.runtime.barrier_resume import InjectedBarrierCrash, TrustedBarrierResumer

    service, event, clock = _setup(isolated_console_graph, tmp_path)
    try:
        with pytest.raises(InjectedBarrierCrash, match="after journal commit"):
            TrustedBarrierResumer(isolated_console_graph, service, HOLDER,
                                 clock=clock).resume(event, fault_at="after_journal_commit")
    finally:
        service.close()

    recovered = SimulatorService(tmp_path / "simulator")
    try:
        assert recovered.status()["held"] is True
        assert recovered.status()["dispatch_ready"] is False
        receipt = recovered.journal.record_command(
            f"prior-{command_state.lower()}",
            f"prior-command-hash-{command_state.lower()}",
            command_state,
        )
        assert receipt == {
            "status": "RECORDED",
            "command_id": f"prior-{command_state.lower()}",
            "state": command_state,
        }
        before = _recovery_state(recovered)
        assert before["identity"]["held"] is True
        assert before["native"]["held"] is True
        assert before["commands"][0]["state"] == command_state
        assert [(row["command_id"], row["state"]) for row in before["history"]] == [
            (f"prior-{command_state.lower()}", command_state),
        ]

        with pytest.raises(ValueError, match="prior command history blocks committed barrier recovery"):
            TrustedBarrierResumer(isolated_console_graph, recovered, HOLDER,
                                 clock=clock).recover(event)

        assert _recovery_state(recovered) == before
        assert recovered.status()["held"] is True
        assert recovered.status()["dispatch_ready"] is False
    finally:
        recovered.close()


def _recovery_state(service):
    checkpoint = service.journal.checkpoint()
    commands = service.journal._db.execute(
        "SELECT command_id,payload_hash,state,event_id,last_known_state,"
        "reconciliation_state,checkpoint_id FROM commands ORDER BY command_id"
    ).fetchall()
    history = service.journal._db.execute(
        "SELECT id,command_id,state,recorded_at FROM command_history ORDER BY id"
    ).fetchall()
    return {
        "cursor": service.journal.applied_cursor,
        "identity": service.journal.identity(),
        "checkpoint": dict(checkpoint) if checkpoint is not None else None,
        "native": json.loads(json.dumps(service.world.checkpoint(), default=lambda value: value.tolist())),
        "commands": [dict(row) for row in commands],
        "history": [dict(row) for row in history],
    }
