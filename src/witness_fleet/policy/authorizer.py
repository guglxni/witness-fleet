"""Pure deterministic authorization over a complete evidence bundle."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from witness_fleet.domain import (
    ActionProposal,
    AuthorizationResult,
    Claim,
    EvidenceBundle,
    GovernanceWitness,
    canonical_json_hash,
)

from .observations import evaluate_observation


def _active_at(witness: GovernanceWitness, tick: int) -> bool:
    return witness.effective_from_tick <= tick and (
        witness.effective_to_tick is None or tick < witness.effective_to_tick
    )


def _scope_matches(witness: GovernanceWitness, proposal: ActionProposal, robot_type: str) -> bool:
    """Match an explicit scope; `all_entry` is the parent DTO's blanket-role marker."""
    corridor_matches = witness.corridor_id in {proposal.corridor_id, "*", "all"}
    blanket = bool({"all_entry", "all", "*"} & set(witness.robot_types))
    # A role wildcard is never an action wildcard: governance must name every
    # action it permits or restricts, including when its role scope is broad.
    action_matches = proposal.kind in witness.action_kinds
    role_matches = robot_type in witness.robot_types or blanket
    return corridor_matches and action_matches and role_matches


def _release_valid(release: GovernanceWitness, restriction: GovernanceWitness,
                   proposal: ActionProposal, robot_type: str, tick: int) -> bool:
    return (
        release.kind == "release"
        and release.restriction_id == restriction.id
        and release.state == "released"
        and release.source_valid
        and release.owner_valid
        and release.approved
        and not release.integrity_errors
        and _active_at(release, tick)
        and release.corridor_id == restriction.corridor_id == proposal.corridor_id
        and set(release.action_kinds).issubset(set(restriction.action_kinds))
        and set(release.robot_types).issubset(set(restriction.robot_types))
        and proposal.kind in release.action_kinds
        and robot_type in release.robot_types
    )


def _make_result(proposal: ActionProposal, evidence: EvidenceBundle, claim: Claim,
                 status: str, reasons: Iterable[str], witnesses: Iterable[str],
                 valid_until: int) -> AuthorizationResult:
    # Stable content-derived receipt identity; no randomness or external state.
    reason_tuple = tuple(sorted(set(reasons)))
    witness_tuple = tuple(sorted(set(witnesses)))
    digest = canonical_json_hash({"proposal": proposal.model_dump(mode="json"),
                                  "evidence_versions": evidence.versions.model_dump(mode="json"),
                                  "claim": claim.model_dump(mode="json"), "status": status,
                                  "reasons": reason_tuple, "witnesses": witness_tuple,
                                  "valid_until": valid_until})
    return AuthorizationResult(
        authorization_id=f"auth_{digest[:32]}", status=status, reason_codes=reason_tuple,
        witness_ids=witness_tuple, versions=evidence.versions,
        action_payload_hash=canonical_json_hash(proposal), valid_until_tick=max(0, valid_until),
        claim_id=claim.id, task_id=proposal.task_id, robot_id=proposal.robot_id,
        fence=claim.fence, resource_fences=claim.resource_fences,
        governance_integrity_version=evidence.versions.policy_epoch,
    )


