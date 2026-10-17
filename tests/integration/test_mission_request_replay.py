"""Retry unknown HTTP action responses without advancing a second native task."""
from concurrent.futures import ThreadPoolExecutor

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401
from test_mission_execution import mission_console  # noqa: F401

from witness_fleet.runtime.mission import MissionController


def test_lost_step_response_replays_across_controller_reopen(mission_console):  # noqa: F811
    owner = mission_console
    controller = MissionController(owner.graph, owner.sources, owner.simulator)
    first = controller.step(1, 'lost-step-response')
    assert len(first['commands']) == 1
    root = owner.graph.read_version_root()
    identity = owner.simulator.journal.identity()
    tick = owner.simulator.world.world_tick
    # No response reaches the client. Its identical retry must not execute recover.
    assert controller.step(1, 'lost-step-response') == first
    # Durable identity, not just a dict in the old controller instance.
    reopened = MissionController(owner.graph, owner.sources, owner.simulator)
    assert reopened.step(1, 'lost-step-response') == first
    assert owner.graph.read_version_root() == root
    assert owner.simulator.journal.identity() == identity
    assert owner.simulator.world.world_tick == tick
    assert len(owner.state()['commands']) == 1


def test_unknown_request_blocks_new_ids_after_side_effect_and_reopen(mission_console, monkeypatch):  # noqa: F811
    owner = mission_console
    controller = MissionController(owner.graph, owner.sources, owner.simulator)
    real_next = controller._next

    def response_crash():
        real_next()
        raise RuntimeError('after physical task, before recording response')

    monkeypatch.setattr(controller, '_next', response_crash)
    with pytest.raises(RuntimeError, match='after physical'):
        controller.step(1, 'pending-request')
    assert owner.simulator.status()['held'] is True
    before = owner.graph.read_version_root()
    tick = owner.simulator.world.world_tick
    reopened = MissionController(owner.graph, owner.sources, owner.simulator)
    for identity in ('pending-request', 'new-request-cannot-bypass'):
        with pytest.raises(ValueError, match='unknown|unresolved'):
            reopened.step(1, identity)
    assert owner.graph.read_version_root() == before
    assert owner.simulator.world.world_tick == tick
    assert len(owner.state()['commands']) == 1


def test_concurrent_same_step_and_conflicts_advance_once(mission_console):  # noqa: F811
    owner = mission_console
    controller = MissionController(owner.graph, owner.sources, owner.simulator)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(controller.step, 1, 'same-event') for _ in range(2)]
        responses = [f.result() for f in futures]
    assert responses[0] == responses[1]
    assert len(owner.state()['commands']) == 1
    with pytest.raises(ValueError, match='conflict'):
        controller.step(2, 'same-event')
    with pytest.raises(ValueError, match='conflict'):
        controller.run('same-event')
    responses[0]['commands'].clear()
    assert len(controller.step(1, 'same-event')['commands']) == 1


def test_run_retry_after_owner_release_does_not_start_courier(mission_console):  # noqa: F811
    owner = mission_console
    controller = MissionController(owner.graph, owner.sources, owner.simulator)
    first = controller.run('recovery-run')
    controller.approve_release(first['release_id'], first['policy_epoch'], 'explicit-owner')
    before = owner.graph.read_version_root()
    assert controller.run('recovery-run') == first
    assert len(controller.state()['commands']) == 4
    assert owner.graph.read_version_root() == before
    assert controller.run('new-courier-run')['mission_phase'] == 'complete'
