"""Read-only native stability windows collected from public service projections."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from witness_fleet.domain import CommandIntent, canonical_json_hash

SAMPLE_COUNT = 10
TICK_SECONDS = 0.01
MAX_TARGET_ERROR_M = 0.05
MAX_SPEED_M_S = 0.01
MAX_DRIFT_M = 0.01
WINDOW_SCHEMA = "native-public-stability-v1"
# This identity marker is intentionally not serializable; projections accept only
# windows sealed by this module's collector in this process.
_WINDOW_SEAL = object()


def _finite(value: Any) -> bool:
    return type(value) in {int, float} and math.isfinite(value)


@dataclass(frozen=True)
class StabilityWindow:
    """Immutable bounded evidence from one exact command and service instance."""

    episode_id: str
    robot_id: str
    command_id: str
    command_payload_hash: str
    target_xy: tuple[float, float]
    start_tick: int
    end_tick: int
    sample_count: int
    max_target_error_m: float
    max_speed_m_s: float
    max_drift_m: float
    tick_seconds: float
    sensor_config_hash: str
    visibility_state: str
    visibility_fraction: float
    schema: str = WINDOW_SCHEMA
    _service_identity: int = field(default=0, repr=False, compare=False)
    _seal: object = field(default=None, repr=False, compare=False)


class StabilityWindowCollector:
    """Collect consecutive read-only service status samples after controller DONE.

    The collector never advances the simulation. The owner must call service.advance
    for authorized ticks between calls to collect(). A missed tick or any command,
    episode, actor, receipt, held-state, or pose discontinuity resets the window.
    """

    def __init__(self, service: Any, command: CommandIntent):
        if not isinstance(command, CommandIntent):
            raise ValueError("typed retained command required")
        self.service = service
        self.command = CommandIntent.model_validate(command.model_dump(mode="json"))
        if self.command.proposal.kind.value not in {"travel", "deliver"}:
            raise ValueError("stability windows apply only to travel and delivery")
        params = self.command.proposal.parameters
        target = (params.get("target_x"), params.get("target_y"))
        if not all(_finite(value) for value in target):
            raise ValueError("finite exact command target required")
        self.target_xy = (float(target[0]), float(target[1]))
        self._samples: list[tuple[int, float, float, str, str]] = []

    @property
    def sample_count(self) -> int:
        return len(self._samples)

    def collect(self) -> StabilityWindow | None:
        """Observe one current tick without physics advancement; return window at N."""
        service = self.service
        with service._lock:
            status = service.status()
            receipt = service.command(self.command.command_id)
            if not isinstance(status, dict) or not isinstance(receipt, dict):
                self._samples.clear()
                return None
            native = receipt.get("native")
            robot_id = self.command.proposal.robot_id
            poses = status.get("poses")
            pose = poses.get(robot_id) if isinstance(poses, dict) else None
            observations = service.observations()
            samples = observations.get("robots") if isinstance(observations, dict) else None
            sample = samples.get(robot_id) if isinstance(samples, dict) else None
            tick = status.get("world_tick")
            if not _valid_sample(sample, robot_id, tick):
                self._samples.clear()
                return None
            if (not isinstance(sample, Mapping)
                    or sample.get('world_tick') != tick
                    or not isinstance(sample.get('sensor'), Mapping)
                    or not isinstance(sample['sensor'].get('config_hash'), str)
                    or not sample['sensor'].get('config_hash')):
                self._samples.clear()
                return None
            if self._samples and tick != self._samples[-1][0] + 1:
                self._samples.clear()
            if (status.get("held") is not False
                    or not isinstance(status.get("episode_id"), str)
                    or type(tick) is not int
                    or receipt.get("status") != "KNOWN"
                    or receipt.get("state") not in {"CONTROLLER_DONE", "OUTCOME_VERIFIED"}
                    or receipt.get("command_id") != self.command.command_id
                    or receipt.get("payload_hash") != canonical_json_hash(self.command)
                    or not isinstance(native, dict)
                    or native.get("status") != "done"
                    or native.get("robot_id") != robot_id
                    or native.get("kind") != self.command.proposal.kind.value
                    or native.get("accepted_tick") != self.command.effective_world_tick
                    or native.get("target") != list(self.target_xy)
                    or not isinstance(pose, dict)
                    or not all(_finite(pose.get(axis)) for axis in ("x", "y"))
                    or not isinstance(sample, Mapping)):
                self._samples.clear()
                return None
            x, y = float(pose["x"]), float(pose["y"])
            if math.hypot(x - self.target_xy[0], y - self.target_xy[1]) >= MAX_TARGET_ERROR_M:
                self._samples.clear()
                return None
            config_hash = sample["sensor"]["config_hash"]
            episode_id = status["episode_id"]
            if self._samples and (episode_id != self._samples[-1][4]
                                  or config_hash != self._samples[-1][3]):
                self._samples.clear()
            if not self._samples or tick == self._samples[-1][0] + 1:
                self._samples.append((tick, x, y, config_hash, episode_id))
            else:
                self._samples.clear()
                return None
            self._samples = self._samples[-SAMPLE_COUNT:]
            if len(self._samples) > SAMPLE_COUNT:
                self._samples = self._samples[-SAMPLE_COUNT:]
            if len(self._samples) != SAMPLE_COUNT:
                return None
            first_tick, first_x, first_y, first_config, _ = self._samples[0]
            last_tick, last_x, last_y, last_config, _ = self._samples[-1]
            drift = max(math.hypot(sx - first_x, sy - first_y)
                        for _, sx, sy, _, _ in self._samples)
            tick_seconds = float(service.world.model.opt.timestep)
            if not _finite(tick_seconds) or tick_seconds <= 0:
                self._samples.clear()
                return None
            speeds = [math.hypot(b[1] - a[1], b[2] - a[2]) / tick_seconds
                      for a, b in zip(self._samples, self._samples[1:], strict=False)]
            max_error = max(math.hypot(sx - self.target_xy[0], sy - self.target_xy[1])
                            for _, sx, sy, _, _ in self._samples)
            max_speed = max(speeds, default=0.0)
            if drift > MAX_DRIFT_M or max_speed > MAX_SPEED_M_S or max_error >= MAX_TARGET_ERROR_M:
                self._samples.clear()
                return None
            window_visibility = sample['visibility']
            return StabilityWindow(
                episode_id=status["episode_id"], robot_id=robot_id,
                command_id=self.command.command_id,
                command_payload_hash=canonical_json_hash(self.command),
                target_xy=self.target_xy, start_tick=first_tick, end_tick=last_tick,
                sample_count=SAMPLE_COUNT, max_target_error_m=max_error,
                max_speed_m_s=max_speed, max_drift_m=drift,
                tick_seconds=tick_seconds,
                sensor_config_hash=last_config,
                visibility_state=window_visibility["state"],
                visibility_fraction=window_visibility["fraction"],
                _service_identity=id(service),
                _seal=_WINDOW_SEAL,
            )


def validate_stability_window(service: Any, command: CommandIntent,
                              window: StabilityWindow | None,
                              *, episode_id: str, world_tick: int) -> bool:
    """Check opaque collector provenance, exact command, bounds and current end tick."""
    if not isinstance(window, StabilityWindow) or window._seal is not _WINDOW_SEAL:
        return False
    params = command.proposal.parameters
    target = (params.get("target_x"), params.get("target_y"))
    return (
        window._service_identity == id(service)
        and window.episode_id == episode_id
        and window.robot_id == command.proposal.robot_id
        and window.command_id == command.command_id
        and window.command_payload_hash == canonical_json_hash(command)
        and isinstance(window.target_xy, tuple) and len(window.target_xy) == 2
        and all(_finite(value) for value in window.target_xy)
        and all(_finite(value) for value in target)
        and window.target_xy == (float(target[0]), float(target[1]))
        and type(world_tick) is int
        and window.end_tick == world_tick
        and window.sample_count == SAMPLE_COUNT
        and type(window.start_tick) is int and type(window.end_tick) is int
        and window.end_tick - window.start_tick == SAMPLE_COUNT - 1
        and _finite(window.max_target_error_m)
        and window.max_target_error_m < MAX_TARGET_ERROR_M
        and _finite(window.max_speed_m_s)
        and window.max_speed_m_s <= MAX_SPEED_M_S
        and _finite(window.max_drift_m)
        and window.max_drift_m <= MAX_DRIFT_M
        and _finite(window.tick_seconds)
        and window.tick_seconds > 0
        and isinstance(window.sensor_config_hash, str)
        and bool(window.sensor_config_hash)
        and isinstance(window.visibility_state, str)
        and window.visibility_state in {"visible", "insufficient"}
        and isinstance(window.visibility_fraction, (int, float))
        and _finite(window.visibility_fraction)
        and 0 <= window.visibility_fraction <= 1
        and window.schema == WINDOW_SCHEMA
    )


def _valid_sample(sample: Any, robot_id: str, tick: Any) -> bool:
    if not isinstance(sample, Mapping) or sample.get("robot_id") != robot_id or sample.get("world_tick") != tick:
        return False
    sensor, visibility, ranges = sample.get("sensor"), sample.get("visibility"), sample.get("ranges_m")
    if not isinstance(sensor, Mapping) or not isinstance(visibility, Mapping) or not isinstance(ranges, list) or not ranges:
        return False
    maximum, expiry = sensor.get("max_range_m"), sensor.get("expires_tick")
    state, fraction = visibility.get("state"), visibility.get("fraction")
    return (
        _finite(maximum) and isinstance(maximum, (int, float)) and maximum > 0
        and type(expiry) is int and type(tick) is int and expiry > tick
        and isinstance(sensor.get("config_hash"), str) and bool(sensor.get("config_hash"))
        and state in {"visible", "insufficient"}
        and _finite(fraction) and isinstance(fraction, (int, float)) and 0 <= fraction <= 1
        and all(_finite(distance) and isinstance(distance, (int, float))
                and 0 <= distance <= maximum for distance in ranges)
    )
