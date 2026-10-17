import pytest
from retained_fixture_sources import RetainedFixtureSources

from witness_fleet.ingestion.source_store import SourceStore


def test_explicit_secondary_retention_is_available_and_writes_stay_primary(tmp_path):
    primary, secondary = tmp_path / 'primary', tmp_path / 'secondary'
    original = SourceStore(secondary).retain('bootstrap', b'authoritative retained source')
    combined = RetainedFixtureSources(primary, secondary)
    assert combined.get(original.revision_id) == original
    assert combined.validate_span(original.revision_id, 0, 13, 'authoritative')['source_id'] == 'bootstrap'
    written = combined.retain('approval', b'new approval source')
    assert written.bytes_path.is_relative_to(primary)


def test_corrupt_primary_cannot_be_hidden_by_valid_secondary(tmp_path):
    primary, secondary = tmp_path / 'primary', tmp_path / 'secondary'
    original = SourceStore(primary).retain('same', b'source')
    SourceStore(secondary).retain('same', b'source')
    original.bytes_path.write_bytes(b'tampered')
    with pytest.raises(ValueError, match='integrity'):
        RetainedFixtureSources(primary, secondary).get(original.revision_id)


def test_missing_everywhere_remains_missing(tmp_path):
    with pytest.raises(KeyError):
        RetainedFixtureSources(tmp_path / 'a', tmp_path / 'b').get('missing:' + '0' * 64)
