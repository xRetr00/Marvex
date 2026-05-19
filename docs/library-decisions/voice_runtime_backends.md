# Library Decision: Voice Runtime Backend Stack

library name: moonshine-voice, FunASR, sherpa-onnx, Kokoro-ONNX, Piper TTS, stream2sentence, Silero VAD, webrtcvad-wheels, and sounddevice

official source: PyPI package indexes plus upstream project repositories for each package. Marvex validates actual compatibility through `uv` resolution against the local project stack.

maintenance status: Active or usable enough for adapter-backed evaluation as of May 19, 2026 based on successful `uv pip install --dry-run -e . ...` and `uv add ...` resolution in this repo. Full model runtime behavior still depends on explicitly installed local model/voice assets.

why use it: Voice runtime should not custom-build STT, TTS, wakeword, VAD, or streaming sentence detection engines. These packages provide maintained engine paths while Marvex keeps orchestration, policy, privacy, and Control Plane surfaces in `packages.voice_runtime` behind adapters.

why not custom code: Custom audio inference, speech synthesis, wakeword, VAD, and sentence segmentation would create low-quality infrastructure, higher maintenance risk, and likely privacy mistakes. Marvex only owns the bounded orchestration, selector, safe envelope, and model/voice management seams.

fallback if abandoned: Keep the `VoiceRuntime` backend interfaces stable and swap to a CLI/subprocess or alternate adapter. If a direct dependency conflicts, document the exact `uv` resolver or `pip check` blocker and keep the backend available only as an external command seam.

pyproject dependency: moonshine-voice

declared dependency: moonshine-voice==0.0.59

pyproject dependency: funasr

declared dependency: funasr==1.3.1

pyproject dependency: sherpa-onnx

declared dependency: sherpa-onnx==1.13.2

pyproject dependency: sherpa-onnx-core

declared dependency: sherpa-onnx-core==1.13.2

pyproject dependency: kokoro-onnx

declared dependency: kokoro-onnx==0.5.0

pyproject dependency: piper-tts

declared dependency: piper-tts==1.4.2

pyproject dependency: stream2sentence

declared dependency: stream2sentence==0.3.2

pyproject dependency: silero-vad

declared dependency: silero-vad==6.2.1

pyproject dependency: webrtcvad-wheels

declared dependency: webrtcvad-wheels==2.0.14

pyproject dependency: sounddevice

declared dependency: sounddevice==0.5.5

verified date: 2026-05-19

verified by: Codex

uv compatibility result: `uv pip install --dry-run -e . moonshine-voice funasr sherpa-onnx kokoro-onnx piper-tts stream2sentence silero-vad webrtcvad-wheels` resolved successfully. `uv add ...` installed the packages, then `uv run python -m pip check` initially reported `sherpa-onnx 1.13.2 requires sherpa-onnx-core, which is not installed`; adding `sherpa-onnx-core==1.13.2` fixed the check.

architecture fit: Good when isolated behind `packages.voice_runtime` and `packages.voice_worker_runtime` adapters. Moonshine v2 is the main STT backend id, SenseVoice-Small via FunASR is fallback STT, sherpa-onnx is the ASR/KWS/TTS/VAD secondary seam, Kokoro-ONNX is main TTS, Piper is fallback TTS, Silero is main VAD, webrtcvad-wheels is fallback VAD, stream2sentence is evaluated behind the sentence clamp adapter, and sounddevice owns local microphone/playback device access behind a mockable worker adapter.

adopt / defer / reject decision: Adopt direct dependencies and keep real model execution explicit and model/voice-asset controlled. No raw audio or generated audio is persisted by default. The Control Plane can list/select/test/download safe projections, but the frontend does not run engines directly.

risks: The stack is heavy and installs PyTorch and ONNX-related packages. Actual model downloads can be large and must remain explicit user-triggered operations into safe local model directories. Backend exceptions must be mapped into `VoiceErrorEnvelope` without raw provider or engine text.
