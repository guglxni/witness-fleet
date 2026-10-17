# Architecture decision records

These accepted entries are **design decisions**, not completed implementation. Date: 15 October 2026.

| ADR | Decision | Alternatives/reason | Revisit trigger |
|---|---|---|---|
| ADR-001 | One all-track scout/recovery/courier product | Three unrelated demos obscure the causal loop | Organizer eligibility changes |
| ADR-002 | Canonical per-tenant FalkorDB ops graph | Decorative graphs/opaque corpus IDs cannot show authority relationships | New scale or tenant constraints |
| ADR-003 | Direct episode/task persistence plus one narrow GraphRAG-SDK corpus lane | Deeper structured-ingestion audit supersedes Graphiti-first preference | SDK gate fails or measured retrieval need |
| ADR-004 | Deterministic authorizer, separate advisory classifier | Confidence is not permission; symbolic success is not physical evidence | Never remove to improve a score |
| ADR-005 | MuJoCo original simple assets; single physics owner | Awign reuse rights unresolved and not an integrated fleet; full ROS/Isaac adds risk | Native smoke gate fails |
| ADR-006 | Planar simulator only for unit tests/debug | Tests policy but not contact/recovery fidelity | User approves lower-fidelity scope and revised claims |
| ADR-007 | Single coordinator first; concurrent claim clients in tests | Centralized autonomy is adequate, not decentralized consensus | Proven multi-writer need |
| ADR-008 | Graph action ledger plus simulator-owned durable receipts | Checkpoints alone cannot establish external effects | Simulator receipt contract changes |
| ADR-009 | Model-free baseline always; System One shadow before activation | Unmeasured classifier must not become a dependency | Held-out per-family benefit established |
| ADR-010 | Microsoft-Decision-1 first hosted candidate; Jev/OpenAI optional | Deployment observed historically, not benchmarked; distinct APIs | Availability/quality/cost/user choice changes |
| ADR-011 | SDK isolated worker/environment | Provider/dependency mismatch and destructive graph surfaces | Compatible shared environment demonstrated |
| ADR-012 | All applicable restrictions checked outside ranking | Top-k may hide governance; recency is not authority | No automatic relaxation |
| ADR-013 | Original synthetic sources/identities | Real employer data unnecessary and event-restricted | Explicit lawful authorization plus compatible rules |
| ADR-014 | Application-owned immutable revisions/approval | Corpus replacement is not revision history | Upstream contract proven equivalent |
| ADR-015 | No training/new frameworks before complete incident | Integration count is not capability | Measured bottleneck plus written experiment |

## Change process

Append a proposed ADR with reason, affected requirements/tests, migration/rollback and evidence needed. Accepted replacement marks the older record superseded; do not delete rationale. Scope cuts must be explicit and user-visible, not silently marked complete.
