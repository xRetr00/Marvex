from scripts import check_file_size_policy, check_forbidden_modules, check_port_boundaries


def test_uv_virtualenv_is_excluded_from_repo_boundary_scans():
    assert ".venv" in check_forbidden_modules.EXCLUDED_PARTS
    assert ".venv" in check_file_size_policy.EXCLUDED_PARTS
    assert ".venv" in check_port_boundaries.EXCLUDED_PARTS
