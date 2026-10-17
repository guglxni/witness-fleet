

def test_measurement_capture_records_actual_tick_contact_and_pixels(tmp_path):
    from scripts.capture_simulation import capture
    result = capture(tmp_path, seed=3, render=False)
    assert result['status'] == 'native-component-measurement'
    assert result['world_tick'] > 0
    assert result['recovery']['contact_count'] > 0
    assert result['recovery']['measured_displacement_m'] >= .75
    assert result['hidden_state_access'] == 'evaluator-only'
    assert result['fleet_acceptance'] is False
    assert (tmp_path / 'measurements.json').exists()
    assert not (tmp_path / 'recovery.mp4').exists()
