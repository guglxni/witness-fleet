"""Trusted-local approval command contract.

The configured_local label describes caller-supplied local configuration only; it is
not cryptographic authentication or protection against in-process impersonation.
"""

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import Field, StrictStr, field_validator

from witness_fleet.domain import NonNegativeInt, StrictModel

Identifier = Annotated[StrictStr, Field(min_length=1, max_length=128)]
ApprovalNotes = Annotated[StrictStr, Field(max_length=512)]


class _ApprovalInput(StrictModel):
    event_id: StrictStr
    expected_policy_epoch: NonNegativeInt
    notes: ApprovalNotes = ""


class TrustedLocalPrincipal(StrictModel):
    actor_id: Identifier
    tenant_id: Literal["demo", "other"]
    role: Literal["maintenance_owner"]
    trust_mode: Literal["configured_local"]

    @field_validator("actor_id")
    @classmethod
    def actor_id_has_no_nul(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("actor_id must not contain NUL")
        return value


class ApprovalCommand(StrictModel):
    event_id: Identifier
    target_id: Identifier
    actor_id: Identifier
    tenant_id: Literal["demo", "other"]
    action: Literal["approve"] = "approve"
    expected_policy_epoch: NonNegativeInt
    notes: ApprovalNotes = ""

    @field_validator("event_id", "target_id", "actor_id")
    @classmethod
    def identifiers_have_no_nul(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("identifiers must not contain NUL")
        return value


def approval_command(
    *, request: Mapping[str, object], target_id: str, principal: TrustedLocalPrincipal
) -> ApprovalCommand:
    if not isinstance(principal, TrustedLocalPrincipal):
        raise TypeError("principal must be a TrustedLocalPrincipal instance")
    if not isinstance(request, Mapping):
        raise TypeError("request must be a mapping")
    validated = _ApprovalInput.model_validate(request)
    return ApprovalCommand(
        event_id=validated.event_id,
        target_id=target_id,
        actor_id=principal.actor_id,
        tenant_id=principal.tenant_id,
        action="approve",
        expected_policy_epoch=validated.expected_policy_epoch,
        notes=validated.notes,
    )
