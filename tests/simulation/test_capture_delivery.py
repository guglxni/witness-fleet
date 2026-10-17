def test_measurement_capture_includes_real_loaded_east_side_delivery(tmp_path):
    from scripts.capture_simulation import capture
    report=capture(tmp_path,seed=3,render=False)
    assert report['fleet_acceptance'] is False
    assert report['delivery']['status']=='done'
    assert report['delivery']['payload_id']=='capture-payload'
    assert report['delivery']['position'][0] > 3.7
