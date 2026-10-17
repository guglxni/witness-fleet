from services.simulator import FacilityWorld


def test_corrupt_checkpoint_does_not_partially_mutate_physics():
    import numpy as np
    import pytest
    with FacilityWorld(episode_id='same') as world:
        saved = world.checkpoint()
        before = world.data.qpos.copy()
        saved['qpos'] = before + 1
        saved['qvel'] = np.zeros((1,))
        with pytest.raises(ValueError):
            world.restore(saved)
        assert np.array_equal(world.data.qpos, before)


def test_checkpoint_tick_cannot_be_a_boolean():
    import pytest
    with FacilityWorld(episode_id='same') as world:
        saved = world.checkpoint()
        saved['world_tick'] = True
        with pytest.raises(ValueError):
            world.restore(saved)
