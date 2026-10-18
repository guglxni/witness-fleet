"""The visitor diagram must present all real robots and no fabricated zones."""
from witness_fleet.hosting import _DEMO_HTML


def test_floor_projection_contains_courier_and_native_coordinates():
    assert 'id="courier"' in _DEMO_HTML
    assert 'Math.min(650,50+(Number(p.x)' not in _DEMO_HTML
    assert '350+(Number(p.x)||0)*45' in _DEMO_HTML
    assert 'SAFE ZONE' not in _DEMO_HTML
    assert 'World tick ·' not in _DEMO_HTML
    assert "travel:'Navigate corridor'" in _DEMO_HTML
    assert "verify:'Verify evidence'" in _DEMO_HTML
