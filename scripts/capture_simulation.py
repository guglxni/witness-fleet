"""Capture native component measurements, explicitly not integrated fleet evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import mujoco
import numpy as np

from services.simulator import FacilityWorld


def _json(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {k: _json(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(v) for v in value]
    return value


def capture(output, *, seed=3, render=True):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    world = FacilityWorld(seed=seed, scenario='SC-001')
    renderer = writer = None
    samples = []
    try:
        if render:
            import imageio.v2 as imageio
            from PIL import Image, ImageDraw
            renderer = mujoco.Renderer(world.model, height=360, width=640)
            writer = imageio.get_writer(out / 'recovery.mp4', fps=20, codec='libx264', quality=8)
            camera = mujoco.MjvCamera()
            camera.lookat[:] = [0, .2, 0]
            camera.distance = 15
            camera.azimuth = 90
            camera.elevation = -75

        start = world.start_skill('recovery', 'recover',
                                  {'target_displacement_m': .75, 'timeout_ticks': 2000})
        if start['status'] != 'accepted':
            raise RuntimeError(f'native recovery not accepted: {start}')
        for tick in range(2000):
            world.step()
            state = world.skill_status('recovery')
            if tick % 5 == 0:
                samples.append({'tick': world.world_tick, 'poses': world.poses(),
                                'obstruction_position': world._object_position().tolist(),
                                'status': state['status'], 'phase': state.get('phase'),
                                'contact_count': state['contact_count']})
                if renderer is not None:
                    renderer.update_scene(world.data, camera=camera)
                    image = Image.fromarray(renderer.render())
                    draw = ImageDraw.Draw(image)
                    draw.rectangle((0, 0, 640, 42), fill=(12, 18, 26))
                    draw.text((12, 6), 'NATIVE MUJOCO - EVALUATOR VIEW - NOT FLEET ACCEPTANCE', fill='white')
                    draw.text((12, 24), f'Tick {world.world_tick}  |  contacts {state["contact_count"]}  |  phase {state.get("phase")}', fill=(110, 230, 200))
                    writer.append_data(np.asarray(image))
                    if tick == 0:
                        image.save(out / 'first-frame.png')
                    image.save(out / 'last-frame.png')
            if state['status'] in {'done', 'failed', 'held', 'timed_out'}:
                break
        if state['status'] != 'done':
            raise RuntimeError(f'native recovery failed: {_json(state)}')
        recovery_state = state
        recovery_tick = world.world_tick
        recovery_poses = world.poses()
        for target in (-4.0, -6.7):
            world.start_skill('scout', 'travel', {'target_x':target,'target_y':-.55,'timeout_ticks':2000})
            for _ in range(2000):
                world.step()
                if world.skill_status('scout')['status'] not in {'accepted','running'}:
                    break
            if world.skill_status('scout')['status'] != 'done':
                raise RuntimeError('scout failed to clear the loaded courier route')
        world.load_payload('courier','capture-payload')
        world.start_skill('courier','deliver',{'target_x':4.0,
                                              'target_y':0.0,'timeout_ticks':2000})
        for _ in range(2000):
            world.step()
            if world.skill_status('courier')['status'] not in {'accepted','running'}:
                break
        delivery_state = world.skill_status('courier')
        delivery = world.inspect('courier')['payload']
        if delivery_state['status'] != 'done' or delivery.get('delivery_zone') is not True:
            raise RuntimeError('native loaded east-side delivery postcondition failed')
        root = Path(__file__).resolve().parents[1]
        sources = ['services/simulator/world.py', 'services/simulator/sensors.py',
                   'services/simulator/assets/facility.xml']
        report = {'scope': 'native_component_only_not_integrated_fleet',
                  'max_contact_force_n': float(state.get('max_contact_force_n', 0)),
                  'carton_displacement_m': float(np.linalg.norm(world._object_position()[:2] - world._obstruction_initial[:2])),
                  'status': 'native-component-measurement', 'seed': seed,
                  'scenario': 'SC-001', 'world_tick': world.world_tick,
                  'hidden_state_access': 'evaluator-only', 'fleet_acceptance': False,
                  'recovery': _json(recovery_state), 'recovery_world_tick': recovery_tick,
                  'recovery_poses': recovery_poses,
                  'delivery': {'status':delivery_state['status'],
                               'position': [delivery['observed_pose'][axis] for axis in ('x','y','z')],
                               **delivery},
                  'sim_time_s': float(world.data.time),
                  'poses': world.poses(), 'obstruction_position': world._object_position().tolist(),
                  'native_sources': {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in sources},
                  'limitations': ['Synthetic primitive physics, not real robot certification',
                                  'Direct component harness, not graph-authorized motion',
                                  'Video shows recovery only; JSON includes actual native loaded crossing',
                                  'No graph-integrated fleet or process-kill coordinator acceptance']}
        (out / 'measurements.json').write_text(json.dumps(report, indent=2) + '\n')
        (out / 'trajectory.json').write_text(json.dumps(samples, indent=2) + '\n')
        return report
    finally:
        if writer is not None:
            writer.close()
        if renderer is not None:
            renderer.close()
        world.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--seed', type=int, default=3)
    parser.add_argument('--no-render', action='store_true')
    args = parser.parse_args()
    print(json.dumps(capture(args.output, seed=args.seed, render=not args.no_render), indent=2))
