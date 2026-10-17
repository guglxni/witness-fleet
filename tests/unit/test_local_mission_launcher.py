"""Safety contracts for the reproducible local demo launcher (no Docker side effects)."""
import argparse
from pathlib import Path

import pytest

from scripts import run_local_mission


def test_launcher_uses_dynamic_loopback_bounded_retained_server():
    command = run_local_mission.graph_command('wf-owned-test')
    assert command[0:3] == ['docker', 'run', '-d']
    assert command[command.index('-p') + 1] == '127.0.0.1::6379'
    assert command[command.index('--memory') + 1] == '512m'
    assert command[command.index('--cpus') + 1] == '1'
    assert command[command.index('--restart') + 1] == 'no'
    assert '--rm' not in command
    assert command[command.index('-v') + 1] == 'wf-owned-test:/var/lib/falkordb/data'
    assert '@sha256:' in command[-1]


def test_launcher_never_reuses_retained_run_directory(tmp_path):
    root = tmp_path / 'retained'
    root.mkdir()
    (root / 'keep').write_text('evidence')
    with pytest.raises(ValueError, match='new empty'):
        run_local_mission.prepare_root(root)
    assert (root / 'keep').read_text() == 'evidence'


def test_launcher_accepts_new_real_directory(tmp_path):
    root = run_local_mission.prepare_root(tmp_path / 'new')
    assert root.is_dir()
    link = tmp_path / 'link'
    link.symlink_to(root)
    with pytest.raises(ValueError, match='symlink'):
        run_local_mission.prepare_root(link)


def test_launcher_binds_ui_only_to_loopback_and_preserves_defaults():
    args = run_local_mission.parser().parse_args(['--run-dir', '/tmp/new'])
    assert isinstance(args, argparse.Namespace)
    assert args.port == 8095
    assert not hasattr(args, 'host')
    assert isinstance(args.run_dir, Path)
