# Graph authority, temporal validity and coordination mathematics

**Proposed contracts, not proven distributed-system guarantees.** Use RUNTIME.md for concrete clocks and sequenced policy propagation.

## 1. Temporal validity and scope

For approved governance record $d$ at effective simulation tick $t$, use half-open interval $valid(d,t)=[t_{from}\le t<t_{to}]$, with explicit unbounded end representation. The required clock domain is `simulation_tick_v1`; RUNTIME.md defines the fixed-episode UTC-to-tick conversion. Source UTC and real host wall time are not directly used as dispatch validity. Currentness also requires not explicitly superseded/revoked under the policy rules. `recorded_at` is not effective time; later ingestion never automatically gives higher authority.

Let $scope(d,a,r,\ell,c)$ match action, robot, load and corridor. Missing/wildcard scope is not permissive by default. A release $l$ lifts restriction $d$ only if it explicitly names $d$, has authenticated approved authority within the owner's scope, a valid interval, no unresolved contradiction, and a scope covering the particular proposed action. It cannot globally erase the restriction for unrelated actors/actions.

## 2. Deterministic permission

Let $B(a,s)$ be valid base permission, $D(a,s)$ all current applicable restrictions, and $Lifted(d,a,s)$ a checked release. Define:

$$PolicyAllow(a,s)=B(a,s)\land Integrity(s)\land\bigwedge_{d\in D(a,s)}Lifted(d,a,s).$$

`Integrity` includes complete authoritative witness and consistent relevant governance. Absence of a known restriction does not prove base permission. Missing/malformed query results or truncated policy enumeration means unknown/deny, not $D=\varnothing$.

Full admission is:

$$Admit(a,s)=PolicyAllow(a,s)\land PhysicalVerified(a,s)\land DependenciesReady(a,s)\land ClaimCurrent(a,s)\land ResourcesAvailable(a,s)\land VersionCurrent(a,s).$$

This is Boolean conjunction over explicit checks, **not multiplication of uncertain scores**. A model score cannot relax a term. All checks being true establishes only the modeled software contract, not certified physical safety.

## 3. Witness completeness

A governance witness must include the graph edges `Decision-IMPOSES->Restriction-APPLIES_TO->Corridor`, `Decision-OWNED_BY->Owner`, and `Decision-SUPPORTED_BY->EvidenceSpan-IN_REVISION->Revision-REVISION_OF->Source`; releases add `LIFTS`, `APPROVED_BY`, `SUPPORTED_BY`.

A MATCH that returns only complete paths can accidentally hide an incomplete restriction. Therefore perform tenant-wide governance integrity validation (including missing scope/target edges), enumerate all relevant restrictions and require every one to have a validated full witness; missing edges cause a hold. Unknown affected scope blocks tenant admissions until resolved. Semantic retrieval candidates are separate from this exhaustive set. This is why top-k retrieval cannot be the authorization query.

## 4. Evidence identity and immutable spans

Retain original source bytes $b$ with $h_b=SHA256(b)$. Strictly decode UTF-8, normalize newlines under normalizer version $v$, preserving codepoints, to text $u$. Retain $h_u=SHA256(UTF8(u))$. Span $(i,j,q)$ is valid iff $0\le i\le j\le len(u)$ and $q=u[i:j]$. Store revision ID and both hashes.

Hash equality establishes byte identity, not authenticity or truth. Approval is a separate authenticated event. SDK source-signature namespaces are not cryptographic signatures; optional chunk-local offsets need translation to this canonical convention.[79][80]

## 5. Claims, fences and idempotency

For task version $v$, current policy epoch $p$ and claim epoch $e$, a claim transition must compare expected $(v,p,e)$ plus availability/readiness and atomically create new owner/fence. Exactly one winning result is a required concurrent-test observation, not assumed from “writes serialize”. After every conflict/timeout reread actual state. Redis multi-command transactions do not provide rollback of earlier successful commands after an execution-time error.[6][31]

Fencing invariant: adapter accepts command with fence $f$ only if it equals the current permitted fence for that resource/task and coordinator epoch/sequence is synchronized. Once $f'$ supersedes $f$ with $f'>f$, old worker cannot act, even if it resumes believing its lease is valid. Lease expiry permits reassessment, not replay.

Idempotency invariant: event/command ID $k$ maps to exactly one payload hash $h$. Repeating $(k,h)$ returns prior receipt/state; $(k,h')$ with $h'\ne h$ rejects. The external effect still requires reconciliation after uncertainty; no distributed exactly-once guarantee follows from deduplicating a table.

## 6. Snapshot consistency and invalidation

A snapshot witness records graph version, policy epoch and exact dependency versions. Prefer one query for relevant paths; for a bundle use version-before/version-after and retry if changed. At admission validate expected versions in the transition. Relevant updates invalidate dependencies; unrelated high-frequency sensor writes need not cancel every plan.

Policy commit and simulator actuation are ordered through the RUNTIME transition sequencer, not one fictitious distributed transaction. Pending revocation stops new affected admissions until propagated. In-flight effects cannot be undone; measure controlled-stop behavior after the effective tick.

## 7. Recovery properties

Critical records acknowledged as durable must be included in the selected persistence contract. Test app restart, DB process restart, container recreation and restore separately. AOF fsync policy has performance/durability tradeoffs; actual image configuration and source-file persistence must be verified.[11][12]

After restore compare epoch/fences/command journal with simulator state. If ordering cannot be proven, hold. Old graph data cannot safely authorize a newer world merely because queries now return successfully.

## 8. Monotonicity properties for tests

- Adding an unlifted applicable restriction cannot enable an action.
- Removing provenance/approval cannot enable an action.
- Making supporting physical evidence older cannot make it fresh.
- Increasing robot footprint under fixed free-space evidence cannot improve clearance.
- A higher fence permanently invalidates earlier fences for the same ownership domain.
- Missing response/unknown state cannot become verified outcome without new evidence.

Property tests validate the implemented model under sampled/constructed cases; they do not establish universal theorem-level system guarantees.

<!-- GENERATED CITATION REFERENCES -->

## Sources

[6] https://docs.falkordb.com/design/concurrency.md — Atomicity and Concurrency Control in FalkorDB
[11] https://docs.falkordb.com/operations/durability/index.md — FalkorDB Durability and Data Persistence Guide
[12] https://docs.falkordb.com/operations/durability/persistence.md — Configuring RDB & AOF Data Persistence in Docker
[31] https://redis.io/docs/latest/develop/using-commands/transactions — Transactions | Docs
[79] https://github.com/FalkorDB/GraphRAG-SDK/blob/35e67a0b27fdcc7f2c28508b09e86169851a8187/graphrag_sdk/src/graphrag_sdk/ingestion/extraction_strategies/graph_extraction.py — GraphRAG SDK: span extraction and propagation
[80] https://github.com/FalkorDB/GraphRAG-SDK/blob/35e67a0b27fdcc7f2c28508b09e86169851a8187/graphrag_sdk/src/graphrag_sdk/ingestion/chunking_strategies/fixed_size.py — GraphRAG SDK: fixed-size chunk offsets
