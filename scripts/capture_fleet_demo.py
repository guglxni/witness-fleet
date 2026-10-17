"""Capture an actual graph-authorized mission-v2 run, not a component simulation."""
from __future__ import annotations

import argparse
import hashlib
import json
import socket
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.simulator.service import SimulatorService  # noqa: E402, I001


SOURCE_FILES = (
    "scripts/capture_fleet_demo.py",
    "src/witness_fleet/api/mission.py",
    "src/witness_fleet/api/local.py",
    "src/witness_fleet/api/app.py",
    "src/witness_fleet/runtime/bootstrap.py",
    "src/witness_fleet/runtime/mission.py",
    "src/witness_fleet/runtime/coordinator.py",
    "src/witness_fleet/runtime/execution.py",
    "src/witness_fleet/runtime/approval.py",
    "src/witness_fleet/runtime/approval_writer.py",
    "src/witness_fleet/runtime/observation_store.py",
    "src/witness_fleet/runtime/storage.py",
    "src/witness_fleet/runtime/sensing.py",
    "src/witness_fleet/runtime/effects.py",
    "src/witness_fleet/runtime/command_effects.py",
    "src/witness_fleet/runtime/local_adapter.py",
    "src/witness_fleet/runtime/outcomes.py",
    "src/witness_fleet/policy/authorizer.py",
    "src/witness_fleet/graph/governance.py",
    "src/witness_fleet/graph/store.py",
    "src/witness_fleet/graph/migrations.py",
    "src/witness_fleet/ingestion/source_store.py",
    "src/witness_fleet/domain.py",
    "services/simulator/service.py",
    "services/simulator/world.py",
    "services/simulator/sensors.py",
    "services/simulator/stability.py",
    "services/simulator/journal.py",
    "services/simulator/assets/facility.xml",
)
TERMINAL_TASK_STATES = {"VERIFIED", "FAILED", "CANCELLED"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run and record the actual mission-v2 graph-authorized SC-001 fleet demo. "
            "The explicit demo-owner release is a configured scripted local action, "
            "not human-authenticated approval."
        )
    )
    parser.add_argument("--run-dir", required=True, type=Path,
                        help="new, empty retained run directory (all outputs stay inside)")
    parser.add_argument("--graph-port", required=True, type=int,
                        help="explicit independent loopback FalkorDB server port")
    parser.add_argument("--graph-user", default="default",
                        help="configured FalkorDB username (default: default)")
    parser.add_argument("--output", required=True, type=Path,
                        help="new MP4 output path inside --run-dir")
    parser.add_argument("--approve-demo-owner", action="store_true",
                        help="explicitly opt in to one scripted configured demo-owner release")
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--sample-every", type=int, default=5,
                        help="capture one native rendered frame per this many service ticks")
    return parser


