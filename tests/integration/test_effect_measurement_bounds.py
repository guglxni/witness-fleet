"""Regression coverage for bounded native-effect measurements.

Tampering below alters transport reads layered over real native service runs;
it does not synthesize mission evidence or native measurements.
"""
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from test_native_execution_window import recovery_command
from test_service_admission import control

from services.simulator.service import SimulatorService
from services.simulator.stability import StabilityWindowCollector
from witness_fleet.domain import (
    ActionProposal,
    AuthorizationResult,
    Claim,
    CommandIntent,
    DispatchEvent,
    SkillKind,
    VersionVector,
    canonical_json_hash,
)


class TamperedTransport:
    """Expose real service state with explicitly altered transport responses."""

    def __init__(self, service):
        self.service = service
        self.tamper = None

    def __getattr__(self, name):
        return getattr(self.service, name)

    def command(self, command_id):
        receipt = deepcopy(self.service.command(command_id))
        if self.tamper is not None:
            self.tamper(receipt)
        return receipt

    def observations(self):
        return self.service.observations()


def _service(tmp_path, episode):
    service = SimulatorService(tmp_path)
    service.create_episode(episode, 'SC-001', 3)
    service.load_payload('courier', 'parcel')
    service.receive(control('fence', 1, 'FENCE_INSTALL', {
        'task_id': 'task', 'task_fence': 1, 'resource_fences': {'corridor': 1},
    }))
    return service


def _command(service, kind, robot, parameters, effects):
    now = datetime.now(UTC)
    tick = service.status()['world_tick']
    sequence = service.status()['last_sequence'] + 1
    versions = VersionVector(graph_version=0, policy_epoch=0, coordinator_epoch=0)
    proposal = ActionProposal(id=f'proposal-{kind}-{sequence}', robot_id=robot,
        task_id='task', kind=SkillKind(kind), parameters=parameters,
        expected_versions=versions, required_predicates=(),
        required_resource_ids=('corridor',), expected_effects=tuple(effects),
        corridor_id='corridor')
    claim = Claim(id='claim', task_id='task', robot_id=robot, holder_id='owner',
        coordinator_epoch=0, fence=1, resource_fences={'corridor': 1},
        lease_expires_at_utc=now + timedelta(hours=1),
        clock_domain='coordinator_epoch_utc_lease_v1', state='active')
    authorization = AuthorizationResult(authorization_id=f'auth-{kind}-{sequence}',
        status='ALLOW', reason_codes=(), witness_ids=('permit',), versions=versions,
        action_payload_hash=canonical_json_hash(proposal), valid_until_tick=tick + 10000,
        claim_id=claim.id, task_id='task', robot_id=robot, fence=1,
        resource_fences=claim.resource_fences, governance_integrity_version=0)
    command = CommandIntent(command_id=f'{kind}-command-{sequence}', proposal=proposal,
        payload_hash=canonical_json_hash(proposal), claim_id=claim.id, fence=1,
        resource_fences=claim.resource_fences, authorization_id=authorization.authorization_id,
        policy_epoch=0, coordinator_epoch=0, dispatch_sequence=sequence,
        effective_world_tick=tick, authorization=authorization)
    wire = command.model_dump(mode='json')
    event = DispatchEvent(id=command.command_id, sequence=sequence,
        coordinator_epoch=0, kind='COMMAND', effective_world_tick=tick,
        payload=wire, payload_hash=canonical_json_hash(wire))
    return event, command


def _start(service, kind, robot, parameters, effects):
    event, command = _command(service, kind, robot, parameters, effects)
    result = service.receive(event)
    assert result['command_state'] == 'RUNNING', result
    return event, command


def _advance_until_done(service, command, limit=2000):
    for _ in range(limit):
        receipt = service.command(command.command_id)
        if receipt['state'] != 'RUNNING':
            return receipt
        service.advance(1)
    return service.command(command.command_id)


def _clear_corridor(service):
    """Run and check the real recovery actuator before travel/delivery fixtures."""
    event = recovery_command(service, deadline=2000)
    assert service.receive(event)['command_state'] == 'RUNNING'
    service.advance(1200)
    receipt = service.command(event.id)
    assert receipt['state'] == 'CONTROLLER_DONE', receipt
    assert receipt['native']['contact_count'] > 0
    assert receipt['native']['measured_displacement_m'] >= .75


