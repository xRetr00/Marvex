from __future__ import annotations

from services.core.main import CoreServiceEntrypointConfig, create_control_plane_service_app


def test_core_control_plane_uses_persistent_voice_worker_control() -> None:
    runtime = create_control_plane_service_app(
        config=CoreServiceEntrypointConfig(local_auth_token="fake-control-token")
    )
    headers = {"authorization": "Bearer fake-control-token"}

    started = runtime.dispatch(
        method="POST",
        path="/control/voice/worker/start",
        headers=headers,
        body=b"{}",
    )
    status = runtime.dispatch(
        method="GET",
        path="/control/voice/worker",
        headers=headers,
    )

    assert started.status == "200 OK"
    assert started.payload["status"]["lifecycle_state"] == "running"
    assert status.status == "200 OK"
    assert status.payload["lifecycle_state"] == "running"

    runtime.dispatch(
        method="POST",
        path="/control/voice/worker/stop",
        headers=headers,
        body=b"{}",
    )
