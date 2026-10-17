"""Native telemetry can be retained through the actual canonical append schema."""
from datetime import UTC, datetime

import pytest
from isolated_console_fixture import isolated_console_graph  # noqa: F401
from isolated_runtime_fixture import isolated_runtime_graph  # noqa: F401

from services.simulator.service import SimulatorService
from witness_fleet.runtime.sensing import capture_evidence


def test_retain_native_observations_roundtrip_and_idempotency(isolated_console_graph, tmp_path):  # noqa: F811
    from witness_fleet.runtime.observation_store import retain_observations

    graph = isolated_console_graph
    graph.append_node('Episode', 'sensor-roundtrip', {'scenario_family': 'SC-001'})
    service = SimulatorService(tmp_path)
    try:
        service.create_episode('sensor-roundtrip', 'SC-001', 3)
        service.load_payload('courier', 'parcel')
        observations = capture_evidence(service, tenant_id=graph.tenant_id,
            corridor_id='corridor', release_id='release', now_utc=datetime.now(UTC))
        # Native command effects include nested immutable pose/measurement maps.
        from witness_fleet.domain import Observation
        data = observations[0].model_dump(mode='json')
        data['quality']['nested_measurement'] = {'pose': {'x': 1.25}, 'samples': [1, 2]}
        observations = (Observation.model_validate(data),) + observations[1:]
        retained = retain_observations(graph, observations, episode_id='sensor-roundtrip')
        assert retained == observations
        before = graph.read_version_root()
        assert retain_observations(graph, observations, episode_id='sensor-roundtrip') == observations
        assert graph.read_version_root() == before
        nodes = graph.read_snapshot(labels=['Observation'])['nodes']
        assert {n['id'] for n in nodes} == {o.id for o in observations}
        with pytest.raises(ValueError):
            retain_observations(graph, observations, episode_id='wrong-episode')
        assert graph.read_version_root() == before
    finally:
        service.close()
