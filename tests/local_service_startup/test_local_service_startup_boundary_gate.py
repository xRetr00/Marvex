from scripts import check_local_service_startup_boundaries


def test_local_service_startup_boundary_gate_passes():
    assert check_local_service_startup_boundaries.main() == 0

