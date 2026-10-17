from witness_fleet.graph.governance import validate_governance


def test_every_governance_root_label_is_scanned_for_detachment():
    labels = ('Decision', 'Restriction', 'Permission', 'Release', 'ApprovalEvent', 'Owner')
    nodes = [{'labels': [label], 'id': f'orphan-{label.lower()}', 'state': 'active'}
             for label in labels]
    _, errors = validate_governance({'nodes': nodes, 'edges': []}, None)
    for node in nodes:
        assert f"DETACHED_GOVERNANCE:{node['id']}" in errors


def test_orphan_decision_root_is_not_invisible():
    _, errors = validate_governance(
        {'nodes': [{'labels': ['Decision'], 'id': 'decision-orphan', 'state': 'active'}], 'edges': []},
        None,
    )
    assert 'DETACHED_GOVERNANCE:decision-orphan' in errors


def test_detached_restriction_cannot_disappear_from_integrity_scan():
    witnesses, errors = validate_governance(
        {'nodes': [{'labels': ['Restriction'], 'id': 'ban', 'state': 'active'}], 'edges': []}, None
    )
    assert witnesses == ()
    assert 'DETACHED_GOVERNANCE:ban' in errors