def _delivery_fixture(tmp_path, episode):
    service = _service(tmp_path, episode)
    _clear_corridor(service)
    _, park = _start(service, 'travel', 'scout', {
        'target_x': -3.5, 'target_y': -.55, 'timeout_ticks': 2000,
        'execution_until_tick': service.status()['world_tick'] + 2000,
    }, ['arrived'])
    assert _advance_until_done(service, park)['state'] == 'CONTROLLER_DONE'
    _, approach = _start(service, 'travel', 'courier', {
        'target_x': -3.5, 'target_y': 0, 'timeout_ticks': 2000,
        'execution_until_tick': service.status()['world_tick'] + 2000,
    }, ['arrived'])
    assert _advance_until_done(service, approach)['state'] == 'CONTROLLER_DONE'
    _, delivery = _start(service, 'deliver', 'courier', {
        'target_x': 4, 'target_y': 0, 'timeout_ticks': 2000,
        'execution_until_tick': service.status()['world_tick'] + 2000,
    }, ['delivered'])
    receipt = _advance_until_done(service, delivery)
    return service, delivery, receipt


def _collect_window(service, command):
    from services.simulator.stability import StabilityWindowCollector

    collector = StabilityWindowCollector(service, command)
    start = service.status()['world_tick']
    window = None
    for index in range(10):
        if index:
            service.advance(1)
        window = collector.collect()
    assert window is not None and window.start_tick == start
    return window


def test_native_stability_window_is_ten_consecutive_read_only_public_samples(tmp_path):

    service = _service(tmp_path, 'stable-window')
    try:
        _, command = _start(service, 'travel', 'scout', {
            'target_x': -3.5, 'target_y': -.55, 'timeout_ticks': 2000,
            'execution_until_tick': 2000,
        }, ['arrived'])
        service.advance(500)
        assert service.command(command.command_id)['state'] == 'CONTROLLER_DONE'
        from services.simulator.stability import StabilityWindowCollector

        collector = StabilityWindowCollector(service, command)
        window = None
        start = service.status()['world_tick']
        for index in range(10):
            if index:
                service.advance(1)
            window = collector.collect()
        assert window is not None and window.start_tick == start
        assert window.sample_count == 10
        assert window.start_tick == 500
        assert window.end_tick == 509
        assert window.max_target_error_m < .05
        assert window.max_speed_m_s <= .01
        assert window.command_id == command.command_id
        assert window.command_payload_hash == canonical_json_hash(command)
        assert window.tick_seconds == pytest.approx(float(service.world.model.opt.timestep))
    finally:
        service.close()


def test_travel_projection_requires_current_exact_command_stability_window(tmp_path):
    from witness_fleet.runtime.command_effects import capture_command_effects

    service = _service(tmp_path, 'window-gate')
    try:
        _, command = _start(service, 'travel', 'scout', {
            'target_x': -3.5, 'target_y': -.55, 'timeout_ticks': 2000,
            'execution_until_tick': 2000,
        }, ['arrived'])
        service.advance(500)
        assert service.command(command.command_id)['state'] == 'CONTROLLER_DONE'
        assert capture_command_effects(service, command=command,
                                       now_utc=datetime.now(UTC)) == ()
        from services.simulator.stability import StabilityWindowCollector

        collector = StabilityWindowCollector(service, command)
        window = None
        start = service.status()['world_tick']
        for index in range(10):
            if index:
                service.advance(1)
            window = collector.collect()
        assert window is not None and window.start_tick == start
        effects = capture_command_effects(service, command=command,
                                          now_utc=datetime.now(UTC),
                                          stability_window=window)
        assert [effect.predicate for effect in effects] == ['arrived']
        service.advance(1)
        assert capture_command_effects(service, command=command,
                                       now_utc=datetime.now(UTC),
                                       stability_window=window) == ()
    finally:
        service.close()
def test_real_native_delivery_emits_delivered_with_measured_window(tmp_path):
    from witness_fleet.runtime.command_effects import capture_command_effects

    service, command, receipt = _delivery_fixture(tmp_path, 'native-delivery-positive')
    try:
        assert receipt['state'] == 'CONTROLLER_DONE', receipt
        assert receipt['native']['result']['postcondition']['payload_in_delivery_zone'] is True
        assert service.observations()['robots']['courier']['payload']['delivery_zone'] is True
        window = _collect_window(service, command)
        effects = capture_command_effects(service, command=command,
            now_utc=datetime.now(UTC), stability_window=window)
        assert [effect.predicate for effect in effects] == ['delivered']
        assert effects[0].quality['payload_id'] == 'parcel'
        assert effects[0].quality['delivery_identity_binding']['pose_match_tolerance_m'] == .005
        assert effects[0].visibility == window.visibility_state
    finally:
        service.close()


