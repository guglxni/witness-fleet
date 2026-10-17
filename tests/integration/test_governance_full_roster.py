from test_governance_integrity import valid_snapshot
from test_governance_roster import bind_roster

from witness_fleet.graph.governance import validate_governance


def test_full_roster_document_cannot_be_replaced_by_embedded_subobject(tmp_path):
    snapshot, sources = valid_snapshot(tmp_path)
    roster = next(n for n in snapshot['nodes'] if n['id'] == 'roster-span')
    roster_revision = next(n for n in snapshot['nodes'] if n['id'] == 'roster-rev')
    old = sources.get(roster_revision['revision_id']).text_path.read_text()
    full = 'prefix data\n' + old + '\nconflicting suffix'
    source = sources.retain('mixed-roster', full.encode())
    span = sources.validate_span(source.revision_id, len('prefix data\n'), len('prefix data\n')+len(old), old)
    roster.update(start_char=span['start'], end_char=span['end'], quote=span['quote'], quote_hash=span['quote_hash'])
    roster_revision.update(revision_id=source.revision_id, content_hash=source.bytes_hash,
                           normalized_hash=source.normalized_hash)
    next(n for n in snapshot['nodes'] if n['id'] == 'roster-source')['source_id'] = 'mixed-roster'
    _, errors = validate_governance(snapshot, sources)
    assert any('INVALID_OWNER_ROSTER' in error for error in errors)


def test_roster_action_duplicates_cannot_be_accepted_as_enum_scope(tmp_path):
    snapshot, sources = valid_snapshot(tmp_path)
    bind_roster(snapshot, sources, actions=('travel', 'travel', 'deliver'))
    _, errors = validate_governance(snapshot, sources)
    assert any('INVALID_OWNER_ROSTER' in error for error in errors)
