"""Strict serialized domain contracts shared across Witness Fleet components."""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from collections.abc import Mapping
from datetime import datetime, timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
PositiveInt = Annotated[int, Field(strict=True, gt=0)]
JsonObject = Mapping[str, Any]


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        # Copy before wrapping: a proxy over a caller-owned dict is still mutable via its owner.
        return MappingProxyType({key: _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_deep_freeze(item) for item in value)
    return value


def _deep_thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _deep_thaw(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_deep_thaw(item) for item in value]
    return value


def _validate_json(value: Any, path: str = "value") -> None:
    """Reject values that cannot be represented as finite canonical JSON."""
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must be finite")
        return
    if isinstance(value, list | tuple):
        for index, item in enumerate(value):
            _validate_json(item, f"{path}[{index}]")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} keys must be strings")
            _validate_json(item, f"{path}.{key}")
        return
    if isinstance(value, BaseModel):
        _validate_json(value.model_dump(mode="json"), path)
        return
    raise ValueError(f"{path} contains non-JSON value {type(value).__name__}")


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None or value.utcoffset() != timedelta(0):
        raise ValueError("datetime must be timezone-aware UTC")
    return value


def _json_object(value: JsonObject) -> JsonObject:
    _validate_json(value)
    return _deep_freeze(value)


def _freeze_fence_map(value: Mapping[str, NonNegativeInt]) -> Mapping[str, NonNegativeInt]:
    if any(not key for key in value):
        raise ValueError("resource IDs must be non-empty")
    return _deep_freeze(value)


