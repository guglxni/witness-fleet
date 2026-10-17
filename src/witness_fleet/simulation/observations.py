"""Convert explicit sensor returns only; unknown is never clear or absent."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from witness_fleet.domain import Observation, Pose, canonical_json_hash

Counter = Annotated[int, Field(strict=True, ge=0)]
Finite = Annotated[float, Field(strict=True, allow_inf_nan=False)]
ROLES = {'scout': .22, 'recovery': .38, 'courier': .50}


class SensorMetadata(BaseModel):
    mode: Literal['S0']
    expires_tick: Counter
    config_hash: str = Field(min_length=1)


class Visibility(BaseModel):
    state: Literal['visible', 'insufficient']
    fraction: Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]


class Gap(BaseModel):
    visibility: Literal['visible', 'insufficient']
    width_m: tuple[Finite, Finite]
    fits: dict[str, Annotated[bool, Field(strict=True)]]

    @model_validator(mode='after')
    def conservative_interval(self):
        if self.width_m[0] < 0 or self.width_m[1] < self.width_m[0] or set(self.fits) != set(ROLES):
            raise ValueError('bounded width interval and all explicit roles are required')
        return self


class Obstruction(BaseModel):
    state: Literal['observed', 'unknown', 'absent']


class SensorRecord(BaseModel):
    model_config = ConfigDict(extra='ignore')
    robot_id: str = Field(min_length=1)
    world_tick: Counter
    sensor: SensorMetadata
    pose: Pose
    visibility: Visibility
    gap: Gap | None
    obstruction: Obstruction

    @model_validator(mode='before')
    @classmethod
    def reject_boolean_pose(cls, value):
        if isinstance(value, dict) and isinstance(value.get('pose'), dict):
            if any(isinstance(coordinate, bool) for coordinate in value['pose'].values()):
                raise ValueError('sensor pose coordinates cannot be booleans')
        return value

    @model_validator(mode='after')
    def valid_lifetime(self):
        if self.sensor.expires_tick <= self.world_tick:
            raise ValueError('observation expiry must be after measured world tick')
        return self


def normalize_sensor_record(record, *, episode_id: str, robot_type: str,
                            occurred_at: datetime, recorded_at: datetime) -> tuple[Observation, ...]:
    if robot_type not in ROLES:
        raise ValueError('explicit configured robot role required')
    raw = SensorRecord.model_validate(record)
    observed = raw.visibility.state == 'visible' and raw.visibility.fraction >= .5
    gap_visible = observed and raw.gap is not None and raw.gap.visibility == 'visible'
    clearance = (raw.gap.fits[robot_type] and raw.gap.width_m[0] >= ROLES[robot_type]
                 if gap_visible and raw.gap is not None else None)
    obstruction = {'observed': True, 'absent': False, 'unknown': None}[raw.obstruction.state] if observed else None
    quality: dict = {'visibility_fraction': raw.visibility.fraction}
    if raw.gap:
        quality['width_interval_m'] = raw.gap.width_m
    scope = {'corridor_id': 'corridor-c', 'robot_type': robot_type,
             'footprint': ROLES[robot_type], 'payload_class': 'loaded' if robot_type == 'courier' else 'unloaded'}
    digest = canonical_json_hash({'episode_id': episode_id, 'record': raw.model_dump(mode='json'), 'role': robot_type})
    common = {'episode_id': episode_id, 'robot_id': raw.robot_id, 'occurred_at': occurred_at,
              'recorded_at': recorded_at, 'world_tick': raw.world_tick, 'expires_tick': raw.sensor.expires_tick,
              'pose': raw.pose, 'visibility': raw.visibility.state, 'scope': scope, 'quality': quality,
              'sensor_config_hash': raw.sensor.config_hash, 'subject_id': 'corridor-c'}
    return tuple(Observation(id=f'obs-{digest}-{predicate}', predicate=predicate, value=value, **common)
                 for predicate, value in (('clearance', clearance), ('obstruction', obstruction)))
