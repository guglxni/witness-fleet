import pytest
from pydantic import ValidationError

from witness_fleet.runtime.approval import (
    ApprovalCommand,
    TrustedLocalPrincipal,
    approval_command,
)


def test_valid_approval_command_preserves_trusted_fields_and_round_trips():
    principal = TrustedLocalPrincipal(
        actor_id="owner/é.%2F",
        tenant_id="demo",
        role="maintenance_owner",
        trust_mode="configured_local",
    )
    request = {
        "event_id": "evt/é.%2F",
        "expected_policy_epoch": 0,
        "notes": "reviewed",
    }
    request_before = request.copy()

    command = approval_command(
        request=request,
        target_id="target/é.%2F",
        principal=principal,
    )

    assert command == ApprovalCommand(
        event_id="evt/é.%2F",
        target_id="target/é.%2F",
        actor_id="owner/é.%2F",
        tenant_id="demo",
        action="approve",
        expected_policy_epoch=0,
        notes="reviewed",
    )
    assert ApprovalCommand.model_validate_json(command.model_dump_json()) == command
    with pytest.raises(ValidationError):
        command.notes = "changed"
    assert request == request_before


def test_command_rejects_forbidden_request_fields():
    principal = TrustedLocalPrincipal(
        actor_id="owner",
        tenant_id="demo",
        role="maintenance_owner",
        trust_mode="configured_local",
    )
    for key, value in (
        ("actor_id", "untrusted"),
        ("tenant_id", "other"),
        ("target_id", "other-target"),
        ("action", "reject"),
    ):
        with pytest.raises(ValidationError):
            approval_command(
                request={"event_id": "evt", "expected_policy_epoch": 0, key: value},
                target_id="target",
                principal=principal,
            )


def test_command_rejects_invalid_identifier_and_notes_boundaries():
    principal = TrustedLocalPrincipal(
        actor_id="owner",
        tenant_id="demo",
        role="maintenance_owner",
        trust_mode="configured_local",
    )
    for event_id in ("", "e" * 129, "evt\x00id"):
        with pytest.raises(ValidationError):
            approval_command(
                request={"event_id": event_id, "expected_policy_epoch": 0},
                target_id="target",
                principal=principal,
            )
    for notes in ("n" * 513, 5):
        with pytest.raises(ValidationError):
            approval_command(
                request={"event_id": "evt", "expected_policy_epoch": 0, "notes": notes},
                target_id="target",
                principal=principal,
            )

    for target_id in ("", "t" * 129, "target\x00id"):
        with pytest.raises(ValidationError):
            approval_command(
                request={"event_id": "evt", "expected_policy_epoch": 0},
                target_id=target_id,
                principal=principal,
            )


def test_factory_requires_validated_principal_instance():
    request = {"event_id": "evt", "expected_policy_epoch": 0}

    for principal in (
        None,
        {
            "actor_id": "owner",
            "tenant_id": "demo",
            "role": "maintenance_owner",
            "trust_mode": "configured_local",
        },
        type("Lookalike", (), {"actor_id": "owner", "tenant_id": "demo"})(),
    ):
        with pytest.raises(TypeError, match="principal must be a TrustedLocalPrincipal"):
            approval_command(request=request, target_id="target", principal=principal)


def test_factory_requires_mapping_request():
    principal = TrustedLocalPrincipal(
        actor_id="owner",
        tenant_id="demo",
        role="maintenance_owner",
        trust_mode="configured_local",
    )

    with pytest.raises(TypeError, match="request must be a mapping"):
        approval_command(request=["event", 0], target_id="target", principal=principal)


def test_principal_rejects_missing_required_fields():
    with pytest.raises(ValidationError):
        TrustedLocalPrincipal(actor_id="owner", tenant_id="demo", role="maintenance_owner")


def test_command_rejects_missing_policy_epoch():
    with pytest.raises(ValidationError):
        approval_command(
            request={"event_id": "evt"},
            target_id="target",
            principal=TrustedLocalPrincipal(
                actor_id="owner",
                tenant_id="demo",
                role="maintenance_owner",
                trust_mode="configured_local",
            ),
        )


def test_command_rejects_non_integer_or_negative_policy_epoch():
    principal = TrustedLocalPrincipal(
        actor_id="owner",
        tenant_id="demo",
        role="maintenance_owner",
        trust_mode="configured_local",
    )
    for epoch in (True, 1.0, "1", -1):
        with pytest.raises(ValidationError):
            approval_command(
                request={"event_id": "evt", "expected_policy_epoch": epoch},
                target_id="target",
                principal=principal,
            )


def test_command_defaults_action_to_approve():
    command = ApprovalCommand(
        event_id="event",
        target_id="target",
        actor_id="owner",
        tenant_id="demo",
        expected_policy_epoch=0,
    )

    assert command.action == "approve"


def test_command_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        ApprovalCommand(
            event_id="event",
            target_id="target",
            actor_id="owner",
            tenant_id="demo",
            action="approve",
            expected_policy_epoch=0,
            surprise="no",
        )


def test_principal_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        TrustedLocalPrincipal(
            actor_id="owner",
            tenant_id="demo",
            role="maintenance_owner",
            trust_mode="configured_local",
            extra="no",
        )


def test_principal_actor_id_requires_bounded_non_nul_exact_string():
    for actor_id in ("", "a" * 129, "owner\x00id"):
        with pytest.raises(ValidationError):
            TrustedLocalPrincipal(
                actor_id=actor_id,
                tenant_id="demo",
                role="maintenance_owner",
                trust_mode="configured_local",
            )
    with pytest.raises(ValidationError):
        TrustedLocalPrincipal(
            actor_id=123,
            tenant_id="demo",
            role="maintenance_owner",
            trust_mode="configured_local",
        )
