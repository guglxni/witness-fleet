# API and event contracts

**Planned HTTP/SSE interface. No endpoints are running.** Backend validates tenant/principal; clients cannot choose graph names, run arbitrary Cypher or set authority Booleans.

## Read projections

| Endpoint | Response purpose | Constraints |
|---|---|---|
| `GET /api/health` | Process health and dependency readiness separately | Healthy process is not ready-to-dispatch |
| `GET /api/state` | Current robots/tasks, graph/policy versions, sensor/model mode | No evaluator truth unless explicitly separate oracle endpoint |
| `GET /api/tasks/{id}` | DAG status, unmet predicates, claim and last command | Trusted tenant filter and stable IDs |
| `GET /api/decisions/{id}/witness` | Canonical evidence subgraph and reason codes | Exact stored edges/source locators; all restrictions |
| `GET /api/sources/{revision_id}` | Retained normalized revision plus hash/offset metadata | Synthetic/public allowlist; read-only |
| `GET /api/commands/{id}` | Intent, receipt, last known state and reconciliation | Unknown distinct from not-found |
| `GET /api/episodes/{id}` | Verified history and proposed procedures | No unvalidated automatic skill transfer |
| `GET /api/events` | SSE with stable event IDs and resume cursor | Backpressure bounded; reconnect rehydrates snapshot |
| `GET /api/evaluation/runs/{id}` | Run manifest and real metrics/trace links | Missing metrics null/unavailable, never placeholder success |

## Explicit commands

| Endpoint | Payload | Authorization/consistency |
|---|---|---|
| `POST /api/incidents` | Synthetic fixture ID, seed, idempotency event ID | Local operator; creates episode, cannot inject privileged labels into policy |
| `POST /api/tasks/{id}/inspect` | Requested bounded inspection and expected versions | Proposal only; normal authorizer/claim path |
| `POST /api/releases/{id}/approve` | Expected policy epoch, source revision/span, scope, event ID | Server-derived maintenance-owner principal, exact authority scope, audited diff |
| `POST /api/commands/{id}/reconcile` | Expected command/version, event ID | Reads receipt/evidence; cannot assert success by user Boolean |
| `POST /api/hold` | Scope and reason, event ID | Local conservative hold; cannot become general remote motor API |
| `POST /api/model-mode` | disabled/shadow/advisory, expected config version | Advisory only after declared evaluation gate; no authorization mode |

Future public deployment requires real authentication/session/CSRF/origin controls; local synthetic roles are not production IAM. Unknown path/tenant rejects. Error responses expose enum and correlation ID, not secrets, query text containing private values or raw provider body.

## Event envelope

```text
schema_version, event_id, tenant_context_id, episode_id,
event_type, occurred_at, recorded_at, world_tick,
graph_version, policy_epoch, coordinator_epoch, sequence,
subject_id, correlation_id, causation_id, payload_hash,
payload (typed per event)
```

Event types: observation_received, hypothesis_proposed/refuted, fact_accepted/expired, task_blocked/ready, claim_won/lost, authorization_result, command_prepared/sent/receipt/unknown, outcome_verified/failed, source_staged/promoted, restriction_activated, release_approved, revocation_pending/applied, model_assessment, provider_unavailable, recovery_reconciled.

SSE is a UI projection, not authoritative command delivery. Dropped events require snapshot rehydration from graph and event cursor; a disconnected UI marks state stale. UI cannot infer “no restrictions” because an event stream is empty.

## Error taxonomy

`INVALID_INPUT`, `NOT_FOUND`, `NOT_AUTHORIZED`, `NEEDS_EVIDENCE`, `NEEDS_APPROVAL`, `STALE_VERSION`, `CONFLICT`, `DEPENDENCY_UNAVAILABLE`, `UNKNOWN_OUTCOME`, `PROVIDER_REFUSAL`, `PROVIDER_INVALID`, `NOT_READY`.

Use explicit HTTP status mapping in implementation tests. Idempotency-key reuse with different payload returns conflict. Do not retry uncertain state-changing operations without identity-based reconciliation.
