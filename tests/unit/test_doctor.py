from witness_fleet.doctor import dependency_report


def test_missing_package_report_is_not_a_success():
    report = dependency_report(packages=["witness-fleet-definitely-missing-package"])
    assert report["status"] == "blocked"
    assert report["packages"][0]["status"] == "missing"
    assert report["packages"][0]["version"] is None


def test_installed_package_records_real_version():
    report = dependency_report(packages=["mujoco", "fastapi", "falkordb"])
    assert report["status"] == "ok"
    assert all(row["version"] for row in report["packages"])
