# Simulator reconciliation transport - trusted mutations remain proposed

## Current read-only lookup acceptance

The exact-ID/malformed-kind/HTTP-status repairs have completed matching bounded SPEC and QUALITY PASS, with35 lookup tests (including real loopback Uvicorn) and41 including transport-adjacent tests. Current hashes/limits are in artifacts/repair-wave/continue-current-manifest.json. The QUALITY depth/RecursionError note is not reproduced: its probe was explicitly approval-blocked and not retried. Read-only lookup still neither authorizes mutation nor resolves cancellation/HOLD. All mutation design below remains proposed, not implemented. The older read-only HOLD discussion is historical and is superseded only for the repaired bounded defects.


## Read-only slice state

`service.event`, `GET /events/{event_id:path}` and `client.query_event` now exist locally from deleg_396b1a64. Their acceptance remains HOLD: the parent reproduced uncaught TypeError for unhashable response kind values and failed literal percent/dot identifier round trips through TestClient. Independent SPEC/QUALITY reviews completed under deleg_052b1fa3 and both returned HOLD at all five matching current file hashes. Parent reran the focused two-file suite: 8 passed in 0.37s, but those tests do not cover the rejected cases. Detailed parent observations are in artifacts/repair-wave/event-lookup-parent-reconciliation.json; completed-review provenance is in artifacts/repair-wave/event-lookup-completed-reviews.json. No trusted hold/cancel mutation transport was implemented by that slice. The proposals and requirements below do not imply it exists or authorize paused graph/runtime actions.

## Acceptance and ownership

The parent owns the simulator HTTP/service/client integration boundary. This document is a design proposal only. Implementation is gated on independently accepted current journal/service contracts; graph-driven coordinator composition additionally requires the graph and runtime gates. The application graph and cached-record redesign remain approval-paused. Nothing here clears those approvals, changes existing records, or grants a browser/model policy authority.

## Required behavior

1. `GET /events/{event_id}` returns the immutable original event identity and its journal disposition. A missing identity is `NOT_FOUND`, never `NEVER_ADMITTED` or permission to resend.
2. `GET /commands/{command_id}` returns durable receipt/unknown overlay without starting or admitting a command.
3. A trusted takeover holds the native step owner before cancellation/proof issuance. Only a graph-allocated strictly higher coordinator epoch may fence an old owner. The simulator must never invent an epoch.
4. An unadmitted event can be cancelled only with an exact simulator-owned proof bound to the original immutable identity, current held epoch, and policy/task/resource fence snapshot. A caller's `approved`, actor string, model answer or arbitrary proof-shaped object is not authority.
5. The cancellation is a separate immutable disposition; it must not replace the old event body/hash. Applied commands cannot be classified as never admitted.
6. After proof-backed dispositions close every earlier sequence, a sequenced epoch barrier installs the already allocated epoch and clears ingress HOLD only if there are no unresolved receipts. Native physical HOLD and ingress readiness must be reconciled deliberately, not inferred from HTTP 200.

## Public method proposal

These are proposed signatures, not claims that routes exist:

```text
service.event(event_id) -> immutable event + journal status | NOT_FOUND
service.hold_for_reconciliation(higher_epoch, reason, trusted_context)
service.cancel_never_admitted(original_event, proof_id, trusted_context)
client.query_event(event_id)
client.hold_for_reconciliation(higher_epoch, reason)
client.cancel_never_admitted(original_event, proof_id)
```

The trusted context must come from the local backend integration session, not arbitrary request JSON. The current loopback/TrustedHost checks constrain network location but do not establish principal authorization. There is no permission to create a public control endpoint or to add credentials during this work.

## Sequence trace to verify

```text
restart/takeover
  -> graph allocates strictly higher epoch by fenced CAS
  -> trusted simulator hold at that exact epoch
  -> immutable event lookup + durable receipt lookup
  -> PREPARED/RECEIVED identity: exact never-admitted proof
  -> separate proof-backed cancellation disposition
  -> contiguous application of original sequence disposition
  -> ordered epoch barrier
  -> current-policy reauthorization for new commands
```

An admitted/unknown command takes the receipt/effect reconciliation path instead. It must not take the never-admitted path simply because a GET failed.

## Tests required before implementation acceptance

- Normal immutable event lookup, unknown ID, malformed ID and exact byte-preserving round trip.
- Network timeout, dropped response, non-object response, redirect and invalid status remain transport uncertainty, not effect failure.
- Untrusted callers cannot create higher epochs or submit proof authority; strict request schemas forbid extra actor/approval fields.
- Stale, numeric, mismatched, replayed or policy/fence-obsolete proof IDs fail closed.
- Cancellation retains the original command/event payload, handles repeated identical requests idempotently and does not admit motion.
- Deterministic independent-connection admission/cancellation race: no cancellation proof can win after ACCEPTED.
- Held native-world state persists over process restart; stale receipt/NOT_FOUND cannot clear it.
- Epoch barrier and restored checkpoint cannot resume unknown or unverified effects.
- Real HTTP process-kill integration and graph outage remain required after module tests; TestClient checks alone are not fleet acceptance.

## Open design decision

The specification requests a controlled local principal but the current HTTP service has no implemented trust-bearing session seam. Decide and review that seam before exposing hold/cancel mutations. It cannot be approximated with caller-provided roles, loopback location alone, hard-coded secrets, or arbitrary model claims.