def authorize(
    proposal: ActionProposal,
    evidence: EvidenceBundle,
    claim: Claim,
    *,
    now_tick: int,
    now_utc: datetime,
    robot_type: str,
) -> AuthorizationResult:
    """Authorize only when bundle, claim, physical evidence, and all governance agree.

    No graph, model, network or hidden simulator truth is consulted. `planning_facts`
    cannot substitute for the proposal's required fresh observation predicates.
    """
    if type(now_tick) is not int:
        raise TypeError("now_tick must be an exact integer")
    reasons: set[str] = set()
    witnesses: set[str] = set()
    valid_until = max(now_tick + 1, 0)
    if now_utc.tzinfo is None or now_utc.utcoffset() is None or now_utc.utcoffset().total_seconds() != 0:
        raise ValueError("now_utc must be timezone-aware UTC")
    if now_tick < 0:
        raise ValueError("now_tick must be non-negative")

    # An explicit execution window is part of the hashed proposal payload and
    # must be well-formed even when another admission check would fail later.
    execution_until = proposal.parameters.get("execution_until_tick")
    bounded_window = "execution_until_tick" in proposal.parameters
    timeout_ticks = proposal.parameters.get("timeout_ticks", 2000)
    if bounded_window and (
        type(execution_until) is not int
        or type(timeout_ticks) is not int
        or timeout_ticks <= 0
        or not now_tick < execution_until <= now_tick + min(timeout_ticks, 2000)
    ):
        return _make_result(proposal, evidence, claim, "DENY", ("INVALID_EXECUTION_WINDOW",), (), valid_until)

    # Bundle quality is checked before any positive inference.
    if evidence.completeness != "complete" or evidence.integrity_errors:
        reasons.add("EVIDENCE_BUNDLE_INCOMPLETE")
        reasons.update("GOVERNANCE_INTEGRITY" for _ in evidence.integrity_errors)
        witnesses.update(w.id for w in evidence.governance_candidates if w.integrity_errors)
        return _make_result(proposal, evidence, claim, "STALE", reasons, witnesses, valid_until)
    if evidence.versions != proposal.expected_versions:
        reasons.add("VERSION_MISMATCH")
        return _make_result(proposal, evidence, claim, "STALE", reasons, witnesses, valid_until)
    if (claim.state != "active" or claim.task_id != proposal.task_id
            or claim.robot_id != proposal.robot_id or claim.holder_id != proposal.robot_id
            or claim.coordinator_epoch != proposal.expected_versions.coordinator_epoch
            or claim.lease_expires_at_utc <= now_utc
            or claim.resource_fences.keys() != set(proposal.required_resource_ids)):
        reasons.add("CLAIM_STALE_OR_MISMATCHED")
        return _make_result(proposal, evidence, claim, "STALE", reasons, witnesses, valid_until)

    governance = tuple(evidence.governance_candidates)
    # Positive authority requires an enumerated corridor, action and role scope.
    # Blanket markers are meaningful only for conservative restrictions.
    invalid_permissions = tuple(item for item in governance if item.kind == "permission"
        and (item.corridor_id in {"", "*", "all"} or not item.action_kinds or not item.robot_types
             or any(role not in {"scout", "recovery", "courier"} for role in item.robot_types)))
    if invalid_permissions:
        return _make_result(proposal, evidence, claim, "DENY", ("INVALID_PERMISSION_SCOPE", "NO_BASE_PERMISSION"),
                            (item.id for item in invalid_permissions), valid_until)
    for item in governance:
        # Integrity is not hidden by scope or candidate order. Staged proposals are inert;
        # an apparently active invalid witness is an integrity failure.
        if item.integrity_errors or (item.state in {"active", "released"}
                and not (item.source_valid and item.owner_valid and item.approved)):
            witnesses.add(item.id)
            reasons.add("GOVERNANCE_INTEGRITY")
    if "GOVERNANCE_INTEGRITY" in reasons:
        return _make_result(proposal, evidence, claim, "NEEDS_APPROVAL", reasons, witnesses, valid_until)

    active_restrictions = tuple(item for item in governance if item.kind == "restriction"
                                and item.state == "active" and _active_at(item, now_tick))
    staged_restrictions = tuple(item for item in governance if item.kind == "restriction"
                                and item.state == "staged" and _active_at(item, now_tick))
    active_permission = any(item.kind == "permission" and item.state == "active"
        and item.source_valid and item.owner_valid and item.approved and not item.integrity_errors
        and _active_at(item, now_tick) and _scope_matches(item, proposal, robot_type)
        for item in governance)
    if bounded_window:
        active_permission = active_permission and any(
            item.kind == "permission" and item.state == "active"
            and item.source_valid and item.owner_valid and item.approved and not item.integrity_errors
            and item.effective_from_tick <= now_tick
            and (item.effective_to_tick is None or item.effective_to_tick >= execution_until)
            and _scope_matches(item, proposal, robot_type)
            for item in governance
        )
    if not active_permission:
        reasons.add("NO_BASE_PERMISSION")

    denied = False
    staged_block = False
    horizon_restrictions = tuple(
        item for item in governance if bounded_window and item.kind == "restriction"
        and item.state in {"active", "staged"}
        and item.effective_from_tick < execution_until
        and (item.effective_to_tick is None or item.effective_to_tick > now_tick)
        and _scope_matches(item, proposal, robot_type)
    )
    for restriction in active_restrictions:
        applicable = _scope_matches(restriction, proposal, robot_type)
        if not applicable:
            continue
        if not (restriction.source_valid and restriction.owner_valid and restriction.approved):
            reasons.add("GOVERNANCE_INTEGRITY")
            witnesses.add(restriction.id)
            continue
        matching_releases = [release for release in governance
                             if release.restriction_id == restriction.id
                             and release.state in {"active", "staged", "released"}
                             and _active_at(release, now_tick)]
        valid_releases = [release for release in matching_releases
                          if _release_valid(release, restriction, proposal, robot_type, now_tick)]
        if bounded_window:
            valid_releases = [release for release in valid_releases
                              if release.effective_from_tick <= now_tick
                              and (release.effective_to_tick is None
                                   or release.effective_to_tick >= execution_until)]
        if valid_releases:
            continue
        if any(release.kind == "release" and release.restriction_id == restriction.id
               and release.state == "staged" and not release.approved for release in matching_releases):
            staged_block = True
            reasons.add("RELEASE_NOT_APPROVED")
            witnesses.update(r.id for r in matching_releases if r.kind == "release")
        elif _scope_matches(restriction, proposal, robot_type):
            denied = True
            reasons.add("ACTIVE_RESTRICTION")
            witnesses.add(restriction.id)

    # A staged restriction can indicate a pending policy transition for an otherwise blocked action.
    for restriction in staged_restrictions:
        if restriction.corridor_id == proposal.corridor_id and _scope_matches(restriction, proposal, robot_type):
            staged_block = True
            reasons.add("RESTRICTION_PENDING_APPROVAL")
            witnesses.add(restriction.id)
    for restriction in horizon_restrictions:
        if restriction.state == "active":
            if restriction in active_restrictions and any(
                release.kind == "release" and release.restriction_id == restriction.id
                and _release_valid(release, restriction, proposal, robot_type, now_tick)
                and release.effective_from_tick <= now_tick
                and (release.effective_to_tick is None
                     or release.effective_to_tick >= execution_until)
                for release in governance
            ):
                continue
            denied = True
            reasons.add("ACTIVE_RESTRICTION")
            witnesses.add(restriction.id)
        else:
            staged_block = True
            reasons.add("RESTRICTION_PENDING_APPROVAL")
            witnesses.add(restriction.id)

    if denied:
        status = "DENY"
    elif staged_block:
        status = "NEEDS_APPROVAL"
    elif "GOVERNANCE_INTEGRITY" in reasons:
        status = "NEEDS_APPROVAL"
    elif not active_permission:
        status = "DENY"
    else:
        missing = []
        for predicate in proposal.required_predicates:
            physical = evaluate_observation(evidence.observations, predicate,
                subject_id=proposal.corridor_id, robot_id=proposal.robot_id, robot_type=robot_type,
                now_tick=now_tick, now_utc=now_utc,
                expected_scope={key: proposal.parameters[key] for key in ("footprint", "payload_class")
                                if key in proposal.parameters})
            if physical.status != "VERIFIED":
                missing.append(predicate)
        if missing:
            status = "NEEDS_EVIDENCE"
            reasons.add("REQUIRED_OBSERVATION_MISSING_OR_UNSAFE")
        else:
            status = "ALLOW"
            # Finite admission horizon; never extend beyond retained observation TTL.
            valid_until = now_tick + 2000
    valid_until = min([valid_until] + [item.expires_tick for item in evidence.observations
                                      if item.predicate in proposal.required_predicates
                                      and item.robot_id == proposal.robot_id
                                      and item.subject_id == proposal.corridor_id
                                      and item.world_tick <= now_tick and now_tick < item.expires_tick
                                      and item.recorded_at <= now_utc and item.occurred_at <= now_utc])
    valid_until = min([valid_until] + [item.effective_to_tick for item in governance
                                      if item.effective_to_tick is not None
                                      and item.effective_from_tick <= now_tick < item.effective_to_tick])
    return _make_result(proposal, evidence, claim, status, reasons, witnesses, valid_until)
