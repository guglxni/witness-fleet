# Additive owner-roster provenance contract

Owner identity, role and authority scope cannot be proved by unchecked graph properties. The operational source-binding extension adds `(Owner)-[:SUPPORTED_BY]->(EvidenceSpan)-[:IN_REVISION]->(Revision)-[:REVISION_OF]->(Source)` alongside the normative decision and release support branches.

The owner support span is the complete normalized synthetic JSON roster. It must be retained and hash/locator validated, contain exactly one matching `owner_id`, an explicit `maintenance_owner` role, an explicit corridor list, and explicit authorized `actions`. Decision/release action scopes must be subsets of the roster actions. `approved` in source JSON is not approval; the exact graph ApprovalEvent still supplies the server-side synthetic act.

Typed policy fields must reconcile with the owning Decision scope: Permission `action_kind` is one of the exact decision action kinds; Restriction `rule_type` is `prohibit`; `subject_scope` is an exact robot-role list encoded as JSON; `condition_json` contains exactly corridor_id and action_kinds with the same scope as the decision. Missing/ambiguous/conflicting fields fail closed.

The sample roster permits inspect/recover only; it cannot confer courier travel/delivery authority. Runtime promotion and graph persistence remain unverified until graph-write approval and exact DB tests.
