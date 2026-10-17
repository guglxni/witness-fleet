"""Trusted in-process HOLD and cancellation reconciliation boundary."""

from datetime import UTC, datetime

from witness_fleet.domain import DispatchEvent

_HOLD_REASON = "trusted_local_reconciliation"


def _valid_now(clock):
    now = clock()
    if (not isinstance(now, datetime) or now.tzinfo is None
            or now.utcoffset() != UTC.utcoffset(now)):
        raise ValueError("reconciliation clock must be explicit UTC")
    return now


def _lease_identity(root, holder_id, clock):
    if not isinstance(root, dict):
        raise ValueError("current coordinator lease is unavailable")
    epoch = root.get("coordinator_epoch")
    if type(epoch) is not int or epoch < 0:
        raise ValueError("coordinator epoch must be an exact nonnegative integer")
    if not isinstance(holder_id, str) or not holder_id or root.get("coordinator_holder_id") != holder_id:
        raise ValueError("coordinator lease does not belong to configured holder")
    lease_text = root.get("coordinator_lease_expires_at_utc")
    if not isinstance(lease_text, str) or not lease_text:
        raise ValueError("valid UTC coordinator lease is required")
    try:
        lease = datetime.fromisoformat(lease_text.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("valid UTC coordinator lease is required") from None
    if lease.tzinfo is None or lease.utcoffset() != UTC.utcoffset(lease):
        raise ValueError("valid UTC coordinator lease is required")
    if lease <= _valid_now(clock):
        raise ValueError("coordinator lease is expired")
    return (holder_id, epoch, lease_text)


class TrustedLocalReconciler:
    """Trusted-local, fail-closed wrapper around native durable reconciliation.

    This is not an HTTP API or an in-process security sandbox. It cannot allocate
    epochs, release HOLD, or issue barriers.
    """

    def __init__(self, graph, service, holder_id, clock=None):
        self.graph = graph
        self.service = service
        self.holder_id = holder_id
        self.clock = clock or (lambda: datetime.now(UTC))

    def _current_lease(self):
        return _lease_identity(self.graph.read_version_root(), self.holder_id, self.clock)

    def _assert_lease_unchanged(self, expected):
        if self._current_lease() != expected:
            raise ValueError("coordinator lease changed; reconciliation authority is stale")

    def hold(self):
        """Install or confirm durable HOLD at the configured live graph epoch."""
        with self.service._lock:
            lease = self._current_lease()
            _, epoch, _ = lease
            identity = self.service.journal.identity()
            local_epoch = identity.get("coordinator_epoch")
            if type(local_epoch) is not int or local_epoch < 0:
                raise ValueError("local coordinator epoch is invalid")
            if epoch < local_epoch or (epoch == local_epoch and not identity.get("held")):
                raise ValueError("graph epoch must be higher than local epoch unless already held")
            if epoch > local_epoch:
                self.service.journal.hold_for_reconciliation(epoch, reason=_HOLD_REASON)
                if self.service.world is not None:
                    self.service.world.hold(_HOLD_REASON, source_id=_HOLD_REASON)
                self.service._synchronize_journal_hold()
            elif (self.service.world is not None
                  and self.service.journal._meta("reconciliation_hold_epoch") == str(epoch)
                  and identity.get("hold_reason") == _HOLD_REASON):
                self.service.world.hold(_HOLD_REASON, source_id=_HOLD_REASON)
            self.service._save()
            self._assert_lease_unchanged(lease)
            return {"status": "HELD", "coordinator_epoch": epoch,
                    "reason": self.service.journal.identity()["hold_reason"]}

    def cancel_prepared(self, event):
        """Cancel only a command proven by the native journal never to be admitted."""
        if not isinstance(event, DispatchEvent):
            raise ValueError("typed immutable DispatchEvent required")
        event = DispatchEvent.model_validate(event.model_dump(mode="json"))
        if event.kind != "COMMAND":
            raise ValueError("only a typed COMMAND event can be cancelled")
        with self.service._lock:
            lease = self._current_lease()
            identity = self.service.journal.identity()
            if (identity.get("held") is not True
                    or type(identity.get("coordinator_epoch")) is not int
                    or identity["coordinator_epoch"] != lease[1]):
                raise ValueError("current graph lease must match the durable held epoch")
            durable_event = event.model_dump(mode="json")
            proof = self.service.journal.prove_never_admitted(durable_event)
            if proof.get("status") != "NEVER_ADMITTED":
                raise ValueError("native journal cannot prove command was never admitted")
            disposition = self.service.journal.record_cancellation_disposition(
                durable_event, proof=proof,
            )
            self._assert_lease_unchanged(lease)
            return disposition
