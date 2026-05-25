import json

from packages.capability_runtime import AutonomyMode, AutonomyPolicy
from packages.control_plane_api.approvals import InMemoryApprovalStore
from packages.control_plane_api.models import ControlPlaneSnapshot
from packages.learning_runtime import LearningCandidateStore, LearningPipelineRunner
from tests.control_plane_api.asgi_helpers import asgi_call, create_control_plane_test_app


def _call(app, path: str, *, method: str = "GET", body: dict | None = None):
    status, _headers, payload = asgi_call(app, path, method=method, token="dev-token", body=body)
    return status, payload


def test_feedback_api_ingests_lists_and_applies_learning_candidates_through_protected_api() -> None:
    store = LearningCandidateStore()
    runner = LearningPipelineRunner(store=store, autonomy_policy=AutonomyPolicy.for_mode(AutonomyMode.AUTO_MARVEX))
    app = create_control_plane_test_app(
        approval_store=InMemoryApprovalStore(),
        snapshot=ControlPlaneSnapshot.foundation_default(schema_version="1"),
        local_auth_token="dev-token",
        learning_store=store,
        learning_runner=runner,
    )
    feedback = {
        "trace_id": "trace-feedback",
        "turn_id": "turn-feedback",
        "signal_kind": "user_correction",
        "payload": {"text": "Prefer official source citations.", "applies_to": "grounded_answer"},
        "raw_feedback_persisted": False,
    }

    submit_status, submit_payload = _call(app, "/control/feedback", method="POST", body=feedback)
    list_status, list_payload = _call(app, "/control/feedback")
    candidates_status, candidates_payload = _call(app, "/control/learning/candidates")
    candidate_id = candidates_payload["preference_candidates"][0]["candidate_id"]
    apply_status, apply_payload = _call(app, f"/control/learning/candidates/{candidate_id}/apply", method="POST")

    assert submit_status == "200 OK"
    assert submit_payload["preference_candidates"]
    assert list_status == "200 OK"
    assert list_payload["event_count"] == 1
    assert candidates_status == "200 OK"
    assert candidates_payload["skill_candidates"]
    assert apply_status == "200 OK"
    assert apply_payload["status"] == "applied"
    assert "raw_feedback_persisted\": true" not in json.dumps(candidates_payload).lower()
    assert json.dumps(apply_payload).lower().find("raw_candidate_payload_persisted\": true") == -1
