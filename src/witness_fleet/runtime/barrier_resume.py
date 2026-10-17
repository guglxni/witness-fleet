"""Trusted in-process graph-proven barrier resume and explicit recovery."""
from datetime import UTC, datetime

from witness_fleet.domain import DispatchEvent
from witness_fleet.runtime.barrier_provenance import validate_barrier


class InjectedBarrierCrash(BaseException):
    """Fault injection modeling abrupt process loss without ordinary exception cleanup."""


class TrustedBarrierResumer:
    """Use retained graph proof to invoke the private simulator resume path.

    This wrapper is a trusted in-process boundary, not an HTTP API or Python sandbox.
    Ordinary event delivery never calls this class and receives no equality capability.
    """

    def __init__(self, graph, service, holder_id, *, clock=None):
        self.graph = graph
        self.service = service
        self.holder_id = holder_id
        self.clock = clock or (lambda: datetime.now(UTC))

    def _validate(self, event):
        if not isinstance(event, DispatchEvent):
            raise ValueError("typed immutable retained graph barrier required")
        now = self.clock()
        if (not isinstance(now, datetime) or now.tzinfo is None
                or now.utcoffset() != UTC.utcoffset(now)):
            raise ValueError("barrier resume clock must be explicit UTC")
        return validate_barrier(self.graph, event, holder_id=self.holder_id, now_utc=now)

    def resume(self, event, *, fault_at=None):
        """Admit an exact next-cursor graph barrier and clear only reconciliation HOLD."""
        if fault_at not in {None, "before_admission", "after_journal_commit",
                            "before_native_release", "after_native_release"}:
            raise ValueError("unsupported barrier admission fault point")
        provenance = self._validate(event)
        return self.service._trusted_barrier_resume(
            event, provenance_identity=provenance,
            revalidate=lambda: self._validate(event), fault_at=fault_at)

    def recover(self, event, *, fault_at=None):
        """Explicitly finish a previously committed barrier; startup never calls this."""
        if fault_at not in {None, "after_held_checkpoint", "after_release_checkpoint"}:
            raise ValueError("unsupported barrier recovery fault point")
        provenance = self._validate(event)
        return self.service._recover_committed_barrier(
            event, provenance_identity=provenance,
            revalidate=lambda: self._validate(event), fault_at=fault_at)