def validate_args(args: argparse.Namespace) -> argparse.Namespace:
    if not args.approve_demo_owner:
        raise SystemExit("refusing motion without explicit --approve-demo-owner opt-in")
    if type(args.graph_port) is not int or not 1 <= args.graph_port <= 65535:
        raise ValueError("graph port must be an integer in [1, 65535]")
    if args.graph_port in {6380, 6381, 6382, 6383}:
        raise ValueError("graph port must not target any documented repository graph server")
    if not isinstance(args.graph_user, str) or not args.graph_user.strip():
        raise ValueError("graph username must be nonempty")
    if type(args.fps) is not int or not 1 <= args.fps <= 60:
        raise ValueError("fps must be an integer in [1, 60]")
    if type(args.sample_every) is not int or not 1 <= args.sample_every <= 1000:
        raise ValueError("sample interval must be an integer in [1, 1000]")

    run_dir = args.run_dir.expanduser().absolute()
    if run_dir.is_symlink():
        raise ValueError("run directory must be a real directory, not a symlink")
    if run_dir.exists():
        if not run_dir.is_dir():
            raise ValueError("run directory must be a real directory, not a symlink")
        if any(run_dir.iterdir()):
            raise ValueError("run directory must be empty to preserve retained data")
    else:
        run_dir.mkdir(parents=True, exist_ok=False)

    output_arg = args.output.expanduser()
    output = (output_arg if output_arg.is_absolute() else run_dir / output_arg).resolve()
    if not output.is_relative_to(run_dir.resolve()):
        raise ValueError("output must be inside the run directory")
    if output.exists():
        raise ValueError("output must not already exist")
    if output.suffix.lower() != ".mp4":
        raise ValueError("output must have an .mp4 extension")
    output.parent.mkdir(parents=True, exist_ok=True)
    args.run_dir, args.output = run_dir.resolve(), output
    return args


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _graph_port_is_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def project_state(state: dict, manifest: dict) -> dict:
    task_ids = set(manifest["task_ids"])
    commands = [
        {"command_id": command["command_id"], "task_id": command["task_id"],
         "kind": command.get("kind"), "state": command.get("state"),
         "reason_codes": command.get("reason_codes", []),
         "world_tick": command.get("world_tick"),
         "local_receipt": command.get("local_receipt"),
         "native_receipt": _receipt_projection(command.get("native_receipt", command.get("native")))}
        for command in state.get("commands", []) if command.get("task_id") in task_ids
    ]
    command_ids = {command["command_id"] for command in commands}
    events = []
    for event in state.get("events", []):
        try:
            subjects = json.loads(event.get("subject_ids_json", "[]"))
        except (TypeError, json.JSONDecodeError):
            subjects = []
        if any(subject in task_ids or subject in command_ids
               or subject == manifest["release_id"] for subject in subjects):
            events.append({key: event.get(key) for key in
                           ("event_id", "sequence", "kind", "payload_hash", "subject_ids_json",
                            "effective_world_tick", "coordinator_epoch")})
    observations = []
    for observation in state.get("observations", []):
        public = {key: value for key, value in observation.items()
                  if key not in {"pose", "raw_payload", "measurement"}}
        canonical = json.dumps(observation, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False, allow_nan=False)
        observations.append({**public, "payload_sha256": hashlib.sha256(
            canonical.encode("utf-8")).hexdigest()})
    sources = state.get("sources", [])
    return {
        "episode_id": state.get("episode_id"),
        "scenario": state.get("scenario"),
        "world_tick": state.get("world_tick"),
        "graph_version": state.get("graph_version"),
        "policy_epoch": state.get("policy_epoch"),
        "coordinator_epoch": state.get("coordinator_epoch"),
        "dispatch_sequence": state.get("dispatch_sequence"),
        "dispatch_ready": state.get("dispatch_ready"),
        "held": state.get("held"),
        "mission_phase": state.get("mission_phase"),
        "approval_required": state.get("approval_required"),
        "metrics": state.get("metrics"),
        "tasks": [task for task in state.get("tasks", []) if task.get("id") in task_ids],
        "commands": commands,
        "events": events,
        "sources": [{key: source.get(key) for key in
                     ("source_id", "revision_id", "normalized_hash", "source_kind")
                     if key in source} for source in sources],
        "observations": observations,
        "release_id": manifest["release_id"],
    }


def _receipt_projection(receipt):
    if not isinstance(receipt, dict):
        return receipt
    public_fields = {
        "status", "kind", "robot_id", "world_tick", "accepted_tick", "started_tick",
        "deadline_tick", "reason", "phase", "contact_count", "max_contact_force_n",
        "measured_displacement_m",
    }
    return {key: receipt[key] for key in public_fields if key in receipt}


def is_complete_mission(state: dict, *, held: bool | None = None) -> bool:
    tasks = state.get("tasks")
    commands = state.get("commands")
    metrics = state.get("metrics")
    if (not isinstance(tasks, list) or len(tasks) != 7
            or not all(isinstance(task, dict) for task in tasks)
            or not isinstance(commands, list) or len(commands) != 7
            or not all(isinstance(command, dict) for command in commands)):
        return False
    task_ids = [task.get("id") for task in tasks]
    command_task_ids = [command.get("task_id") for command in commands]
    return (
        all(task.get("state") == "VERIFIED" for task in tasks)
        and all(isinstance(task_id, str) and task_id for task_id in task_ids)
        and len(set(task_ids)) == 7
        and all(isinstance(task_id, str) and task_id for task_id in command_task_ids)
        and set(command_task_ids) == set(task_ids)
        and all(command.get("state") == "OUTCOME_VERIFIED" for command in commands)
        and all(command.get("native_receipt", {}).get("status") == "done" for command in commands)
        and all(command.get("local_receipt", {}).get("state") == "OUTCOME_VERIFIED"
                and command.get("local_receipt", {}).get("status") == "KNOWN"
                for command in commands)
        and state.get("approval_required") is False
        and state.get("mission_phase") == "complete"
        and isinstance(metrics, dict)
        and metrics.get("recovery_verified") == 1
        and metrics.get("delivery_completed") == 1
        and state.get("dispatch_ready") is True
        and state.get("held") is False
        and (held is None or held is False)
    )


