"""Scoped fleet evidence keeps the sensing robot's identity, including peer samples."""

from datetime import UTC, datetime

import pytest

from services.simulator.service import SimulatorService
from witness_fleet.runtime.sensing import capture_evidence


def test_initial_ray_samples_preserve_unknown_and_observer_scope(tmp_path):
    service = SimulatorService(tmp_path)
    try:
        service.create_episode('sensing-episode', 'SC-001', 3)
        service.load_payload('courier', 'sensing-parcel')
        evidence = capture_evidence(service, tenant_id='demo', corridor_id='declared-corridor',
                                    release_id='declared-release', now_utc=datetime.now(UTC))
        fit = {(item.robot_id, item.scope['robot_type']): item for item in evidence
               if item.predicate == 'courier_fit'}
        scout = fit[('scout', 'courier')]
        assert scout.value is False
        assert scout.subject_id == 'declared-corridor'
        assert scout.scope['release_id'] == 'declared-release'
        assert scout.pose.x == -3.8
        assert scout.expires_tick == 50
        assessment = next(o for o in evidence if o.robot_id == 'recovery' and o.predicate == 'obstacle_assessed')
        assert assessment.value is True
        assert assessment.scope['robot_type'] == 'recovery'
        courier = fit[('courier', 'courier')]
        assert courier.value is None  # No ray return is not a positive fit.
        assert courier.visibility == 'insufficient'
        assert all(item.episode_id == 'sensing-episode' and item.sensor_config_hash for item in evidence)
        assert service.status()['world_tick'] == 0
        assert not any(item.predicate == 'recovery_verified' and item.value is True for item in evidence)
    finally:
        service.close()


def test_positive_post_recovery_projection_uses_fresh_ray_sample_not_controller_flag(tmp_path):
    service = SimulatorService(tmp_path)
    try:
        service.create_episode('post-recovery-sensing', 'SC-001', 3)
        service.load_payload('courier', 'post-recovery-parcel')
        assert service.world is not None
        # Native fixture exercise only, not authorization acceptance.
        service.world.start_skill('recovery', 'recover', {'timeout_ticks': 2000})
        for _ in range(2000):
            service.world.step()
            if service.world.skill_status('recovery')['status'] == 'done':
                break
        assert service.world.skill_status('recovery')['status'] == 'done'
        evidence = capture_evidence(service, tenant_id='demo', corridor_id='corridor',
                                    release_id='release', now_utc=datetime.now(UTC))
        sample = next(o for o in evidence if o.robot_id == 'scout' and o.predicate == 'courier_fit')
        assert sample.value is True
        assert sample.world_tick == service.status()['world_tick']
        assert sample.expires_tick == sample.world_tick + 50
        assert sample.visibility == 'visible'
        assert not any(o.predicate == 'recovery_verified' for o in evidence)
    finally:
        service.close()


def test_mixed_sensor_ticks_are_rejected(tmp_path, monkeypatch):
    service = SimulatorService(tmp_path)
    try:
        service.create_episode('mixed-frame', 'SC-001', 3)
        service.load_payload('courier', 'mixed-frame-parcel')
        sample = service.observations()
        sample['robots']['scout']['world_tick'] = 1
        monkeypatch.setattr(service, 'observations', lambda: sample)
        with pytest.raises(ValueError, match='frame identity'):
            capture_evidence(service, tenant_id='demo', corridor_id='corridor',
                             release_id='release', now_utc=datetime.now(UTC))
    finally:
        service.close()


def test_caller_cannot_label_an_unloaded_courier_as_loaded(tmp_path):
    service = SimulatorService(tmp_path)
    try:
        service.create_episode('empty-courier', 'SC-001', 3)
        with pytest.raises(ValueError, match='loaded courier'):
            capture_evidence(service, tenant_id='demo', corridor_id='corridor',
                             release_id='release', now_utc=datetime.now(UTC))
    finally:
        service.close()