@pytest.mark.parametrize('tamper', [
    'payload_pose_shape', 'payload_pose_nonfinite', 'zone_nonfinite',
    'negative_radius', 'height_nonfinite', 'wrong_target',
    'wrong_robot', 'wrong_kind', 'wrong_accepted_tick', 'wrong_receipt_hash',
    'result_shape', 'postcondition_shape', 'false_flag', 'missing_flag',
])
def test_delivery_malformed_or_mismatched_native_transport_fails_closed(tmp_path, tamper):
    from witness_fleet.runtime.command_effects import capture_command_effects

    raw, command, receipt = _delivery_fixture(tmp_path, f'delivery-{tamper}')
    service = TamperedTransport(raw)
    try:
        assert receipt['state'] == 'CONTROLLER_DONE', receipt
        from services.simulator.stability import StabilityWindowCollector

        collector = StabilityWindowCollector(service, command)
        window = None
        start = service.status()['world_tick']
        for index in range(10):
            if index:
                service.advance(1)
            window = collector.collect()
        assert window is not None and window.start_tick == start

        def alter(response):
            native = response['native']
            if tamper == 'wrong_receipt_hash':
                response['payload_hash'] = 'transport-tamper'
            elif tamper == 'wrong_robot':
                native['robot_id'] = 'scout'
            elif tamper == 'wrong_kind':
                native['kind'] = 'travel'
            elif tamper == 'wrong_accepted_tick':
                native['accepted_tick'] += 1
            else:
                result = native['result']
                if tamper == 'result_shape':
                    native['result'] = []
                    return
                post = result['postcondition']
                if tamper == 'postcondition_shape':
                    result['postcondition'] = 'bad-shape'
                elif tamper == 'false_flag':
                    post['payload_in_delivery_zone'] = False
                elif tamper == 'missing_flag':
                    post.pop('payload_in_delivery_zone')
                elif tamper == 'payload_pose_shape':
                    post['payload_pose'] = [1, 2]
                elif tamper == 'payload_pose_nonfinite':
                    post['payload_pose'][0] = float('nan')
                elif tamper == 'zone_nonfinite':
                    post['zone_center'][1] = float('inf')
                elif tamper == 'negative_radius':
                    post['zone_radius_m'] = -0.1
                elif tamper == 'height_nonfinite':
                    post['relative_height_m'] = float('nan')
                elif tamper == 'wrong_target':
                    native['target'] = [3.9, 0.0]

        service.tamper = alter
        assert capture_command_effects(service, command=command,
                                       now_utc=datetime.now(UTC),
                                       stability_window=window) == ()
    finally:
        raw.close()


@pytest.mark.parametrize('tamper', [
    'range_nonfinite', 'sensor_shape', 'visibility_shape', 'range_negative',
    'sensor_expiry', 'visibility_fraction',
])
def test_inspection_malformed_or_insufficient_native_sensor_fails_closed(tmp_path, tamper):
    from witness_fleet.runtime.command_effects import capture_command_effects

    raw = _service(tmp_path, f'inspection-{tamper}')
    service = TamperedTransport(raw)
    try:
        _, command = _start(service, 'inspect', 'scout', {
            'timeout_ticks': 100, 'execution_until_tick': 100,
        }, ['inspected'])
        raw.advance(1)
        assert raw.command(command.command_id)['state'] == 'CONTROLLER_DONE'

        def alter(receipt):
            measured = receipt['native']['result']
            if tamper == 'range_nonfinite':
                measured['ranges_m'][0] = float('inf')
            elif tamper == 'sensor_shape':
                measured['sensor'] = []
            elif tamper == 'visibility_shape':
                measured['visibility'] = {'state': 'insufficient', 'fraction': .1}
            elif tamper == 'range_negative':
                measured['ranges_m'][0] = -1
            elif tamper == 'sensor_expiry':
                measured['sensor']['expires_tick'] = raw.status()['world_tick']
            elif tamper == 'visibility_fraction':
                measured['visibility']['fraction'] = 2

        service.tamper = alter
        assert capture_command_effects(service, command=command,
                                       now_utc=datetime.now(UTC)) == ()
    finally:
        raw.close()

@pytest.mark.parametrize('tamper', ['sensor_shape', 'visibility_fraction', 'ranges_shape'])
def test_stability_collector_rejects_malformed_public_sample_transport(tmp_path, tamper):
    raw = _service(tmp_path, f'stability-malformed-{tamper}')
    service = TamperedTransport(raw)
    try:
        _, command = _start(service, 'travel', 'scout', {
            'target_x': -3.5, 'target_y': -.55, 'timeout_ticks': 2000,
            'execution_until_tick': 2000,
        }, ['arrived'])
        raw.advance(500)
        assert raw.command(command.command_id)['state'] == 'CONTROLLER_DONE'
        original = service.observations

        def observations():
            result = deepcopy(original())
            sample = result['robots']['scout']
            if tamper == 'sensor_shape':
                sample['sensor'] = []
            elif tamper == 'visibility_fraction':
                sample['visibility']['fraction'] = 1.5
            else:
                sample['ranges_m'] = 'not-a-range-vector'
            return result

        service.observations = observations
        collector = StabilityWindowCollector(service, command)
        tick = raw.status()['world_tick']
        assert collector.collect() is None
        assert collector.sample_count == 0
        assert raw.status()['world_tick'] == tick
    finally:
        raw.close()


