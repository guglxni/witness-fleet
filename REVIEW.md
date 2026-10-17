# Independent specification review and disposition

**Document review only.** No database query, robot simulation, policy implementation or model inference was exercised. Reviewers see proposed contracts; their findings do not establish runtime defects or runtime safety.

## Initial independent cross-document review

The reviewer inspected architecture, graph schema, runtime, decision contracts, requirements, evaluation and math. It returned five concrete issues:

| Finding | Disposition in this package | Required future proof |
|---|---|---|
| Corridor queries can miss orphan/scope-incomplete restrictions | GRAPH_SCHEMA Q-002 and math/GRAPH_AUTHORITY require tenant-wide integrity enumeration; unknown affected scope blocks tenant admissions | Remove scope/applicability/ownership/support edges; action cannot become permitted |
| Policy validity had ambiguous UTC versus tick domains | RUNTIME §1 and schema define `simulation_tick_v1`, explicit tick fields, fixed episode UTC mapping and source/audit UTC separately | Boundary conversion, paused clock, restart epoch, late activation tests |
| Sequencer lacked durable graph ordering/replay contract | RUNTIME §2 defines global sequence, atomic domain+outbox mutation, journal cursor, idempotency, gaps, barrier and cancellation disposition | Kill around each commit/send/ack boundary, missing/reordered/late events |
| Authorization receipt referenced but not modeled | GRAPH_SCHEMA defines immutable AuthorizationReceipt/witness edges and W-004 checks; RUNTIME/program design bind IDs, payload, versions, fences and expiry | Mutate payload/actor/task/claim/dependency/epoch and reject stale receipt |
| Claim lease field drift | GRAPH_SCHEMA uses `lease_expires_at_utc`, coordinator epoch/domain and per-resource fences, matching RUNTIME | Clock jump/restart and stale worker tests; persisted monotonic deadlines not reusable |

The first and fifth were independently being corrected during parent integration; the reviewer read an earlier snapshot. All five are design corrections, not measured implementation fixes.

## Additional parent review corrections

- Specified Map/Location/Corridor route edges and Episode→corridor/robot/hazard/map retrieval edges previously described only in query prose.
- Distinguished three-class SENTLI illustration from application F-001's four labels; no accidental wire-schema substitution.
- Removed the mathematically unnecessary fallback-error independence condition from the one-step expected-loss equation; conditional routed-subset calibration remains necessary.
- Labeled sequential latency sum as an approximation, not a sum of overlapping concurrent durations.
- Replaced citation to SDK docs for provider-confidence semantics with the actual confidence documentation.
- Removed claims that external documentation proves local non-execution.
- Separated backend-derived synthetic owner approval from cryptographic signing and production IAM.
- Preserved protected instruction-file consent block rather than writing alternate instruction files.

## Follow-up review and final clarification

A bounded second read confirmed written repairs to policy clock mapping, authorization receipts, canonical lease fields and durable sequencing. It still flagged restart cancellation/sequence ambiguity. The retained follow-up log was truncated, so it is not treated as a full approval or evidence of any unobserved wording; no runtime behavior was tested.

The parent subsequently clarified:
- CancellationDisposition is a separate immutable reconciliation record referencing the original event ID/sequence/hash, not a new payload reusing its sequence. A privileged **hold-only** reconciliation operation installs the new epoch fence before proving NEVER_ADMITTED; it cannot command movement. Missing/unknown receipts stay held. This avoids waiting for an ordered barrier behind the very gap being repaired.
- Integrity scanning starts independently from all governance entity types, including a Decision missing its IMPOSES/GRANTS edge, rather than only restrictions reachable from a corridor. Unknown affected scope blocks tenant admissions.

These final clarifications have documentation checks but have not received a subsequent independent runtime/schema implementation test. Do not present the review as an unconditional safety approval.

## Review limitations

The follow-up review is bounded to the repaired runtime/schema contracts. Source metadata/link checks are separate from methods interpretation. Citation-reference validation proves identity consistency, not entailment coverage or fact-check completeness. All actual behavior still requires PLAN's tests and independently reviewed implementation.
