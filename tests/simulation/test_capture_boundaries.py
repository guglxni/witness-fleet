def test_capture_actual_contact_force_is_within_native_acceptance(tmp_path):
    from scripts.capture_simulation import capture
    result = capture(tmp_path, seed=3, render=False)
    assert result['scope'] == 'native_component_only_not_integrated_fleet'
    assert result['recovery']['status'] == 'done'
    assert result['max_contact_force_n'] <= 120
    assert result['carton_displacement_m'] <= 1.6
