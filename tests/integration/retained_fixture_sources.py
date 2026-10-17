"""Explicit retained roots for additive fixtures sharing one isolated graph."""

from witness_fleet.ingestion.source_store import SourceStore


class RetainedFixtureSources(SourceStore):
    def __init__(self, primary, *additional):
        super().__init__(primary)
        self.additional = tuple(SourceStore(root) for root in additional)

    def get(self, revision_id):
        try:
            return super().get(revision_id)
        except KeyError:
            for store in self.additional:
                try:
                    return store.get(revision_id)
                except KeyError:
                    continue
            raise
