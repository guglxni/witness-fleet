"""Operator mission lifecycle must pause for explicit release; inspection stays inert."""
import uuid

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401
from test_mission_execution import mission_console  # noqa: F401


def test_mission_controller_runs_to_approval_then_measured_delivery(mission_console):  # noqa: F811
    from witness_fleet.runtime.mission import MissionController

    owner = mission_console
    controller = MissionController(owner.graph, owner.sources, owner.simulator)
    first = controller.run('run-' + uuid.uuid4().hex)
    assert first['approval_required'] is True
    assert first['mission_phase'] == 'awaiting_owner_release'
    assert first['operator_mode'] == 'local_mission'
    assert first['metrics']['delivery_completed'] == 0
    assert len(first['commands']) == 4
    before = controller.graph.read_version_root()
    again = controller.run('still-waiting')
    assert again['approval_required'] is True
    assert len(again['commands']) == 4
    assert controller.graph.read_version_root() == before
    with pytest.raises(ValueError, match='epoch'):
        controller.approve_release(first['release_id'], first['policy_epoch'] + 1, 'stale')
    controller.approve_release(first['release_id'], first['policy_epoch'], 'explicit-release')
    final = controller.run('complete')
    assert final['mission_phase'] == 'complete'
    assert len(final['commands']) == 7
    assert all(t['state'] == 'VERIFIED' for t in final['tasks'])
    assert final['metrics']['delivery_completed'] == 1
    assert not final['approval_required']
    assert controller.run('idempotent-complete')['commands'] == final['commands']


def test_mission_controller_refuses_premature_owner_release(mission_console):  # noqa: F811
    from witness_fleet.runtime.mission import MissionController

    owner = mission_console
    controller = MissionController(owner.graph, owner.sources, owner.simulator)
    before = controller.graph.read_version_root()
    with pytest.raises(ValueError, match='verification|prerequisite'):
        controller.approve_release(owner.manifest['release_id'], before['policy_epoch'], 'premature')
    assert controller.graph.read_version_root() == before
    assert not owner.simulator.status()['started_commands']


def test_inspection_coordinator_has_no_implicit_motion_interface(mission_console):  # noqa: F811
    assert not hasattr(mission_console, 'run')
    assert not hasattr(mission_console, 'approve_release')
