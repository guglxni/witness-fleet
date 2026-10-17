# Security, trust boundaries, and safety limits

This is a source-grounded description of the local synthetic demo and its intended containment boundaries. It is not a penetration-test report, safety case, or real-robot operating authorization. The larger requirements catalogue in [`SECURITY.md`](../../SECURITY.md) explicitly labels many invariants and test paths as proposed.

## Trust boundaries

1. **Browser to API:** request fields are untrusted. Mission controller binds actor, task plan and expected evidence to the retained fixture; the UI cannot supply ALLOW or manufacture sensor results ([`runtime/mission.py`](../../src/witness_fleet/runtime/mission.py)).
2. **Coordinator to graph:** canonical evidence and governance snapshots must be complete, correctly scoped, integrity-checked and version-current; stale versions, malformed records or governance integrity errors cannot yield allow ([`graph/governance.py`](../../src/witness_fleet/graph/governance.py), [`policy/authorizer.py`](../../src/witness_fleet/policy/authorizer.py)).
3. **Graph to simulator:** the local adapter accepts typed hash-bound events only; the service journals identities and fences before advancing the native controller ([`runtime/local_adapter.py`](../../src/witness_fleet/runtime/local_adapter.py), [`services/simulator/service.py`](../../services/simulator/service.py), [`services/simulator/journal.py`](../../services/simulator/journal.py)).
4. **Simulator world to policy:** policy consumes projected sensor DTOs and native outcome receipts, not arbitrary mutable `MjData`. In the documented deployment of this demo both app and simulator are in the local trust domain; the Python boundary is not an OS sandbox ([`services/simulator/world.py`](../../services/simulator/world.py), [`services/simulator/sensors.py`](../../services/simulator/sensors.py)).
5. **Optional retrieval/model provider:** untrusted source text and model output are not action authority. SC-001 publishes `model_mode: disabled`; no provider request is needed ([`runtime/coordinator.py`](../../src/witness_fleet/runtime/coordinator.py), [`DECISION_CONTRACTS.md`](../../DECISION_CONTRACTS.md)).

## Fail-closed behavior

The expected conservative response is HOLD/no admission when authority cannot be checked, when evidence is unknown or expired, when versions disagree, when an event/ack is missing, when a payload identity conflicts, when an operator principal/scope is invalid, or when an outcome cannot be verified. `UNKNOWN` is a reconciliation state, not a synonym for failure, safe-to-repeat, or success. See [`RUNTIME.md`](../../RUNTIME.md) and the executable [`runtime/execution.py`](../../src/witness_fleet/runtime/execution.py).

A release is an explicit local synthetic owner event with an exact target, checked expected policy epoch, retained source proof and fresh physical evidence. It only lifts its named release scope. This is not login, enterprise IAM, non-repudiation, cryptographic signing, or a public approval workflow ([`runtime/approval.py`](../../src/witness_fleet/runtime/approval.py), [`runtime/approval_writer.py`](../../src/witness_fleet/runtime/approval_writer.py)).

## Deployment controls that do and do not exist

The mission app binds to loopback via CLI and the launcher publishes a newly named graph container on a loopback ephemeral host port; it retains the created data rather than deleting old runs ([`cli.py`](../../src/witness_fleet/cli.py), [`scripts/run_local_mission.py`](../../scripts/run_local_mission.py)). This narrows exposure in the intended local demo; it is not a hardened production network boundary.

The repository includes a separate ACL/persistent graph profile in [`compose.yaml`](../../compose.yaml) and [`config/roles.acl`](../../config/roles.acl). Do not infer that the mission launcher's bare ephemeral graph container automatically uses those Compose ACL settings. Its launcher path is distinct and should only be used as documented for isolated local demonstration.

No remote endpoint should be exposed as-is. Before any hosted/public service, require a separately reviewed authentication/authorization, CSRF/origin, tenant provisioning and graph-key ACL strategy, credential rotation, audit/log redaction, backup/restore and denial-of-service controls. No deployment configuration for such a topology is ready here.

## Hazard communication

HOLD in this code is a software/simulation state. It does not prove an actual robot has physically stopped, that force has decayed safely, or that a human may enter a work zone. If this code is adapted to hardware, independently design and validate hardware-rated safety controllers, braking dynamics, emergency-stop chain, local watchdog and human procedures before enabling actuation. This guide is not an instruction to operate hardware.