def test_stability_window_rejects_intermediate_sensor_config_change(tmp_path):
    raw = _service(tmp_path, 'stability-config-continuity')
    service = TamperedTransport(raw)
    try:
        _, command = _start(service, 'travel', 'scout', {
            'target_x': -3.5, 'target_y': -.55, 'timeout_ticks': 2000,
            'execution_until_tick': 2000,
        }, ['arrived'])
        raw.advance(500)
        assert raw.command(command.command_id)['state'] == 'CONTROLLER_DONE'
        original = service.observations
        collector = StabilityWindowCollector(service, command)
        window = None
        for index in range(10):
            if index:
                raw.advance(1)
            if index == 4:
                def changed_config():
                    result = deepcopy(original())
                    result['robots']['scout']['sensor']['config_hash'] = 'transport-altered-config'
                    return result
                service.observations = changed_config
            else:
                service.observations = original
            window = collector.collect()

        assert window is None
    finally:
        raw.close()


def test_projection_rejects_terminal_visibility_changed_after_window_capture(tmp_path):
    from witness_fleet.runtime.command_effects import capture_command_effects

    raw, command, receipt = _delivery_fixture(tmp_path, 'delivery-visibility-binding')
    service = TamperedTransport(raw)
    try:
        assert receipt['state'] == 'CONTROLLER_DONE'
        window = _collect_window(service, command)
        original = service.observations

        def observations():
            result = deepcopy(original())
            result['robots']['courier']['visibility'] = {'state': 'visible', 'fraction': .9}
            return result

        service.observations = observations
        assert capture_command_effects(service, command=command,
            now_utc=datetime.now(UTC), stability_window=window) == ()
    finally:
        raw.close()



def test_stability_collector_rejects_nonconsecutive_native_ticks(tmp_path):
    from services.simulator.stability import StabilityWindowCollector

    service = _service(tmp_path, 'stability-gap')
    try:
        _, command = _start(service, 'travel', 'scout', {
            'target_x': -3.5, 'target_y': -.55, 'timeout_ticks': 2000,
            'execution_until_tick': 2000,
        }, ['arrived'])
        service.advance(500)
        collector = StabilityWindowCollector(service, command)
        assert collector.collect() is None
        service.advance(2)
        assert collector.collect() is None
        assert collector.sample_count == 1
    finally:
        service.close()


def test_stability_collector_fails_closed_on_malformed_receipt_transport(tmp_path):
    raw = _service(tmp_path, 'stability-malformed-receipt')
    service = TamperedTransport(raw)
    try:
        _, command = _start(service, 'travel', 'scout', {
            'target_x': -3.5, 'target_y': -.55, 'timeout_ticks': 2000,
            'execution_until_tick': 2000,
        }, ['arrived'])
        raw.advance(500)
        assert raw.command(command.command_id)['state'] == 'CONTROLLER_DONE'
        def malformed_command(command_id):
            return []

        service.command = malformed_command
        collector = StabilityWindowCollector(service, command)
        assert collector.collect() is None
        assert collector.sample_count == 0
    finally:
        raw.close()


def test_stability_window_is_bound_to_same_service_command_and_tick(tmp_path):
    from witness_fleet.runtime.command_effects import capture_command_effects

    service = _service(tmp_path, 'stability-binding')
    try:
        _, command = _start(service, 'travel', 'scout', {
            'target_x': -3.5, 'target_y': -.55, 'timeout_ticks': 2000,
            'execution_until_tick': 2000,
        }, ['arrived'])
        service.advance(500)
        from services.simulator.stability import StabilityWindowCollector

        collector = StabilityWindowCollector(service, command)
        window = None
        start = service.status()['world_tick']
        for index in range(10):
            if index:
                service.advance(1)
            window = collector.collect()
        assert window is not None and window.start_tick == start
        _, other_command = _command(service, 'travel', 'scout', {
            'target_x': -3.5, 'target_y': -.55, 'timeout_ticks': 2000,
            'execution_until_tick': 2000,
        }, ['arrived'])
        assert capture_command_effects(service, command=other_command,
                                       now_utc=datetime.now(UTC),
                                       stability_window=window) == ()
        service.advance(1)
        assert capture_command_effects(service, command=command,
                                       now_utc=datetime.now(UTC),
                                       stability_window=window) == ()
    finally:
        service.close()
