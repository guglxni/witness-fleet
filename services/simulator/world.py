"""Single-clock MuJoCo facility with bounded deterministic skill controllers."""

from __future__ import annotations

import copy
import hashlib
import math
from pathlib import Path
from typing import Any

import mujoco
import numpy as np

from . import sensors

_NATIVE_CONTROLLER_SCHEMA = "facility-world-controllers-v1"


def _native_model_fingerprint(model: mujoco.MjModel) -> dict[str, str]:
    """Fingerprint the current compiled model and its native continuation contract."""
    model_buffer = np.empty(mujoco.mj_sizeModel(model), dtype=np.uint8)
    mujoco.mj_saveModel(model, buffer=model_buffer)
    asset = Path(__file__).with_name("assets") / "facility.xml"
    return {
        "mujoco_version": str(mujoco.__version__),
        "asset_sha256": hashlib.sha256(asset.read_bytes()).hexdigest(),
        "compiled_model_sha256": hashlib.sha256(model_buffer.tobytes()).hexdigest(),
        "controller_schema": _NATIVE_CONTROLLER_SCHEMA,
    }


class FacilityWorld:
    """Owns the MuJoCo model/data; callers receive only poses and sensor projections."""

    ROBOT_IDS = ("scout", "recovery", "courier")
    FOOTPRINTS = {"scout": 0.22, "recovery": 0.38, "courier": 0.50}
    MAX_STEP_BATCH = 10_000
    MAX_SKILL_TIMEOUT = 2_000
    MAX_TARGET_DISPLACEMENT = 1.25
    MAX_PUSH_FORCE = 45.0

    def __init__(self, seed: int = 0, scenario: str = "SC-001", episode_id: str | None = None) -> None:
        if scenario not in {"SC-001", "SC-002", "SC-003", "SC-004", "SC-005", "SC-008"}:
            raise ValueError(f"unsupported scenario: {scenario}")
        self.seed = int(seed)
        self.scenario = scenario
        self.episode_id = episode_id or f"{scenario}-{seed}"
        self._scenario = scenario
        self._footprints = dict(self.FOOTPRINTS)
        self._corridor_half_width = 0.70
        self._closed = False
        self._hold_sources: dict[str, str] = {}
        self._barrier_recovery: dict[str, Any] | None = None
        self._held = False
        self._hold_reason: str | None = None
        self._heartbeat_deadline: float | None = None
        self._heartbeat_timeout_s = 1.0
        self._last_heartbeat_s: float | None = None
        self.world_tick = 0
        asset = Path(__file__).with_name("assets") / "facility.xml"
        self.model = mujoco.MjModel.from_xml_path(str(asset))
        self.data = mujoco.MjData(self.model)
        self.rng = np.random.default_rng(self.seed)
        self._robot_body_ids: dict[str, int] = {}
        self._robot_site_ids: dict[str, int] = {}
        self._robot_qpos_adr: dict[str, int] = {}
        self._robot_joint_adr: dict[str, tuple[int, int, int]] = {}
        self._robot_actuator_ids: dict[str, tuple[int, int, int]] = {}
        self._robot_geom_ids: dict[str, int] = {}
        for robot in self.ROBOT_IDS:
            self._robot_body_ids[robot] = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, robot)
            self._robot_site_ids[robot] = (
                mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SITE, "scout_sensor")
                if robot == "scout"
                else -1
            )
            joint_ids = tuple(
                mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, f"{robot}_{axis}")
                for axis in ("x", "y", "yaw")
            )
            self._robot_joint_adr[robot] = tuple(int(self.model.jnt_qposadr[j]) for j in joint_ids)
            self._robot_qpos_adr[robot] = self._robot_joint_adr[robot][0]
            self._robot_actuator_ids[robot] = tuple(
                mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_ACTUATOR, f"{robot}_{axis}_motor")
                for axis in ("x", "y", "yaw")
            )
            self._robot_geom_ids[robot] = mujoco.mj_name2id(
                self.model, mujoco.mjtObj.mjOBJ_GEOM, f"{robot}_chassis"
            )
        self._obstruction_name = "heavy_box" if scenario == "SC-002" else "carton"

        self._obstruction_body_id = mujoco.mj_name2id(
            self.model, mujoco.mjtObj.mjOBJ_BODY, self._obstruction_name
        )
        self._inactive_obstruction_geom_id = mujoco.mj_name2id(
            self.model, mujoco.mjtObj.mjOBJ_GEOM, "heavy_box_geom" if self._obstruction_name == "carton" else "carton_geom"
        )
        self._obstruction_geom_id = mujoco.mj_name2id(
            self.model, mujoco.mjtObj.mjOBJ_GEOM, f"{self._obstruction_name}_geom"
        )
        self._qpos_adr = int(
            self.model.jnt_qposadr[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, f"{self._obstruction_name}_free")]
        )
        self._parcel_body_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_BODY, "parcel")
        self._parcel_joint_adr = int(
            self.model.jnt_qposadr[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, "parcel_free")]
        )
        parcel_adr = self._parcel_joint_adr
        self.data.qpos[parcel_adr : parcel_adr + 3] = [-6.0, 0.0, 0.48]
        self.data.qpos[parcel_adr + 3 : parcel_adr + 7] = [1.0, 0.0, 0.0, 0.0]
        self._payload_id: str | None = None
        self._payload_loaded = False
        self._delivery_site_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SITE, "delivery_zone")
        # Slide joints default to qpos=0; explicitly seed the episode's initial fixture poses.
        inactive = "carton" if self._obstruction_name == "heavy_box" else "heavy_box"
        inactive_adr = int(self.model.jnt_qposadr[mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, f"{inactive}_free")])
        self.data.qpos[inactive_adr : inactive_adr + 3] = [10.0, 5.0, -1.0]
        # Slide joints default to qpos=0; explicitly seed the episode's initial fixture poses.
        # qpos writes are restricted to initial setup and checkpoint restore.
        # Park the recovery robot outside the scout's initial sight line while
        # keeping it in the corridor for a physically controlled approach.
        initial_robot_xy = {"scout": (-4.0, -0.35), "recovery": (0.0, -0.50), "courier": (-6.0, 0.0)}
        for robot, (x, y) in initial_robot_xy.items():
            adr_x, adr_y, adr_yaw = self._robot_joint_adr[robot]
            body_id = self._robot_body_ids[robot]
            self.data.qpos[adr_x] = x - self.model.body_pos[body_id, 0]
            self.data.qpos[adr_y] = y - self.model.body_pos[body_id, 1]
            initial_yaw = math.pi / 2 if robot == 'recovery' else 0.0
            self.data.qpos[adr_yaw] = initial_yaw
            for actuator, value in zip(self._robot_actuator_ids[robot], (x, y, initial_yaw), strict=True):
                self.data.ctrl[actuator] = value
        # Scenario 003 creates a physically narrow opening; it is observation evidence, not a policy shortcut.
        if scenario == "SC-003":
            self.model.geom_size[self._obstruction_geom_id][1] = 0.45
        if scenario == "SC-004":
            occluder_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, "scenario_occluder")
            self.model.geom_pos[occluder_id] = [-2.8, -0.35, 0.21]
            self.model.geom_size[occluder_id] = [0.08, 0.22, 0.18]
            self.model.geom_contype[occluder_id] = 1
            self.model.geom_conaffinity[occluder_id] = 1
            self.data.qpos[self._qpos_adr : self._qpos_adr + 3] = [-1.0, -0.35, 0.18]
        mujoco.mj_forward(self.model, self.data)
        self._skills: dict[str, dict[str, Any]] = {}
        self._contacts = 0
        self._max_contact_force = 0.0
        self._obstruction_initial = self._object_position().copy()

    def step(self, n: int = 1) -> None:
        self._ensure_open()
        if type(n) is not int or n < 1 or n > self.MAX_STEP_BATCH:
            raise ValueError(f"n must be an integer in [1, {self.MAX_STEP_BATCH}]")
        for _ in range(n):
            self._advance_controllers()
            if self._held:
                self._neutralize_motion()
            mujoco.mj_step(self.model, self.data)
            self.world_tick += 1
            self._record_contacts()
            self._finish_controllers()

    def poses(self) -> dict[str, dict[str, float]]:
        self._ensure_open()
        result = {}
        for robot in self.ROBOT_IDS:
            body_id = self._robot_body_ids[robot]
            adr = self._robot_qpos_adr[robot]
            result[robot] = {
                "x": float(self.data.qpos[adr]),
                "y": float(self.data.qpos[adr + 1]),
                "z": float(self.data.xpos[body_id][2]),
                "yaw": float(self.data.qpos[adr + 2]),
            }
        return result

    def inspect(self, robot_id: str) -> dict[str, Any]:
        self._ensure_open()
        observation = sensors.observe(self, robot_id)
        if robot_id == "courier" and self._payload_loaded:
            payload = self._payload_observation()
            if payload is not None:
                observation["payload"] = payload
        return observation

    def load_payload(self, robot_id: str, payload_id: str) -> dict[str, Any]:
        """Physically place the fixture parcel on the courier chassis before motion."""
        self._ensure_open()
        if robot_id != "courier":
            return {"status": "rejected", "reason": "capability_mismatch"}
        if not isinstance(payload_id, str) or not payload_id.strip() or len(payload_id) > 100:
            return {"status": "rejected", "reason": "invalid_payload_id"}
        if self._payload_loaded:
            return {"status": "rejected", "reason": "payload_already_loaded"}
        pose = self.poses()[robot_id]
        address = self._parcel_joint_adr
        # Fixture loading is an explicit pre-execution world setup operation.
        self.data.qpos[address : address + 3] = [pose["x"], pose["y"], pose["z"] + 0.30]
        self.data.qpos[address + 3 : address + 7] = [1.0, 0.0, 0.0, 0.0]
        self.data.qvel[address : address + 6] = 0.0
        mujoco.mj_forward(self.model, self.data)
        self._payload_id = payload_id
        self._payload_loaded = True
        return {"status": "loaded", "payload_id": payload_id, "robot_id": robot_id}

    def start_skill(self, robot_id: str, kind: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        self._ensure_open()
        params = dict(parameters or {})
        if robot_id not in self.ROBOT_IDS:
            return {"status": "rejected", "reason": "unknown_robot"}
        if self._held and kind not in {"hold", "inspect", "wait"}:
            return {"status": "rejected", "reason": "world_held", "hold_reason": self._hold_reason}
        if kind not in {"travel", "recover", "inspect", "verify", "deliver", "hold", "wait"}:
            return {"status": "rejected", "reason": "unsupported_skill"}
        if robot_id in self._skills and self._skills[robot_id]["status"] in {"accepted", "running"}:
            return {"status": "rejected", "reason": "skill_already_active"}
        if (kind == 'recover' and robot_id != 'recovery') or (kind == 'deliver' and robot_id != 'courier'):
            return {"status": "rejected", "reason": "capability_mismatch"}
        timeout = params.get("timeout_ticks", 500)
        if type(timeout) is not int or timeout < 1 or timeout > self.MAX_SKILL_TIMEOUT:
            return {"status": "rejected", "reason": "timeout_out_of_bounds"}
        state: dict[str, Any] = {
            "robot_id": robot_id,
            "kind": kind,
            "parameters": params,
            "status": "accepted",
            "accepted_tick": self.world_tick,
            "started_tick": None,
            "deadline_tick": self.world_tick + timeout,
            "initial_object": self._object_position().copy(),
            "contact_count": 0,
            "reason": None,
        }
        if kind == "travel":
            target_x = self._bounded_number(params, "target_x", 0.0, -7.0, 7.0)
            target_y = self._bounded_number(params, "target_y", 0.0, -3.0, 3.0)
            state["target"] = np.array([target_x, target_y], dtype=float)
        elif kind == "recover":
            displacement = self._bounded_number(params, "target_displacement_m", 0.75, 0.0, self.MAX_TARGET_DISPLACEMENT)
            if displacement <= 0:
                return {"status": "rejected", "reason": "invalid_displacement"}
            state["target_displacement_m"] = displacement
            object_position = self._object_position()
            state["phase"] = "align"
            state["stage_target"] = np.array([object_position[0], -0.50])
            state["approach_target"] = np.array([object_position[0], -0.50])
            state["push_axis_x"] = float(object_position[0])
            state["push_target_y"] = 1.3
        elif kind == "deliver":
            if not self._payload_loaded:
                return {"status": "rejected", "reason": "no_payload"}
            target_x = self._bounded_number(params, "target_x", 4.0, -7.0, 7.0)
            target_y = self._bounded_number(params, "target_y", -2.5, -3.0, 3.0)
            state["target"] = np.array([target_x, target_y], dtype=float)
        elif kind in {"inspect", "verify"}:
            state["status"] = "accepted"
        elif kind == "hold":
            self.hold(str(params.get("reason", "skill_hold")))
            state["status"] = "done"
        elif kind == "wait":
            state["status"] = "running"
            state["started_tick"] = self.world_tick
        self._skills[robot_id] = state
        return {"status": "accepted", "robot_id": robot_id, "kind": kind, "accepted_tick": self.world_tick}

    def skill_status(self, robot_id: str) -> dict[str, Any]:
        if robot_id not in self._skills:
            return {"status": "idle", "robot_id": robot_id, "world_tick": self.world_tick}
        state = copy.deepcopy(self._skills[robot_id])
        initial_object = state.get("initial_object")
        state.pop("initial_object", None)
        state.pop("parameters", None)
        if "target" in state:
            state["target"] = state["target"].tolist()
        if "approach_target" in state:
            state["approach_target"] = state["approach_target"].tolist()
        state["world_tick"] = self.world_tick
        if state["kind"] == "recover" and initial_object is not None:
            state["measured_displacement_m"] = float(
                np.linalg.norm(self._object_position()[:2] - initial_object[:2])
            )
            state["contact_count"] = int(state["contact_count"])
        return state

    def heartbeat(self, now_s: float, allowed: bool = True, timeout_s: float = 1.0) -> dict[str, Any]:
        self._ensure_open()
        if not math.isfinite(now_s) or not math.isfinite(timeout_s) or timeout_s <= 0:
            raise ValueError("heartbeat time and timeout must be finite; timeout must be positive")
        self._heartbeat_timeout_s = min(timeout_s, 30.0)
        self._last_heartbeat_s = float(now_s)
        self._heartbeat_deadline = float(now_s) + self._heartbeat_timeout_s
        if not allowed:
            self.hold("heartbeat_revoked")
            return {"status": "held", "reason": self._hold_reason, "world_tick": self.world_tick}
        if self._hold_sources.get("watchdog") == "heartbeat_revoked":
            self.clear_hold_source("watchdog", expected_reason="heartbeat_revoked")
        return {"status": "ok", "deadline_s": self._heartbeat_deadline, "world_tick": self.world_tick}

    def watchdog_check(self, now_s: float) -> dict[str, Any]:
        self._ensure_open()
        if self._heartbeat_deadline is None or now_s <= self._heartbeat_deadline:
            return {"status": "ok", "world_tick": self.world_tick}
        self.hold("heartbeat_timeout")
        return {"status": "held", "reason": self._hold_reason, "world_tick": self.world_tick}

    def hold(self, reason: str, *, source_id: str | None = None) -> dict[str, Any]:
        self._ensure_open()
        text = str(reason)[:200]
        if source_id is None:
            source_id = "watchdog" if text.startswith("heartbeat_") else f"native:{text}"
        if not isinstance(source_id, str) or not source_id or len(source_id) > 200:
            raise ValueError("hold source identity must be a bounded non-empty string")
        self._hold_sources[source_id] = text
        self._refresh_hold_projection()
        for state in self._skills.values():
            if state["status"] in {"accepted", "running"}:
                state["status"] = "held"
                state["reason"] = self._hold_reason
        self._neutralize_motion()
        return {"status": "held", "reason": self._hold_reason, "world_tick": self.world_tick,
                "hold_sources": copy.deepcopy(self._hold_sources)}

    def clear_hold_source(self, source_id: str, *, expected_reason: str) -> dict[str, Any]:
        """Remove exactly one native hold owner; unknown legacy holds are never clearable."""
        self._ensure_open()
        if source_id == "legacy:unknown" or self._hold_sources.get(source_id) != expected_reason:
            return {"status": "held", "reason": self._hold_reason,
                    "hold_sources": copy.deepcopy(self._hold_sources)}
        del self._hold_sources[source_id]
        self._refresh_hold_projection()
        return {"status": "held" if self._held else "ok", "reason": self._hold_reason,
                "hold_sources": copy.deepcopy(self._hold_sources)}

    def _refresh_hold_projection(self) -> None:
        self._held = bool(self._hold_sources)
        self._hold_reason = next(iter(self._hold_sources.values()), None)

    def mark_barrier_recovery(self, marker: dict[str, Any] | None) -> None:
        """Persist an exact barrier marker while held for trusted explicit recovery."""
        self._ensure_open()
        if marker is not None:
            if (not isinstance(marker, dict) or set(marker) != {
                    'event_id', 'sequence', 'coordinator_epoch', 'payload_hash'}
                    or not isinstance(marker['event_id'], str) or not marker['event_id']
                    or type(marker['sequence']) is not int or marker['sequence'] < 1
                    or type(marker['coordinator_epoch']) is not int or marker['coordinator_epoch'] < 0
                    or not isinstance(marker['payload_hash'], str) or not marker['payload_hash']):
                raise ValueError('invalid committed barrier recovery marker')
        self._barrier_recovery = copy.deepcopy(marker)

    def checkpoint(self) -> dict[str, Any]:
        self._ensure_open()
        return {
            "model_identity": _native_model_fingerprint(self.model),
            "episode_id": self.episode_id,
            "scenario": self.scenario,
            "seed": self.seed,
            "world_tick": self.world_tick,
            "sim_time": float(self.data.time),
            "payload_id": self._payload_id,
            "payload_loaded": self._payload_loaded,
            "qpos": self.data.qpos.copy(),
            "qvel": self.data.qvel.copy(),
            "act": self.data.act.copy(),
            "ctrl": self.data.ctrl.copy(),
            "skills": copy.deepcopy(self._skills),
            "held": self._held,
            "hold_reason": self._hold_reason,
            "hold_sources": copy.deepcopy(self._hold_sources),
            "barrier_recovery": copy.deepcopy(self._barrier_recovery),
            "contacts": self._contacts,
            "max_contact_force": self._max_contact_force,
            "rng_state": copy.deepcopy(self.rng.bit_generator.state),
        }

    def restore(self, checkpoint: dict[str, Any]) -> None:
        self._ensure_open()
        model_identity = checkpoint.get("model_identity")
        if model_identity is None:
            raise ValueError("checkpoint has no native model identity; a new episode is required")
        if type(model_identity) is not dict or model_identity != _native_model_fingerprint(self.model):
            raise ValueError("checkpoint native model identity does not match the current model")
        if (checkpoint.get("scenario") != self.scenario or checkpoint.get("seed") != self.seed
                or checkpoint.get('episode_id') != self.episode_id):
            raise ValueError("checkpoint belongs to a different scenario or seed")
        # Validate and detach the entire candidate before touching live physics.
        # Partial application makes a corrupt checkpoint an unjournaled effect.
        arrays = {}
        for name in ('qpos', 'qvel', 'act', 'ctrl'):
            value = np.asarray(checkpoint[name])
            if (value.shape != getattr(self.data, name).shape
                    or value.dtype.kind not in 'if' or not np.isfinite(value).all()):
                raise ValueError(f'checkpoint {name} shape or finite-number mismatch')
            arrays[name] = value.astype(float, copy=True)
        tick = checkpoint['world_tick']
        contacts = checkpoint['contacts']
        if type(tick) is not int or tick < 0 or type(contacts) is not int or contacts < 0:
            raise ValueError('checkpoint counters require nonnegative integers')
        sim_time = checkpoint['sim_time']
        force = checkpoint.get('max_contact_force', 0.0)
        for value in (sim_time, force):
            if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value) or value < 0:
                raise ValueError('checkpoint measurements require finite nonnegative numbers')
        held = checkpoint['held']
        loaded = checkpoint['payload_loaded']
        if type(held) is not bool or type(loaded) is not bool:
            raise ValueError('checkpoint flags require booleans')
        hold_sources = checkpoint.get('hold_sources')
        if hold_sources is None:
            hold_sources = ({'legacy:unknown': str(checkpoint.get('hold_reason') or 'legacy held checkpoint')}
                            if held else {})
        if (not isinstance(hold_sources, dict)
                or any(not isinstance(key, str) or not key or not isinstance(value, str) or not value
                       for key, value in hold_sources.items())
                or bool(hold_sources) != held):
            raise ValueError('checkpoint hold sources do not match held projection')
        payload_id = checkpoint['payload_id']
        if payload_id is not None and (not isinstance(payload_id, str) or not payload_id):
            raise ValueError('checkpoint payload identity is invalid')
        if loaded and payload_id is None:
            raise ValueError('loaded checkpoint requires payload identity')
        skills = copy.deepcopy(checkpoint['skills'])
        if not isinstance(skills, dict) or not set(skills).issubset(self.ROBOT_IDS):
            raise ValueError('checkpoint skills require known robot identities')
        skill_vector_shapes = {
            'target': (2,),
            'approach_target': (2,),
            'stage_target': (2,),
            'park_target': (2,),
            'initial_object': (3,),
        }
        for robot, state in skills.items():
            if not isinstance(state, dict):
                raise ValueError(f'checkpoint skill state for {robot} must be an object')
            for field, shape in skill_vector_shapes.items():
                if field not in state:
                    continue
                try:
                    vector = np.asarray(state[field])
                except (TypeError, ValueError) as exc:
                    raise ValueError(f'checkpoint skill vector {field} is invalid') from exc
                if (vector.shape != shape or vector.dtype.kind not in 'if'
                        or not np.isfinite(vector).all()):
                    raise ValueError(f'checkpoint skill vector {field} shape or finite-number mismatch')
                state[field] = vector.astype(float, copy=True)
        rng_state = copy.deepcopy(checkpoint['rng_state'])
        probe_rng = np.random.default_rng()
        probe_rng.bit_generator.state = rng_state
        for name, value in arrays.items():
            getattr(self.data, name)[:] = value
        self.world_tick = tick
        self.data.time = float(sim_time)
        self._payload_id = payload_id
        self._payload_loaded = loaded
        self._skills = skills
        self._hold_sources = copy.deepcopy(hold_sources)
        self._barrier_recovery = copy.deepcopy(checkpoint.get('barrier_recovery'))
        self._held = held
        self._hold_reason = next(iter(self._hold_sources.values()), None)
        self._contacts = contacts
        self._max_contact_force = float(force)
        self.rng.bit_generator.state = rng_state
        mujoco.mj_forward(self.model, self.data)

    def operator_projection(self) -> dict[str, Any]:
        return {
            "world_tick": self.world_tick,
            "sensor_mode": "S0",
            "robots": self.poses(),
            "observations": {robot: self.inspect(robot) for robot in self.ROBOT_IDS},
            "held": self._held,
            "hold_reason": self._hold_reason,
        }

    def close(self) -> None:
        self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("facility world is closed")

    @staticmethod
    def _bounded_number(params: dict[str, Any], key: str, default: float, low: float | None = None, high: float | None = None) -> float:
        value = params.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
            raise ValueError(f"{key} must be a finite number")
        value = float(value)
        if low is not None and value < low or high is not None and value > high:
            raise ValueError(f"{key} outside bounds")
        return value

    def _advance_controllers(self) -> None:
        for robot, state in self._skills.items():
            if state["status"] not in {"accepted", "running"}:
                continue
            if state["status"] == "accepted":
                state["status"] = "running"
                state["started_tick"] = self.world_tick
            if self.world_tick >= state["deadline_tick"]:
                state["status"] = "timed_out"
                state["reason"] = "skill_deadline"
                pose = self.poses()[robot]
                self._set_robot_control(robot, pose['x'], pose['y'], pose['yaw'])
                continue
            if state["kind"] in {"travel", "deliver"}:
                self._control_travel(robot, state)
            elif state["kind"] == "recover":
                self._control_recovery(robot, state)
            elif state["kind"] == "wait":
                continue
            elif state["kind"] in {"inspect", "verify"}:
                state["result"] = self.inspect(robot)
                state["status"] = "done"

    def _control_travel(self, robot: str, state: dict[str, Any]) -> None:
        target = state["target"]
        pose = self.poses()[robot]
        delta = target - np.array([pose["x"], pose["y"]])
        distance = float(np.linalg.norm(delta))
        settling = distance < 0.035
        desired_yaw = pose['yaw']  # Planar slide primitive can translate without wheel steering.
        if settling:
            # Keep a target-position servo active while momentum dissipates. Holding
            # the instantaneous pose would let the actuator's residual velocity
            # carry the robot away after the controller declares arrival.
            goal = target.copy()
        else:
            reference = self.data.ctrl[list(self._robot_actuator_ids[robot][:2])].copy()
            to_target = target - reference
            reference_distance = float(np.linalg.norm(to_target))
            goal = reference + to_target / max(reference_distance, 1e-9) * min(.018, reference_distance)
            lag = goal - np.array([pose['x'], pose['y']])
            lag_distance = float(np.linalg.norm(lag))
            if lag_distance > .3:
                goal = np.array([pose['x'], pose['y']]) + lag / lag_distance * .3
        proposed_x, proposed_y = map(float, goal)
        radius = self.FOOTPRINTS[robot] / 2
        if abs(proposed_y) + radius > self._corridor_half_width or abs(proposed_x) + radius > 7.0:
            state["status"] = "failed"
            state["reason"] = "immediate_geometry_stop"
            self._set_robot_control(robot, pose["x"], pose["y"], pose["yaw"])
            return
        for other, other_pose in self.poses().items():
            if other == robot:
                continue
            separation = math.hypot(proposed_x - other_pose["x"], proposed_y - other_pose["y"])
            if separation < radius + self.FOOTPRINTS[other] / 2 + 0.04:
                state["status"] = "failed"
                state["reason"] = "robot_collision_envelope"
                self._set_robot_control(robot, pose["x"], pose["y"], pose["yaw"])
                return
        self._set_robot_control(robot, proposed_x, proposed_y, desired_yaw)
        if settling:
            qvel_adr = self._robot_joint_adr[robot][:2]
            speed = float(np.linalg.norm(self.data.qvel[list(qvel_adr)]))
            if speed <= 0.01:
                if state["kind"] == "deliver":
                    postcondition = self._delivery_postcondition()
                    if postcondition["payload_in_delivery_zone"]:
                        state["status"] = "done"
                        state["result"] = {"arrival_tick": self.world_tick, "postcondition": postcondition}
                    else:
                        state["status"] = "failed"
                        state["reason"] = "payload_delivery_postcondition_failed"
                else:
                    state["status"] = "done"
                    state["result"] = {"arrival_tick": self.world_tick}

    def _control_recovery(self, robot: str, state: dict[str, Any]) -> None:
        # A short pusher permits a non-penetrating approach inside the south wall.
        # Rotate in open corridor, stage behind the carton, then push north slowly.
        pose = self.poses()[robot]
        yaw_target = math.pi / 2
        phase = state['phase']
        if phase == 'align':
            error = yaw_target - pose['yaw']
            self._set_robot_control(robot, pose['x'], pose['y'], yaw_target)
            if abs(error) < .03:
                state['phase'] = 'stage'
            return
        if phase == 'stage':
            target = np.array([pose['x'], -.50])
            if abs(pose['y'] + .50) < .006:
                self._set_robot_control(robot, pose['x'], -.50, yaw_target)
                velocity = self.data.qvel[self._robot_joint_adr[robot][1]]
                if abs(velocity) < .01:
                    state['phase'] = 'approach'
            else:
                self._bounded_recovery_target(robot, target, yaw_target)
            return
        if phase == 'approach':
            target = state['approach_target']
            if np.linalg.norm(target - np.array([pose['x'], pose['y']])) < .01:
                state['phase'] = 'push'
            else:
                self._bounded_recovery_target(robot, target, yaw_target)
            return
        if phase == 'push':
            target = np.array([state['push_axis_x'], state['push_target_y']])
            self._bounded_recovery_target(robot, target, yaw_target)
            return
        if phase == 'park_side':
            target = state['park_target']
            if np.linalg.norm(target - np.array([pose['x'], pose['y']])) < .03:
                state['phase'] = 'park'
                state['park_target'] = np.array([-.75, 1.4])
            else:
                self._bounded_recovery_target(robot, target, yaw_target)
            return
        if phase == 'park':
            target = state['park_target']
            if np.linalg.norm(target - np.array([pose['x'], pose['y']])) < .03:
                self._set_robot_control(robot, pose['x'], pose['y'], pose['yaw'])
                state['phase'] = 'parked'
                state['status'] = 'done'
                state['result'] = 'physical_contact_and_displacement'
            else:
                self._bounded_recovery_target(robot, target, yaw_target)

    def _bounded_recovery_target(self, robot, target, yaw):
        pose = self.poses()[robot]
        position = np.array([pose['x'], pose['y']])
        reference = self.data.ctrl[list(self._robot_actuator_ids[robot][:2])].copy()
        delta = target - reference
        distance = float(np.linalg.norm(delta))
        goal = reference + delta / max(distance, 1e-9) * min(distance, .006)
        lag = goal - position
        lag_distance = float(np.linalg.norm(lag))
        if lag_distance > .60:
            goal = position + lag / lag_distance * .60
        self._set_robot_control(robot, float(goal[0]), float(goal[1]), yaw)

    def _set_robot_control(self, robot: str, x: float, y: float, yaw: float) -> None:
        for actuator, value in zip(self._robot_actuator_ids[robot], (x, y, yaw), strict=True):
            self.data.ctrl[actuator] = value

    def _neutralize_motion(self) -> None:
        for robot, values in self.poses().items():
            self._set_robot_control(robot, values["x"], values["y"], values["yaw"])

    def _record_contacts(self) -> None:
        pusher_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, "recovery_pusher")
        recovery_id = self._robot_geom_ids["recovery"]
        for idx in range(self.data.ncon):
            contact = self.data.contact[idx]
            pair = {int(contact.geom1), int(contact.geom2)}
            if self._obstruction_geom_id in pair and pair.intersection({pusher_id, recovery_id}):
                force = np.zeros(6)
                mujoco.mj_contactForce(self.model, self.data, idx, force)
                if float(np.linalg.norm(force[:3])) > 0.1:
                    self._contacts += 1
                    self._max_contact_force = max(self._max_contact_force, float(np.linalg.norm(force[:3])))
                    for state in self._skills.values():
                        if state["kind"] == "recover" and state["status"] == "running":
                            state["contact_count"] += 1
                            state["max_contact_force_n"] = max(
                                state.get("max_contact_force_n", 0.0), float(np.linalg.norm(force[:3]))
                            )

    def _finish_controllers(self) -> None:
        for state in self._skills.values():
            if state["kind"] != "recover" or state["status"] != "running":
                continue
            position = self._object_position()
            moved = float(np.linalg.norm(position[:2] - state["initial_object"][:2]))
            target_displacement = float(state["target_displacement_m"])
            clear_of_wall = float(position[1]) >= 1.20
            if (state['phase'] == 'push' and moved >= target_displacement
                    and clear_of_wall and state["contact_count"] > 0):
                state["phase"] = "park_side"
                robot_pose = self.poses()['recovery']
                self._set_robot_control('recovery', robot_pose['x'], robot_pose['y'], robot_pose['yaw'])
                state['park_target'] = np.array([-.75, robot_pose['y']], dtype=float)
            elif self.world_tick >= state["deadline_tick"]:
                state["status"] = "failed"
                state["reason"] = "no_sufficient_physical_displacement"
        # Wall-clock watchdog is explicitly polled by the owner between calls to
        # step; the deterministic scheduler never reads wall clock.

    @property
    def _watchdog_time_s(self) -> float:
        if self._last_heartbeat_s is None:
            return 0.0
        return self._last_heartbeat_s + self.world_tick * self.model.opt.timestep

    def _object_position(self) -> np.ndarray:
        return np.asarray(self.data.xpos[self._obstruction_body_id], dtype=float).copy()

    def _payload_observation(self) -> dict[str, Any] | None:
        geom_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_GEOM, "parcel_geom")
        position = np.asarray(self.data.xpos[self._parcel_body_id], dtype=float)
        courier = self.poses()["courier"]
        visible = np.linalg.norm(position[:2] - np.array([courier["x"], courier["y"]])) <= sensors.MAX_RANGE_M
        if not visible:
            return None
        return {
            "state": "observed",
            "payload_id": self._payload_id,
            "observed_pose": {"x": round(float(position[0]), 3), "y": round(float(position[1]), 3), "z": round(float(position[2]), 3)},
            "delivery_zone": self._delivery_postcondition()["payload_in_delivery_zone"],
            "geom_id": int(geom_id),
        }

    def _delivery_postcondition(self) -> dict[str, Any]:
        payload = np.asarray(self.data.xpos[self._parcel_body_id], dtype=float)
        zone = np.asarray(self.data.site_xpos[self._delivery_site_id], dtype=float)
        zone_radius = float(self.model.site_size[self._delivery_site_id, 0])
        courier = self.poses()["courier"]
        relative_height = float(payload[2] - courier["z"])
        in_zone = bool(
            self._payload_loaded
            and np.linalg.norm(payload[:2] - zone[:2]) <= zone_radius
            and abs(relative_height - 0.30) <= 0.12
        )
        return {
            "payload_in_delivery_zone": in_zone,
            "payload_pose": [round(float(value), 4) for value in payload],
            "zone_center": [round(float(value), 4) for value in zone],
            "zone_radius_m": zone_radius,
            "relative_height_m": round(relative_height, 4),
        }

    def __enter__(self) -> FacilityWorld:
        self._ensure_open()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()
