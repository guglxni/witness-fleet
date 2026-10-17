"""Ensure installed CLI imports the native service without pytest's path shim."""
import os
import subprocess
import sys


def test_installed_native_service_import_works_outside_repo(tmp_path):
    environment = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}
    result = subprocess.run([sys.executable, '-c',
        'from services.simulator.world import FacilityWorld; '
        'world = FacilityWorld(seed=3); print(world.world_tick); world.close()'],
        cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == '0'
