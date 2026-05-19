import io
import json
from wsgiref.util import setup_testing_defaults

from packages.capability_runtime import AutonomyMode, AutonomyPolicy
from packages.control_plane_api.app import create_control_plane_api_app
from packages.control_plane_api.approvals import InMemoryApprovalStore
from packages.control_plane_api.models import ControlPlaneSnapshot
from packages.learning_runtime import LearningCandidateStore, LearningPipelineRunner


def _call(app, path: str, *, method: str = "GET", body: dict | None = None):
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = method
    environ["PATH_INFO"] = path
    environ["HTTP_AUTHORIZATION"] = "Bearer dev-token"
    raw = json.dumps(body or {}).encode("utf-8")
    environ["wsgi.input"] = io.BytesIO(raw)
    environ["CONTENT_LENGTH"] = str(len(raw))
    captured = {}

    def start_response(status, headers, exc_info=None):
        captured["status"] = status

    payload = json.loads(b"".join(app(environ, start_response)).decode("utf-8"))
    return captured["status"], payload


def test_feedback_api_ingests_lists_and_applies_learning_candidates_through_protected_api() -> None:
    store = LearningCandidateStore()
    runner = LearningPipelineRunner(store=store, autonomy_policy=AutonomyPolicy.for_mode(AutonomyMode.AUTO_MARVEX))
    app = create_control_plane_api_app(
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
