from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "smoke_packaged_runtime.ps1"


def test_packaged_runtime_smoke_script_documents_runtime_contract() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "target\\release\\marvex-service.exe" in text
    assert "--console" in text
    assert "NamedPipeClientStream" in text
    assert '{"request":"token_lease"}' in text
    assert "/health" in text
    assert "/control/health" in text
    assert "/control/state" in text
    assert "/control/state/stream" in text
    assert "/v1/turns" in text
    assert "manifest.json" in text
    assert "provider_worker" in text
    assert "intent_worker" in text
    assert "tool_worker" in text
    assert "service.token" not in text