def _phase_label(state: dict, *, pending_release: bool) -> str:
    phase = state.get("mission_phase")
    labels = {
        "recovery_and_verification": "GRAPH-AUTHORIZED TASKS: RECOVERY + VERIFICATION",
        "awaiting_owner_release": "PAUSED: CONFIGURED DEMO-OWNER RELEASE REQUIRED",
        "courier_delivery": "GRAPH-AUTHORIZED TASK: COURIER DELIVERY",
        "complete": "MISSION CONTROLLER REPORTS COMPLETE",
        "held": "MISSION HELD — inspect retained receipts",
    }
    label = labels.get(phase, "MISSION STATE: " + str(phase).upper())
    if pending_release:
        label += " | scripted configured owner; not human-authenticated"
    return label


class RecordingSimulatorService(SimulatorService):
    """Native service subclass; adds frames only after its ordinary advance call."""

    def __init__(self, root):
        super().__init__(root)
        self._recorder = None
        self._state_getter = None

    def attach_recorder(self, recorder, state_getter):
        self._recorder = recorder
        self._state_getter = state_getter

    def advance(self, ticks):
        result = super().advance(ticks)
        if (self._recorder is not None and self._state_getter is not None
                and result.get("world_tick", 0) % self._recorder.sample_every == 0):
            self._recorder.capture_frame(self._state_getter())
        return result

    def command(self, identifier):
        receipt = super().command(identifier)
        local = self.journal.receipt(identifier)
        receipt["local_receipt"] = {
            "status": local["status"],
            "command_id": local["command_id"],
            "payload_hash": local.get("payload_hash"),
            "state": local.get("state"),
            "event_id": local.get("event_id"),
            "last_known_state": local.get("last_known_state"),
            "reconciliation_state": local.get("reconciliation_state"),
        }
        return receipt


class NativeFrameRecorder:
    def __init__(self, world, output: Path, *, fps: int, sample_every: int):
        import imageio.v2 as imageio
        import mujoco

        self.world = world
        self.output = output
        self.fps = fps
        self.sample_every = sample_every
        self.renderer = mujoco.Renderer(world.model, height=360, width=640)
        self.camera = mujoco.MjvCamera()
        self.camera.lookat[:] = [0.0, 0.2, 0.0]
        self.camera.distance = 15.0
        self.camera.azimuth = 90
        self.camera.elevation = -75
        self.writer = imageio.get_writer(
            output, fps=fps, codec="libx264", quality=7,
            macro_block_size=None, ffmpeg_log_level="error",
        )
        self.frame_count = 0
        self.first_tick = None
        self.last_tick = None
        self.last_graph_version = None
        self._last_phase = None
        self.samples = []

    def capture_frame(self, state: dict, *, pending_release: bool = False):
        import numpy as np
        from PIL import Image, ImageDraw

        # The pixel data comes from the actual service-owned MuJoCo world only.
        self.renderer.update_scene(self.world.data, camera=self.camera)
        image = Image.fromarray(self.renderer.render())
        phase = _phase_label(state, pending_release=pending_release)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 640, 57), fill=(12, 18, 26))
        draw.text((12, 6), "WITNESS FLEET | GRAPH + NATIVE SIMULATOR", fill="white")
        draw.text((12, 24), phase[:96], fill=(110, 230, 200))
        draw.text((12, 42), f"tick {state.get('world_tick')} | graph v{state.get('graph_version')} | scenario SC-001",
                  fill=(235, 235, 235))
        self.writer.append_data(np.asarray(image))
        tick = state.get("world_tick")
        if not isinstance(tick, int) or tick < 0:
            raise ValueError("mission state lacks a valid world tick")
        if state.get("scenario") != "SC-001":
            raise ValueError("rendered mission state is not the expected SC-001 episode")
        if self.last_tick is not None and tick < self.last_tick:
            raise ValueError("world tick regressed while recording")
        if (self.last_graph_version is not None and state.get("graph_version") is not None
                and state["graph_version"] < self.last_graph_version):
            raise ValueError("graph version regressed while recording")
        self.last_graph_version = state.get("graph_version")
        self.last_tick = tick
        if self.first_tick is None:
            self.first_tick = tick
        if phase != self._last_phase or not self.samples:
            self.samples.append({"world_tick": tick, "caption": phase})
        self._last_phase = phase
        self.frame_count += 1

    def close(self):
        try:
            self.writer.close()
        finally:
            self.renderer.close()