class StrictModel(BaseModel):
    """Frozen Pydantic wire DTO base with a closed schema and finite numbers."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False, validate_default=True)

    @field_validator("*", mode="after")
    @classmethod
    def serialized_values_are_immutable(cls, value: Any, info: Any) -> Any:
        if (isinstance(value, str) and (info.field_name == "id" or info.field_name.endswith("_id"))
                and value == ""):
            raise ValueError("IDs must be non-empty")
        if isinstance(value, tuple) and (info.field_name.endswith("_ids") or info.field_name == "source_ids"):
            if any(not item for item in value):
                raise ValueError("IDs must be non-empty")
        return _deep_freeze(value)

    @field_serializer("*", when_used="json")
    def serialized_values_are_plain_json(self, value: Any) -> Any:
        return _deep_thaw(value)


class SkillKind(StrEnum):
    INSPECT = "inspect"
    TRAVEL = "travel"
    RECOVER = "recover"
    VERIFY = "verify"
    DELIVER = "deliver"
    HOLD = "hold"
    WAIT = "wait"


class CommandState(StrEnum):
    PREPARED = "PREPARED"
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    RUNNING = "RUNNING"
    CONTROLLER_DONE = "CONTROLLER_DONE"
    OUTCOME_VERIFIED = "OUTCOME_VERIFIED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class Pose(StrictModel):
    x: float
    y: float
    z: float = 0.0
    yaw: float = 0.0


class VersionVector(StrictModel):
    graph_version: NonNegativeInt
    policy_epoch: NonNegativeInt
    coordinator_epoch: NonNegativeInt
    task_version: NonNegativeInt = 0
    dependency_versions: Mapping[str, NonNegativeInt] = Field(default_factory=dict)


class Observation(StrictModel):
    id: str
    tenant_id: str = "demo"
    episode_id: str
    robot_id: str
    occurred_at: datetime
    recorded_at: datetime
    world_tick: NonNegativeInt
    expires_tick: NonNegativeInt
    predicate: str
    value: bool | float | str | None
    pose: Pose
    frame: str = "map"
    visibility: str
    scope: JsonObject = Field(default_factory=dict)
    quality: JsonObject = Field(default_factory=dict)
    sensor_config_hash: str
    subject_id: str = "corridor-c"

    @field_validator("occurred_at", "recorded_at")
    @classmethod
    def timestamps_are_utc(cls, value: datetime) -> datetime:
        return _require_utc(value)

    @field_validator("scope", "quality")
    @classmethod
    def metadata_is_json(cls, value: JsonObject) -> JsonObject:
        return _json_object(value)

    @field_validator("value")
    @classmethod
    def observation_value_is_finite(cls, value: bool | float | str | None) -> bool | float | str | None:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("observation value must be finite")
        return value

    @model_validator(mode="after")
    def expiry_is_exclusive(self) -> Observation:
        if self.expires_tick <= self.world_tick:
            raise ValueError("expires_tick must be greater than world_tick")
        return self


class ActionProposal(StrictModel):
    id: str
    robot_id: str
    task_id: str
    kind: SkillKind
    parameters: JsonObject
    expected_versions: VersionVector
    required_predicates: tuple[str, ...]
    required_resource_ids: tuple[str, ...]
    expected_effects: tuple[str, ...]
    corridor_id: str = "corridor-c"

    @field_validator("parameters")
    @classmethod
    def parameters_are_json(cls, value: JsonObject) -> JsonObject:
        return _json_object(value)


class GovernanceWitness(StrictModel):
    id: str
    kind: Literal["restriction", "permission", "release"]
    decision_id: str
    owner_id: str
    span_id: str
    corridor_id: str
    action_kinds: tuple[SkillKind, ...]
    robot_types: tuple[str, ...]
    state: Literal["active", "staged", "released"]
    effective_from_tick: NonNegativeInt = 0
    effective_to_tick: NonNegativeInt | None = None
    restriction_id: str | None = None
    source_valid: bool
    owner_valid: bool
    approved: bool
    integrity_errors: tuple[str, ...]

    @model_validator(mode="after")
    def interval_is_half_open(self) -> GovernanceWitness:
        if self.effective_to_tick is not None and self.effective_to_tick <= self.effective_from_tick:
            raise ValueError("effective interval must be non-empty and half-open")
        return self


class EvidenceBundle(StrictModel):
    observations: tuple[Observation, ...]
    planning_facts: tuple[JsonObject, ...]
    governance_candidates: tuple[GovernanceWitness, ...]
    integrity_errors: tuple[str, ...]
    versions: VersionVector
    completeness: Literal["complete", "truncated", "unavailable", "invalid"]

    @field_validator("planning_facts")
    @classmethod
    def facts_are_json(cls, values: tuple[JsonObject, ...]) -> tuple[JsonObject, ...]:
        for value in values:
            _json_object(value)
        return values


class Claim(StrictModel):
    id: str
    task_id: str
    robot_id: str
    holder_id: str
    coordinator_epoch: NonNegativeInt
    fence: NonNegativeInt
    resource_fences: Mapping[str, NonNegativeInt]
    lease_expires_at_utc: datetime
    clock_domain: Literal["coordinator_epoch_utc_lease_v1"]
    state: Literal["active", "released"]

    @field_validator("resource_fences")
    @classmethod
    def resource_ids_are_nonempty(cls, value: Mapping[str, NonNegativeInt]) -> Mapping[str, NonNegativeInt]:
        return _freeze_fence_map(value)

    @field_validator("lease_expires_at_utc")
    @classmethod
    def lease_expiry_is_utc(cls, value: datetime) -> datetime:
        return _require_utc(value)


class AuthorizationResult(StrictModel):
    authorization_id: str
    status: Literal["ALLOW", "DENY", "NEEDS_EVIDENCE", "NEEDS_APPROVAL", "STALE"]
    reason_codes: tuple[str, ...]
    witness_ids: tuple[str, ...]
    versions: VersionVector
    action_payload_hash: str
    valid_until_tick: NonNegativeInt
    claim_id: str
    task_id: str
    robot_id: str
    fence: NonNegativeInt
    resource_fences: Mapping[str, NonNegativeInt]
    governance_integrity_version: NonNegativeInt

    @field_validator("resource_fences")
    @classmethod
    def resource_ids_are_nonempty(cls, value: Mapping[str, NonNegativeInt]) -> Mapping[str, NonNegativeInt]:
        return _freeze_fence_map(value)


class CommandIntent(StrictModel):
    command_id: str
    proposal: ActionProposal
    payload_hash: str
    claim_id: str
    fence: NonNegativeInt
    resource_fences: Mapping[str, NonNegativeInt]
    authorization_id: str
    policy_epoch: NonNegativeInt
    coordinator_epoch: NonNegativeInt
    dispatch_sequence: PositiveInt
    effective_world_tick: NonNegativeInt
    authorization: AuthorizationResult

    @field_validator("resource_fences")
    @classmethod
    def resource_ids_are_nonempty(cls, value: Mapping[str, NonNegativeInt]) -> Mapping[str, NonNegativeInt]:
        return _freeze_fence_map(value)

    @model_validator(mode="after")
    def bindings_match(self) -> CommandIntent:
        expected_hash = payload_hash_for_proposal(self.proposal)
        auth = self.authorization
        bindings = (
            self.payload_hash == expected_hash,
            auth.action_payload_hash == expected_hash,
            self.authorization_id == auth.authorization_id,
            self.claim_id == auth.claim_id,
            auth.status == "ALLOW",
            self.effective_world_tick < auth.valid_until_tick,
            self.fence == auth.fence,
            self.proposal.task_id == auth.task_id,
            self.proposal.robot_id == auth.robot_id,
            self.proposal.expected_versions == auth.versions,
            self.proposal.expected_versions.policy_epoch == self.policy_epoch,
            self.proposal.expected_versions.coordinator_epoch == self.coordinator_epoch,
            auth.versions.policy_epoch == self.policy_epoch,
            auth.versions.coordinator_epoch == self.coordinator_epoch,
            self.resource_fences == auth.resource_fences,
            self.policy_epoch == auth.versions.policy_epoch,
            self.coordinator_epoch == auth.versions.coordinator_epoch,
        )
        if not all(bindings):
            raise ValueError("command intent proposal, authorization, and fence bindings must match")
        return self


class DispatchEvent(StrictModel):
    id: str
    tenant_id: str = "demo"
    sequence: PositiveInt
    coordinator_epoch: NonNegativeInt
    kind: Literal["COMMAND", "POLICY_ACTIVATION", "REVOCATION", "FENCE_INSTALL", "EPOCH_BARRIER"]
    payload: JsonObject
    payload_hash: str
    effective_world_tick: NonNegativeInt

    @field_validator("payload")
    @classmethod
    def payload_is_json(cls, value: JsonObject) -> JsonObject:
        return _json_object(value)

    @model_validator(mode="after")
    def hash_matches_payload(self) -> DispatchEvent:
        if self.payload_hash != canonical_json_hash(self.payload):
            raise ValueError("payload_hash does not match payload")
        return self


class CommandReceipt(StrictModel):
    command_id: str
    payload_hash: str
    state: CommandState
    world_tick: NonNegativeInt
    accepted_sequence: NonNegativeInt
    last_known_state: CommandState | None = None
    reason_codes: tuple[str, ...] = ()
    observations: tuple[Observation, ...] = ()


class DecisionRequest(StrictModel):
    id: str
    family_id: str
    claim: str
    span: JsonObject
    labels: tuple[str, ...]
    context: str = ""
    source_ids: tuple[str, ...]
    versions: VersionVector

    @field_validator("span")
    @classmethod
    def span_is_json(cls, value: JsonObject) -> JsonObject:
        return _json_object(value)


class DecisionResult(StrictModel):
    request_id: str
    status: Literal["ok", "disabled", "abstain", "unavailable", "invalid", "refused"]
    probabilities: dict[str, float]
    provider: str
    model: str
    usage: JsonObject
    latency_ms: NonNegativeInt
    reason: str | None = None

    @field_validator("probabilities", "usage")
    @classmethod
    def result_maps_are_json(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _json_object(value)


class FleetEvent(StrictModel):
    id: str
    type: str
    episode_id: str
    world_tick: NonNegativeInt
    sequence: NonNegativeInt
    payload: JsonObject
    recorded_at: datetime

    @field_validator("payload")
    @classmethod
    def payload_is_json(cls, value: JsonObject) -> JsonObject:
        return _json_object(value)

    @field_validator("recorded_at")
    @classmethod
    def recorded_time_is_utc(cls, value: datetime) -> datetime:
        return _require_utc(value)


def canonical_json_hash(value: Any) -> str:
    """SHA-256 hex digest over compact, sorted-key UTF-8 JSON."""
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    _validate_json(value)
    encoded = json.dumps(_deep_thaw(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                         allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def payload_hash_for_proposal(proposal: ActionProposal) -> str:
    """Hash every serialized proposal field, including expected versions."""
    return canonical_json_hash(proposal)


def payload_hash(proposal: ActionProposal) -> str:
    """Return the canonical hash binding an ActionProposal."""
    return payload_hash_for_proposal(proposal)


def utc_to_ticks(value: datetime, epoch: datetime, tick_hz: int) -> int:
    """Map UTC time to ticks using exact integer timedelta arithmetic (ceiling)."""
    _require_utc(value)
    _require_utc(epoch)
    if isinstance(tick_hz, bool) or not isinstance(tick_hz, int) or tick_hz <= 0:
        raise ValueError("tick_hz must be a positive integer")
    delta = value - epoch
    microseconds = (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds
    scaled = microseconds * tick_hz
    return -((-scaled) // 1_000_000)


def make_id(prefix: str) -> str:
    """Create a prefixed, non-deterministic identifier for local proposals/events."""
    if not prefix or not isinstance(prefix, str):
        raise ValueError("prefix must be a non-empty string")
    return f"{prefix}_{uuid.uuid4().hex}"


__all__ = [
    "ActionProposal", "AuthorizationResult", "Claim", "CommandIntent", "CommandReceipt",
    "CommandState", "DecisionRequest", "DecisionResult", "DispatchEvent", "EvidenceBundle",
    "FleetEvent", "GovernanceWitness", "Observation", "Pose", "SkillKind", "StrictModel",
    "VersionVector", "canonical_json_hash", "make_id", "payload_hash",
    "payload_hash_for_proposal", "utc_to_ticks",
]
