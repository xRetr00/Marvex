from apps.cli.main import SERVICE_VERSION as CLI_VERSION
from packages.core.service import SERVICE_VERSION as CORE_VERSION
from packages.local_api.runner import SERVICE_VERSION as LOCAL_API_VERSION
from packages.local_service_startup.startup import DEFAULT_SERVICE_VERSION
from packages.version import MARVEX_VERSION
from packages.voice_worker_runtime.models import VoiceWorkerVersionInfo
from services.desktop_agent.models import SERVICE_VERSION as DESKTOP_AGENT_VERSION
from services.intent_worker.models import SERVICE_VERSION as INTENT_WORKER_VERSION
from services.provider_worker.models import SERVICE_VERSION as PROVIDER_WORKER_VERSION
from services.tool_worker.models import SERVICE_VERSION as TOOL_WORKER_VERSION
from services.voice_worker.models import SERVICE_VERSION as VOICE_WORKER_VERSION


def test_python_runtime_versions_use_the_packaged_marvex_version() -> None:
    assert MARVEX_VERSION == "0.2.1"
    assert {
        CLI_VERSION,
        CORE_VERSION,
        LOCAL_API_VERSION,
        DEFAULT_SERVICE_VERSION,
        DESKTOP_AGENT_VERSION,
        INTENT_WORKER_VERSION,
        PROVIDER_WORKER_VERSION,
        TOOL_WORKER_VERSION,
        VOICE_WORKER_VERSION,
        VoiceWorkerVersionInfo(worker="voice-worker").worker_version,
    } == {MARVEX_VERSION}
