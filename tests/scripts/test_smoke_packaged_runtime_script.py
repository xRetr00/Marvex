from __future__ import annotations

from pathlib import Path
import json


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
    assert "/browser-session/leases" in text
    assert "/sessions" in text
    assert "Invoke-RuntimeClaim" in text
    assert "[Diagnostics.Stopwatch]::StartNew()" in text
    assert "/v1/turns" in text
    assert "manifest.json" in text
    assert "provider_worker" in text
    assert "intent_worker" in text
    assert "tool_worker" in text
    assert "service.token" not in text


def test_packaging_uses_valid_wheel_filename_for_uv_install() -> None:
    tauri = json.loads((ROOT / "apps" / "shell" / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
    resources = tauri["bundle"]["resources"]
    resource_text = json.dumps(resources, sort_keys=True)
    smoke_text = SCRIPT.read_text(encoding="utf-8")

    assert "marvex-runtime.whl" not in resource_text
    assert "marvex-*.whl" in resource_text
    assert "../runtime/wheels" in resource_text
    assert 'Where-Object { $_.Name -ne "marvex-runtime.whl" }' in smoke_text
    assert "wheelhouseDest" in smoke_text


def test_packaging_bundles_node_and_playwright_mcp_runtime() -> None:
    tauri = json.loads((ROOT / "apps" / "shell" / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
    resource_text = json.dumps(tauri["bundle"]["resources"], sort_keys=True)
    build_text = (ROOT / "build-installer.ps1").read_text(encoding="utf-8")

    assert "../runtime/node.exe" in resource_text
    assert "../runtime/playwright-mcp" in resource_text
    assert "@playwright/mcp@" in build_text
    assert "node.exe" in build_text
    assert "cli.js" in build_text


def test_sha_manifest_generation_is_compatible_with_windows_powershell_5() -> None:
    ps1_text = (ROOT / "build-installer.ps1").read_text(encoding="utf-8")
    bat_text = (ROOT / "build-installer.bat").read_text(encoding="utf-8")

    assert "GetRelativePath" not in ps1_text
    assert "GetRelativePath" not in bat_text
    assert "Get-CompatibleRelativePath" in ps1_text


def test_packaging_keeps_voice_models_out_of_installer() -> None:
    tauri = json.loads((ROOT / "apps" / "shell" / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
    resources = tauri["bundle"]["resources"]
    resource_text = json.dumps(resources, sort_keys=True)
    manifest_text = (ROOT / "voice_models.manifest.json").read_text(encoding="utf-8")
    build_text = (ROOT / "build-installer.ps1").read_text(encoding="utf-8")
    smoke_text = SCRIPT.read_text(encoding="utf-8")

    assert "../../../voice_models.manifest.json" in resources
    assert "voice_models.manifest.json" in resource_text
    assert "voice-assets" not in resource_text
    assert "downloaded after installation" in manifest_text
    assert "fetch_voice_models.py" not in build_text
    assert "generate_wakeword_keywords.py" not in build_text
    assert "apps\\shell\\voice-assets" not in smoke_text