def _write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def capture(args: argparse.Namespace) -> dict:
    """Run only against an explicitly selected loopback FalkorDB server."""
    args = validate_args(args)
    token = uuid.uuid4().hex
    graph_name = "wf_fleet_demo_" + token
    prefix = "fleet-demo-" + token
    simulation = graph = controller = recorder = None
    result = {"status": "failed", "graph_name": graph_name, "prefix": prefix,
              "scenario": "SC-001", "seed": 3,
              "graph_host": "127.0.0.1", "graph_port": args.graph_port}
    if not _graph_port_is_listening(args.graph_port):
        result["error"] = f"no graph server is listening on 127.0.0.1:{args.graph_port}"
        return result

    from witness_fleet.graph import GraphStore
    from witness_fleet.ingestion.source_store import SourceStore
    from witness_fleet.runtime.bootstrap import bootstrap
    from witness_fleet.runtime.mission import MissionController

    try:
        simulation = RecordingSimulatorService(args.run_dir / "sim")
        graph = GraphStore(host="127.0.0.1", port=args.graph_port, username=args.graph_user)
        graph.graph_name = graph_name
        graph._graph = graph._client.select_graph(graph_name)
        sources = SourceStore(args.run_dir / "sources")
        graph.initialize()
        manifest = bootstrap(graph, sources, prefix=prefix, scenario="SC-001", seed=3,
                             profile="mission-v2")
        result.update(
            episode_id=manifest["episode_id"], task_ids=manifest["task_ids"],
            release_id=manifest["release_id"], graph_namespace=graph_name,
            graph_host="127.0.0.1", graph_port=args.graph_port,
        )
        simulation.create_episode(manifest["episode_id"], "SC-001", 3)
        simulation.load_payload("courier", prefix + "-parcel")
        controller = MissionController(graph, sources, simulation)
        initial = controller.state()
        if initial.get("mission_phase") != "recovery_and_verification":
            raise RuntimeError("new mission did not begin in expected recovery-and-verification phase")
        recorder = NativeFrameRecorder(controller.simulator.world, args.output,
                                        fps=args.fps, sample_every=args.sample_every)
        simulation.attach_recorder(recorder, controller.state)

        # run() performs the actual graph checks, native dispatch, receipt handling,
        # observation retention and atomic outcome verification; no direct world.step().
        paused = controller.run("fleet-demo-run-" + token)
        recorder.capture_frame(paused, pending_release=paused.get("approval_required") is True)
        release_states = []
        release_recorded = False
        if paused.get("mission_phase") == "awaiting_owner_release" and args.approve_demo_owner:
            # The release is explicitly scripted under a configured local demo principal.
            # It is not a human-authentication ceremony or a real-world approval.
            recorder.capture_frame(paused, pending_release=True)
            release_recorded = True
            approved = controller.approve_release(
                manifest["release_id"], paused["policy_epoch"], "fleet-demo-owner-" + token)
            release_states.append(project_state(approved, manifest))
            if approved.get("mission_phase") != "courier_delivery":
                raise RuntimeError("actual configured demo-owner action did not release courier phase")
            final = controller.run("fleet-demo-delivery-" + token)
        else:
            final = paused
        final = controller.state()
        recorder.capture_frame(final)
        if recorder.frame_count < 1:
            raise RuntimeError("native rendered video contains no frames")
        commands = []
        for item in final.get("commands", []):
            local = simulation.journal.receipt(item["command_id"])
            local_receipt = {key: local.get(key) for key in
                             ("status", "command_id", "payload_hash", "state", "event_id",
                              "last_known_state", "reconciliation_state")}
            commands.append({
                "command_id": item["command_id"], "task_id": item["task_id"],
                "kind": item.get("kind"), "state": item.get("state"),
                "reason_codes": item.get("reason_codes", []),
                "world_tick": item.get("world_tick"),
                "local_receipt": local_receipt,
                "native_receipt": _receipt_projection(item.get("native")),
            })
        final_snapshot = {**final, "commands": commands,
                          "held": simulation.status()["held"],
                          "robots": [{"id": robot.get("id"), "role": robot.get("role"),
                                      "state": robot.get("state")}
                                     for robot in final.get("robots", [])]}
        if not is_complete_mission(final_snapshot, held=simulation.status()["held"]):
            raise RuntimeError("mission did not reach complete graph-verified state")
        result.update(
            status="complete",
            mission_state=project_state(final_snapshot, manifest),
            release_state_snapshots=release_states,
            release_action={
                "performed": release_recorded,
                "actor_kind": "configured_local_demo_owner" if release_recorded else None,
                "human_authenticated": False,
                "event_id": "fleet-demo-owner-" + token if release_recorded else None,
                "caption": "scripted configured demo-owner action; not human-authenticated",
            },
            frame_capture={"frame_count": recorder.frame_count, "fps": args.fps,
                           "dimensions": [640, 360], "first_world_tick": recorder.first_tick,
                           "last_world_tick": recorder.last_tick,
                           "sample_every_ticks": args.sample_every,
                           "captions": recorder.samples},
            tenant_id=graph.tenant_id,
            graph_namespace=graph_name,
            graph_host="127.0.0.1",
            graph_port=args.graph_port,
            graph_namespace_isolated=True,
            graph_version=graph.read_version_root().get("graph_version"),
            policy_epoch=graph.read_version_root().get("policy_epoch"),
            runtime_versions={
                "python": sys.version.split()[0],
                "mujoco": __import__("mujoco").__version__,
                "numpy": __import__("numpy").__version__,
                "imageio": __import__("imageio").__version__,
                "pillow": __import__("PIL").__version__,
            },
            generated_at_utc=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        )
        return result
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = f"{type(exc).__name__}: {exc}"
        try:
            if simulation is not None:
                result["simulator_state"] = simulation.status()
            if controller is not None and controller.manifest is not None:
                state = controller.state()
                result["mission_state"] = project_state(state, controller.manifest)
                result["simulator_held"] = simulation.status()["held"]
        except Exception as state_error:
            result["state_capture_error"] = f"{type(state_error).__name__}: {state_error}"
        return result
    finally:
        try:
            if recorder is not None:
                recorder.close()
        finally:
            if controller is not None:
                controller.close()
            elif simulation is not None:
                simulation.close()
            if graph is not None:
                graph._client.close()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    valid_run_directory = False
    try:
        args = validate_args(args)
        valid_run_directory = True
        report = capture(args)
    except Exception as exc:
        report = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}

    if report.get("status") == "complete":
        try:
            source_hashes = {
                path: _file_hash(ROOT / path) for path in SOURCE_FILES
                if (ROOT / path).is_file()
            }
            complete_report: dict[str, object] = dict(report)
            complete_report["provenance"] = {
                "source_root": str(ROOT),
                "source_sha256": source_hashes,
                "source_tree_clean": None,
                "note": "per-file source hashes are retained; no Git cleanliness/commit claim is made",
            }
            _write_json(args.run_dir / "mission-state.json", report["mission_state"])
            _write_json(args.run_dir / "manifest.json", {
                "status": complete_report["status"],
                "scenario": complete_report["scenario"],
                "seed": complete_report["seed"],
                "run_directory": str(args.run_dir),
                "video": {"path": str(args.output), "sha256": _file_hash(args.output),
                          "bytes": args.output.stat().st_size},
                "provenance": complete_report["provenance"],
                "report": complete_report,
            })
            report = complete_report
        except Exception as exc:
            for artifact in (args.run_dir / "mission-state.json", args.run_dir / "manifest.json"):
                artifact.unlink(missing_ok=True)
            report = {"status": "failed",
                      "error": f"artifact finalization failed: {type(exc).__name__}: {exc}"}
            _write_json(args.run_dir / "failure-report.json", report)
    elif valid_run_directory:
        _write_json(args.run_dir / "failure-report.json", report)

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("status") == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
