from pathlib import Path


def test_setup_does_not_reset_existing_vendor_or_delete_project_data():
    text = Path('scripts/setup.py').read_text()
    assert 'refusing to reset' in text
    assert 'rmtree' not in text
    assert 'down' not in text
    assert '--frozen' in text
