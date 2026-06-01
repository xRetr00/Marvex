from __future__ import annotations

import array
import math
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

from packages.voice_runtime import AudioRingBuffer, ChunkAggregator, EarlySpeechTrigger, PartialTranscriptBuffer, VADDecision, VoicePlaybackResult, VoiceRuntime, VoiceTurnRequest, select_early_speech
from packages.voice_runtime.adapters import SileroVadAdapter, WebRtcVadAdapter

from .assets import VoiceAssetManager, VoiceModelDownloadRequest, VoiceModelInstallRequest
from .audio import FakeLocalAudioAdapter, LocalAudioAdapter, PlaybackAdapterResult, SoundDeviceAudioAdapter
from .backend_runtime import VoiceWorkerBackendRuntime
from .models import (
    VoiceWorkerCommand,
    VoiceWorkerCommandResult,
    VoiceWorkerConfig,
    VoiceWorkerErrorEnvelope,
    VoiceWorkerEvent,
    VoiceWorkerEventType,
    VoiceWorkerHeartbeat,
    VoiceWorkerHealth,
    VoiceWorkerLifecycleState,
    VoiceWorkerStatus,
    VoiceWorkerVersionInfo,
)
from .projections import VoiceWorkerTurnRunResult, synthesis_summary, transcription_summary
from .supervision import (
    WakewordSupervisorHealth,
    WakewordSupervisorPolicy,
    WakewordSupervisorTickResult,
    WakewordWorkerSupervisor,
)


def _write_debug_wav(path: str, pcm_chunks: list[bytes], *, sample_rate: int) -> dict[str, object]:
    """Write captured int16 PCM to a WAV for offline KWS replay (opt-in debug).

    Returns a small projection (path + size) for the diagnostic sink. Only the
    user-requested debug dump path is written; never a default location.
    """

    import wave

    data = b"".join(pcm_chunks)
    try:
        with wave.open(path, "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(int(sample_rate))
            handle.writeframes(data)
        return {"path": path, "bytes": len(data), "sample_rate": int(sample_rate), "ok": True}
    except Exception as exc:  # never let a debug dump disrupt listening
        return {"path": path, "ok": False, "reason_code": type(exc).__name__}


def _frames_rms(frames: tuple[Any, ...]) -> float:
    """Root-mean-square amplitude of int16 PCM frames (0..~32767).

    A cheap "is sound reaching the model" probe for the wake-loop heartbeat.
    ~0 while the user speaks means the captured audio is silent (wrong/muted
    input device); a few hundred+ means real audio is flowing.
    """

    total_sq = 0.0
    count = 0
    for frame in frames:
        pcm = getattr(frame, "pcm", b"") or b""
        if not pcm:
            continue
        try:
            samples = array.array("h")
            samples.frombytes(pcm[: len(pcm) - (len(pcm) % 2)])
        except (ValueError, OverflowError):
            continue
        for sample in samples:
            total_sq += float(sample) * float(sample)
        count += len(samples)
    if count == 0:
        return 0.0
    return math.sqrt(total_sq / count)


def _adaptive_energy_floor(
    ambient_rms: float | None,
    *,
    base_floor: float,
    multiplier: float = 1.8,
    min_floor: float = 350.0,
) -> float:
    """Speech RMS threshold relative to the measured ambient noise floor.

    Hardcoded absolutes (the old 1200) silently break low-gain microphones:
    field logs had speech >1500, but a quieter mic sits at ambient ~490 / speech
    ~700-1000, so a 1200 floor reads every utterance as silence. Deriving the
    floor from the live ambient RMS tracks the mic instead of a magic number:
    high above ambient (so background noise is not speech) but low enough that
    real speech crosses it on any gain. Falls back to ``base_floor`` when no
    ambient estimate is available yet.
    """

    if ambient_rms and ambient_rms > 0:
        return max(min_floor, ambient_rms * multiplier)
    return base_floor


class VoiceWorkerController:
    def __init__(
        self,
        *,
        config: VoiceWorkerConfig | None = None,
        audio: LocalAudioAdapter | None = None,
        voice_runtime: VoiceRuntime | None = None,
        asset_manager: VoiceAssetManager | None = None,
        backend_runtime: VoiceWorkerBackendRuntime | None = None,
        wakeword_supervisor: WakewordWorkerSupervisor | None = None,
        wakeword_supervisor_policy: WakewordSupervisorPolicy | None = None,
    ) -> None:
        self.config = config or VoiceWorkerConfig.default()
        self.audio = audio or FakeLocalAudioAdapter()
        self.voice_runtime = voice_runtime or VoiceRuntime()
        self.asset_manager = asset_manager or VoiceAssetManager(asset_root=Path(".marvex") / "voice-assets")
        self.backend_runtime = backend_runtime or VoiceWorkerBackendRuntime(asset_manager=self.asset_manager)
        # Wire real PCM playback: when SoundDeviceAudioAdapter is used and has no
        # resolver yet, give it a direct handle to the generated-audio sink so that
        # play_audio calls receive actual synthesized PCM bytes instead of silence.
        if isinstance(self.audio, SoundDeviceAudioAdapter) and self.audio._pcm_resolver is None:
            self.audio._pcm_resolver = self.backend_runtime.generated_audio.resolve
        self._state = VoiceWorkerLifecycleState.STOPPED
        self._heartbeat: VoiceWorkerHeartbeat | None = None
        self._events: list[VoiceWorkerEvent] = []
        self._playback_status = "stopped"
        self._queued_tts_count = 0
        self._error: VoiceWorkerErrorEnvelope | None = None
        # True while the continuous wake loop owns the mic input stream. Command
        # handlers that read the mic (listen, speak barge-in) stand down then to
        # avoid a device-busy conflict on the single input device.
        self._continuous_active = False
        self.wakeword_supervisor: WakewordWorkerSupervisor = wakeword_supervisor or WakewordWorkerSupervisor(
            config=self.config,
            asset_manager=self.asset_manager,
            backend_runtime=self.backend_runtime,
            audio=self.audio,
            policy=wakeword_supervisor_policy,
        )

    def status(self) -> VoiceWorkerStatus:
        self.asset_manager.discover_installed()
        return VoiceWorkerStatus(
            worker_id=self.config.worker_id,
            lifecycle_state=self._state,
            process_started=self._state in {VoiceWorkerLifecycleState.RUNNING, VoiceWorkerLifecycleState.PAUSED},
            config=self.config,
            heartbeat=self._heartbeat,
            active_stt_backend_id=self.config.active_stt_backend_id,
            active_tts_backend_id=self.config.active_tts_backend_id,
            active_voice_id=self.config.active_voice_id,
            mic_status="started" if self._state in {VoiceWorkerLifecycleState.RUNNING, VoiceWorkerLifecycleState.PAUSED} else "stopped",
            playback_status=self._playback_status,
            wakeword_status="enabled" if self.config.wakeword.enabled else "disabled",
            queued_tts_count=self._queued_tts_count,
            recent_events=tuple(self._events[-20:]),
            error=self._error,
            model_assets=self.asset_manager.registry(),
            stt_backend_status=self.backend_runtime.stt_status(self.config.active_stt_backend_id),
            tts_backend_status=self.backend_runtime.tts_status(self.config.active_tts_backend_id, self.config.active_voice_id),
            wakeword_model_status=self.backend_runtime.wakeword_status(self.config.wakeword.backend_id),
            wakeword_supervisor_status=self.wakeword_supervisor.health().safe_projection(),
            telemetry=self._telemetry_summary(),
            telemetry_summary=self._telemetry_summary(),
        )

    def health(self) -> VoiceWorkerHealth:
        status = self.status()
        return VoiceWorkerHealth(
            lifecycle_state=status.lifecycle_state,
            process_started=status.process_started,
            heartbeat_ok=status.heartbeat is not None,
        )

    def version(self) -> VoiceWorkerVersionInfo:
        return VoiceWorkerVersionInfo(worker=self.config.worker_id)

    def start_wakeword_supervisor(self, *, explicit_user_triggered: bool = True) -> WakewordSupervisorHealth:
        self.asset_manager.discover_installed()
        self.wakeword_supervisor.update_config(self.config)
        return self.wakeword_supervisor.start(explicit_user_triggered=explicit_user_triggered)

    def stop_wakeword_supervisor(self, *, explicit_user_triggered: bool = True) -> WakewordSupervisorHealth:
        return self.wakeword_supervisor.stop(explicit_user_triggered=explicit_user_triggered)

    def tick_wakeword_supervisor(self) -> WakewordSupervisorTickResult:
        self.asset_manager.discover_installed()
        self.wakeword_supervisor.update_config(self.config)
        tick = self.wakeword_supervisor.tick()
        if tick.detected:
            self._error = None
            wake_trace = f"trace-wakeword-supervisor-{len(self._events) + 1}"
            self._record(
                VoiceWorkerEventType.WAKEWORD_DETECTED,
                trace_id=wake_trace,
                summary=tick.safe_projection(),
            )
            # Bridge: a successful wakeword detection should not just be
            # logged; it should hand off to STT so the rest of the
            # voice pipeline can run. The previous controller left this
            # link missing, so the supervisor would happily detect "Hey
            # Marvex" forever while STT counters stayed at zero.
            self._run_post_wake_capture(parent_trace_id=wake_trace)
        elif tick.exact_blocker and tick.exact_blocker not in {
            "wakeword_supervisor.backoff_active",
            "wakeword_supervisor.not_started",
            "wakeword.not_detected",
        }:
            self._error = VoiceWorkerErrorEnvelope.safe_error(
                trace_id=f"trace-wakeword-supervisor-{len(self._events) + 1}",
                reason_code=tick.exact_blocker,
                message="Wakeword supervisor tick failed.",
            )
            self._record(VoiceWorkerEventType.ERROR, trace_id=self._error.trace_id, summary=tick.safe_projection())
        return tick

    def _resolve_vad_decider(
        self,
        *,
        ambient_rms: float | None = None,
        stats: "dict[str, float] | None" = None,
    ) -> "Callable[[Any], bool]":
        """Return an is-speech decider for a single frame.

        Uses the configured VAD backend (silero primary, webrtc fallback). A
        custom decider can be injected for tests via ``self._vad_decider``.
        Moonshine STT has no internal padding/long-form chunking like Whisper -
        it expects a trimmed utterance - so VAD endpointing here is what makes
        moonshine-v2 transcribe correctly rather than choking on silence.

        ``ambient_rms`` (measured live by the wake loop) makes the RMS energy
        fallback adaptive instead of a hardcoded absolute, so low-gain mics work.
        ``stats`` (if given) is populated with the energy floor used and the
        per-path hit counts + max RMS observed, so post-wake diagnostics can show
        exactly why a capture did/didn't endpoint.
        """

        injected = getattr(self, "_vad_decider", None)
        if callable(injected):
            return injected
        backend = (self.config.vad.main_backend_id or "").strip()
        if backend == "webrtcvad-wheels":
            adapter: Any = WebRtcVadAdapter(aggressiveness=self.config.vad.aggressiveness)
        else:
            adapter = SileroVadAdapter()

        # Decide over a short SLIDING WINDOW, not a single 100ms frame: silero's
        # get_speech_timestamps has min_speech_duration_ms=250, so a lone 100ms
        # frame ALWAYS reads as silence (this is why post-wake capture returned
        # no_speech while the user was clearly speaking). webrtc likewise needs
        # exact 10/20/30ms frames. A ~500ms window satisfies both. RMS energy is
        # an OR fallback; the floor is derived from the live ambient RMS so it
        # tracks the mic (ambient ~490 / speech ~800 on a quiet mic) instead of a
        # magic 1200 that silently breaks low-gain inputs.
        window: deque[Any] = deque(maxlen=5)
        base_floor = float(getattr(self.config.vad, "speech_rms_floor", 0.0) or 700.0)
        energy_floor = _adaptive_energy_floor(ambient_rms, base_floor=base_floor)
        if stats is not None:
            stats["energy_floor"] = round(energy_floor, 1)
            stats["ambient_rms"] = round(float(ambient_rms or 0.0), 1)

        def decide(frame: Any) -> bool:
            window.append(frame)
            frames = tuple(window)
            rms = _frames_rms(frames)
            if stats is not None and rms > stats.get("max_window_rms", 0.0):
                stats["max_window_rms"] = round(rms, 1)
            try:
                if bool(adapter.decide(frames).is_speech):
                    if stats is not None:
                        stats["silero_hits"] = stats.get("silero_hits", 0.0) + 1
                    return True
            except Exception:
                pass
            if rms >= energy_floor:
                if stats is not None:
                    stats["energy_hits"] = stats.get("energy_hits", 0.0) + 1
                return True
            return False

        return decide

    def _default_frame_reader(self) -> "Callable[[], Any]":
        """Frame reader backed by the (chunked) audio adapter. Used by the
        legacy tick path and tests; the continuous wake loop passes its own
        gap-free reader instead."""

        cfg = self.config

        def read() -> Any:
            batch = tuple(
                self.audio.capture_frames(
                    device_id=cfg.audio.input_device_id,
                    sample_rate=cfg.audio.sample_rate,
                    channel_count=cfg.audio.channel_count,
                    frame_count=1,
                )
            )
            return batch[0] if batch else None

        return read

    def _capture_utterance(
        self,
        *,
        vad_decider: "Callable[[Any], bool]",
        read_frame: "Callable[[], Any] | None" = None,
    ) -> tuple[tuple[Any, ...], str]:
        """VAD-endpointed incremental capture of a single user utterance.

        Reads ~100ms frames one at a time from ``read_frame`` (the continuous
        mic stream when listening live, or the chunked adapter for the legacy
        path), starts accumulating on first speech (with a little pre-roll), and
        stops after ``silence_timeout_ms`` of trailing silence or at
        ``max_utterance_ms``. Returns the trimmed utterance frames + a reason.
        """

        cfg = self.config
        frame_ms = max(1, cfg.audio.frame_duration_ms)
        max_frames = max(1, cfg.vad.max_utterance_ms // frame_ms)
        silence_to_end = max(1, cfg.vad.silence_timeout_ms // frame_ms)
        pre_roll_keep = max(0, cfg.vad.tail_padding_ms // frame_ms)
        # Cap how long we wait for ANY speech before giving up (avoid hanging on
        # a wake-word false positive). ~2.5s of leading silence.
        max_leading_silence = max(silence_to_end, 25)
        reader = read_frame or self._default_frame_reader()

        pre_roll: deque = deque(maxlen=pre_roll_keep)
        captured: list[Any] = []
        speech_started = False
        trailing_silence = 0
        leading_silence = 0
        for _ in range(max_frames):
            frame = reader()
            if frame is None:
                break
            is_speech = vad_decider(frame)
            if not speech_started:
                if is_speech:
                    speech_started = True
                    captured.extend(pre_roll)
                    captured.append(frame)
                    trailing_silence = 0
                else:
                    pre_roll.append(frame)
                    leading_silence += 1
                    if leading_silence >= max_leading_silence:
                        return tuple(captured), "no_speech"
                continue
            captured.append(frame)
            if is_speech:
                trailing_silence = 0
            else:
                trailing_silence += 1
                if trailing_silence >= silence_to_end:
                    return tuple(captured), "silence_endpoint"
        if not speech_started:
            return tuple(captured), "no_speech"
        return tuple(captured), "max_utterance"

    def _run_post_wake_capture(
        self,
        *,
        parent_trace_id: str,
        read_frame: "Callable[[], Any] | None" = None,
        on_diagnostic: "Callable[[dict[str, object]], None] | None" = None,
        ambient_rms: float | None = None,
    ) -> None:
        """VAD-endpoint a user utterance after wake and run STT on it.

        Emits VAD_SPEECH_STARTED / VAD_SPEECH_ENDED / TRANSCRIPTION_STARTED /
        TRANSCRIPTION_COMPLETED with the transcript text in the completed
        event's summary so a downstream consumer (shell) can submit a chat
        turn. ``read_frame`` lets the continuous wake loop reuse the same
        gap-free mic stream; the legacy path uses the chunked adapter.
        ``on_diagnostic`` surfaces the post-wake stages to the worker stderr so
        "nothing happens after the wake word" is diagnosable (did we capture a
        command? did STT run? did it produce text?). Failures are swallowed; the
        wake event was already recorded.
        """

        def _diag(payload: dict[str, object]) -> None:
            if on_diagnostic is not None:
                try:
                    on_diagnostic(payload)
                except Exception:
                    pass

        try:
            _diag({"event": "post_wake_capture", "stage": "listening", "ambient_rms": round(float(ambient_rms or 0.0), 1)})
            vad_stats: dict[str, float] = {}
            vad_decider = self._resolve_vad_decider(ambient_rms=ambient_rms, stats=vad_stats)
            frames, reason = self._capture_utterance(vad_decider=vad_decider, read_frame=read_frame)
            # Decisive endpoint diagnostic: the captured frame count, the reason,
            # the energy floor used, the max RMS the VAD actually saw, and which
            # path (silero vs energy) carried detection. With this, a no_speech on
            # a clearly-spoken utterance tells us exactly where the gate failed.
            _diag({"event": "post_wake_capture", "stage": "endpoint", "reason": reason, "frame_count": len(frames), **vad_stats})
            if not frames or reason == "no_speech":
                self._record(
                    VoiceWorkerEventType.VAD_SPEECH_ENDED,
                    trace_id=parent_trace_id,
                    summary={"reason_code": "no_speech", "post_wake_capture": True},
                )
                return
            self._record(
                VoiceWorkerEventType.VAD_SPEECH_STARTED,
                trace_id=parent_trace_id,
                summary={"trigger": "post_wake_capture", "frame_count": len(frames)},
            )
            audio_ref_id = self.backend_runtime.remember_captured_frames(
                trace_id=parent_trace_id,
                frames=frames,
            )
            self._record(
                VoiceWorkerEventType.VAD_SPEECH_ENDED,
                trace_id=parent_trace_id,
                summary={
                    "reason_code": reason,
                    "duration_ms": sum(frame.duration_ms for frame in frames),
                    "audio_ref_present": True,
                },
            )
            self._record(
                VoiceWorkerEventType.TRANSCRIPTION_STARTED,
                trace_id=parent_trace_id,
                summary={"backend_id": self.config.active_stt_backend_id},
            )
            transcription = self.backend_runtime.test_stt(
                trace_id=parent_trace_id,
                backend_id=self.config.active_stt_backend_id,
                audio_ref_id=audio_ref_id,
            )
            summary = {
                **transcription_summary(transcription),
                "audio_ref_present": True,
                "post_wake_capture": True,
                "endpoint_reason": reason,
            }
            if transcription.status == "succeeded" and transcription.text:
                summary["transcript_text"] = transcription.text
            self._record(
                VoiceWorkerEventType.TRANSCRIPTION_COMPLETED,
                trace_id=parent_trace_id,
                summary=summary,
            )
            _diag(
                {
                    "event": "post_wake_stt",
                    "status": str(transcription.status),
                    "backend": self.config.active_stt_backend_id,
                    "text_present": bool(transcription.status == "succeeded" and transcription.text),
                    "text_len": len(transcription.text or ""),
                }
            )
        except Exception as exc:
            # Defensive: any failure here is logged but must not crash
            # the supervisor tick loop.
            _diag({"event": "post_wake_capture", "stage": "error", "reason": type(exc).__name__})
            self._record(
                VoiceWorkerEventType.ERROR,
                trace_id=parent_trace_id,
                summary={"post_wake_capture": True, "reason_code": "post_wake_capture_failed"},
            )

    def run_wake_listen_loop(
        self,
        *,
        capture: Any,
        should_stop: "Callable[[], bool]",
        frames_per_decode: int = 3,
        idle_timeout: float = 0.5,
        lock: Any | None = None,
        on_diagnostic: "Callable[[dict[str, object]], None] | None" = None,
        diagnostic_interval_decodes: int = 50,
        debug_dump_path: str | None = None,
        debug_dump_seconds: float = 6.0,
    ) -> dict[str, object]:
        """Continuous wake-word + command loop over a gap-free mic stream.

        This is the root fix for "Hey Marvex never triggers": the streaming
        zipformer needs CONTIGUOUS audio. Instead of reopening the device every
        tick and feeding disjoint windows, we open one persistent stream and
        feed its back-to-back frames to the KWS. On detection we capture the
        command utterance from the SAME stream (VAD-endpointed) and emit its
        transcript, then resume listening. Runs until ``should_stop`` returns
        True. Does not hold any command lock while reading audio.

        ``on_diagnostic`` (injected by the worker, which owns stderr) makes the
        loop observable in the field: without it, non-detections are silent and
        "wake word never triggers" is undiagnosable. We emit a start event, a
        periodic heartbeat (frames read, decode count, last KWS confidence and
        reason_code, detection count) and surface swallowed KWS runtime errors
        immediately. The KWS confidence in the heartbeat is the single most
        useful signal: if speaking "Hey Marvex" shows confidence climbing but
        below threshold, lower the threshold; if it stays ~0 or audio never
        flows, the problem is the mic/stream, not the threshold.
        """

        def _emit(payload: dict[str, object]) -> None:
            if on_diagnostic is not None:
                try:
                    on_diagnostic(payload)
                except Exception:
                    pass

        self.asset_manager.discover_installed()
        self.wakeword_supervisor.update_config(self.config)
        if not self.config.wakeword.enabled:
            _emit({"event": "wake_listen_refused", "reason_code": "wakeword_not_enabled"})
            return {"started": False, "reason_code": "wakeword_not_enabled"}
        if not self.wakeword_supervisor._asset_ready():  # noqa: SLF001 - readiness gate
            _emit({"event": "wake_listen_refused", "reason_code": "wakeword_model_not_installed"})
            return {"started": False, "reason_code": "wakeword_model_not_installed"}

        from contextlib import nullcontext

        def _locked():
            return lock if lock is not None else nullcontext()

        detections = 0
        frames_read = 0
        decode_count = 0
        last_confidence = 0.0
        last_reason_code: str | None = None
        last_rms = 0.0
        max_rms_window = 0.0
        # Live ambient-noise estimate (EMA of quiet decodes), used to make the
        # post-wake VAD energy floor + the batch-probe gate adaptive to the mic.
        ambient_ema = 0.0
        # Rolling buffer of recent frames (~6s) for the batch self-probe below.
        recent_frames: deque[Any] = deque(maxlen=max(2 * max(1, frames_per_decode), 60))
        probes_done = 0
        # Opt-in raw-audio capture for triage (MARVEX_VOICE_DEBUG_DUMP). Writes a
        # bounded WAV of exactly what the KWS is being fed, so we can replay it
        # offline and tell "real audio doesn't decode" from "live feed problem".
        dump_buffer: list[bytes] = []
        dump_samples_target = int(self.config.audio.sample_rate * max(0.0, debug_dump_seconds))
        dump_samples_have = 0
        dumped = debug_dump_path is None
        self._continuous_active = True
        capture.start()
        _emit(
            {
                "event": "wake_listen_started",
                "phrase": self.config.wakeword.phrase,
                "threshold": self.config.wakeword.threshold,
                "frames_per_decode": frames_per_decode,
            }
        )
        reader = lambda: capture.read(timeout=idle_timeout)  # noqa: E731
        try:
            batch: list[Any] = []
            while not should_stop():
                # Audio read is lock-free so JSONL commands (status/speak/
                # listen) are never starved while we listen.
                frame = capture.read(timeout=idle_timeout)
                if frame is None:
                    continue
                frames_read += 1
                if not dumped:
                    pcm = getattr(frame, "pcm", b"") or b""
                    dump_buffer.append(pcm)
                    dump_samples_have += len(pcm) // 2
                    if dump_samples_have >= dump_samples_target:
                        info = _write_debug_wav(
                            debug_dump_path,
                            dump_buffer,
                            sample_rate=self.config.audio.sample_rate,
                        )
                        _emit({"event": "wake_listen_debug_dump", **info})
                        dumped = True
                        dump_buffer = []
                batch.append(frame)
                if len(batch) < max(1, frames_per_decode):
                    continue
                frames = tuple(batch)
                batch = []
                # Audio level (int16 RMS) over this decode window. This is the
                # signal that distinguishes "mic delivers silence" (wrong/muted
                # default device -> RMS stays ~0 even while speaking, so the KWS
                # can never fire) from "audio is fine but the keyword model is
                # not matching" (RMS healthy, confidence still 0).
                last_rms = _frames_rms(frames)
                max_rms_window = max(max_rms_window, last_rms)
                # Track ambient as a slow EMA, but only fold in quiet decodes so
                # speech spikes don't inflate the noise floor. Seed on first read.
                if ambient_ema <= 0.0:
                    ambient_ema = last_rms
                elif last_rms < ambient_ema * 1.5:
                    ambient_ema = 0.9 * ambient_ema + 0.1 * last_rms
                recent_frames.extend(frames)
                # Detection + command capture mutate worker state + the KWS
                # session, so take the lock only around that brief work.
                with _locked():
                    detection = self.backend_runtime.test_wakeword(
                        trace_id=f"wake-listen-{self._tick_counter_advance()}",
                        backend_id=self.config.wakeword.backend_id,
                        frames=frames,
                        phrase=self.config.wakeword.phrase,
                        threshold=self.config.wakeword.threshold,
                    )
                    decode_count += 1
                    last_confidence = float(getattr(detection, "confidence", 0.0) or 0.0)
                    last_reason_code = getattr(detection, "reason_code", None)
                    if decode_count == 1:
                        # Surface what keyword tokens the spotter actually loaded
                        # (audio is proven good via RMS, so a never-firing wake
                        # word points at the keyword config).
                        runner = getattr(self.backend_runtime, "_wakeword_runner", None)
                        diag = getattr(runner, "keyword_diagnostic", None)
                        if isinstance(diag, dict):
                            _emit({"event": "wake_listen_keyword_config", **diag})
                    # Surface a real backend runtime error the moment it
                    # happens (it would otherwise be invisible: non-detections
                    # are not recorded as events).
                    if last_reason_code and "runtime_error" in last_reason_code:
                        _emit({"event": "wake_listen_kws_error", "reason_code": last_reason_code})
                    if detection.detected:
                        self._error = None
                        detections += 1
                        _emit(
                            {
                                "event": "wake_listen_detected",
                                "confidence": last_confidence,
                                "detections": detections,
                            }
                        )
                        wake_trace = f"trace-wake-listen-{len(self._events) + 1}"
                        self._record(
                            VoiceWorkerEventType.WAKEWORD_DETECTED,
                            trace_id=wake_trace,
                            summary=detection.safe_projection(),
                        )
                        # Capture the command from the SAME continuous stream.
                        self._run_post_wake_capture(
                            parent_trace_id=wake_trace, read_frame=reader, on_diagnostic=on_diagnostic, ambient_rms=ambient_ema
                        )
                        batch = []
                    elif decode_count % max(1, diagnostic_interval_decodes) == 0:
                        _emit(
                            {
                                "event": "wake_listen_heartbeat",
                                "frames_read": frames_read,
                                "decodes": decode_count,
                                "detections": detections,
                                "last_confidence": last_confidence,
                                "last_reason_code": last_reason_code,
                                "audio_rms": round(last_rms, 1),
                                "audio_rms_peak": round(max_rms_window, 1),
                            }
                        )
                        # Decisive self-diagnostic: when speech is clearly present
                        # (loud window) but the LIVE persistent stream has detected
                        # nothing, replay the buffered audio through a FRESH stream.
                        # detected-here-but-not-live => the persistent-stream feed
                        # is the bug; not-detected-either => audio content/format.
                        probe = getattr(self.backend_runtime, "probe_wakeword", None)
                        # Adaptive probe gate: fire the recovery probe when this
                        # decode window rose meaningfully above the live ambient
                        # floor, instead of a hardcoded 800 that a low-gain mic
                        # (ambient ~490 / peak ~550) never reaches.
                        probe_gate = max(450.0, ambient_ema * 1.4)
                        if (
                            callable(probe)
                            and detections == 0
                            and max_rms_window >= probe_gate
                            and probes_done < 5
                            and len(recent_frames) >= max(1, frames_per_decode)
                        ):
                            probes_done += 1
                            try:
                                hit, keyword = probe(
                                    backend_id=self.config.wakeword.backend_id,
                                    frames=tuple(recent_frames),
                                    phrase=self.config.wakeword.phrase,
                                    threshold=self.config.wakeword.threshold,
                                )
                            except Exception:
                                hit, keyword = False, ""
                            _emit(
                                {
                                    "event": "wake_listen_batch_probe",
                                    "detected": bool(hit),
                                    "keyword": keyword,
                                    "buffered_frames": len(recent_frames),
                                    "audio_rms_peak": round(max_rms_window, 1),
                                }
                            )
                            # Second chance: the fresh-stream probe catches wakes
                            # the long-lived persistent stream misses (its decoder
                            # state drifts over a long session). Treat a probe hit
                            # as a real wake and capture the command.
                            if hit:
                                self._error = None
                                detections += 1
                                wake_trace = f"trace-wake-listen-{len(self._events) + 1}"
                                self._record(
                                    VoiceWorkerEventType.WAKEWORD_DETECTED,
                                    trace_id=wake_trace,
                                    summary={"via": "batch_probe", "keyword": keyword, "phrase": self.config.wakeword.phrase},
                                )
                                _emit({"event": "wake_listen_detected", "via": "batch_probe", "detections": detections})
                                self._run_post_wake_capture(
                                    parent_trace_id=wake_trace, read_frame=reader, on_diagnostic=on_diagnostic, ambient_rms=ambient_ema
                                )
                                batch = []
                        max_rms_window = 0.0
        finally:
            self._continuous_active = False
            capture.stop()
            _emit(
                {
                    "event": "wake_listen_stopped",
                    "frames_read": frames_read,
                    "decodes": decode_count,
                    "detections": detections,
                    "last_confidence": last_confidence,
                    "last_reason_code": last_reason_code,
                    "audio_rms": round(last_rms, 1),
                }
            )
        return {"started": True, "detections": detections, "stopped": True}

    def _tick_counter_advance(self) -> int:
        # Reuse the supervisor's counter for unique trace ids in the loop.
        self.wakeword_supervisor._tick_counter += 1  # noqa: SLF001
        return self.wakeword_supervisor._tick_counter  # noqa: SLF001

    def wakeword_supervisor_health(self) -> WakewordSupervisorHealth:
        self.asset_manager.discover_installed()
        return self.wakeword_supervisor.health()

    def clean_shutdown_wakeword_supervisor(self) -> WakewordSupervisorHealth:
        return self.wakeword_supervisor.clean_shutdown()

    def handle(self, command: VoiceWorkerCommand) -> VoiceWorkerCommandResult:
        handler = getattr(self, f"_handle_{command.command}")
        event = handler(command)
        return VoiceWorkerCommandResult(
            command_id=command.command_id,
            trace_id=self._trace_id_for(command),
            status=self.status(),
            event=event,
            error=self._error,
        )

    def _trace_id_for(self, command: VoiceWorkerCommand) -> str:
        return command.trace_id or command.command_id

    def run_manual_turn(self, *, trace_id: str, assistant_turn_runner: Callable[[str], Any], policy_decider: Callable[[str], Any]) -> VoiceWorkerTurnRunResult:
        frames = tuple(self.audio.capture_frames(device_id=self.config.audio.input_device_id, sample_rate=self.config.audio.sample_rate, channel_count=self.config.audio.channel_count, frame_count=4))
        ring = AudioRingBuffer(max_frames=4, pre_roll_ms=sum(frame.duration_ms for frame in frames))
        aggregator = ChunkAggregator(max_utterance_ms=self.config.vad.max_utterance_ms, silence_cutoff_ms=self.config.vad.silence_timeout_ms, tail_padding_ms=self.config.vad.tail_padding_ms)
        for frame in frames:
            ring.append(frame)
            aggregator.accept(frame, VADDecision.speech_started(frame_count=1, confidence=0.8, noise_floor_db=-45))
        events = (
            self._record(VoiceWorkerEventType.VAD_SPEECH_STARTED, trace_id=trace_id, summary={"frame_count": len(frames)}),
            self._record(VoiceWorkerEventType.VAD_SPEECH_ENDED, trace_id=trace_id, summary={"duration_ms": sum(frame.duration_ms for frame in frames)}),
            self._record(VoiceWorkerEventType.TRANSCRIPTION_STARTED, trace_id=trace_id),
        )
        turn = self.voice_runtime.run_voice_turn(VoiceTurnRequest.manual(trace_id=trace_id, audio_ref_id=f"memory://voice/captured/{trace_id}"), assistant_turn_runner=assistant_turn_runner, policy_decider=policy_decider)
        partials = PartialTranscriptBuffer(max_items=4)
        if turn.transcription.text:
            partials.add(turn.transcription.text)
        early_speech = select_early_speech(EarlySpeechTrigger(intent_kind="web_search", elapsed_ms=900), policy=self.voice_runtime.config.early_speech)
        more_events = (
            self._record(VoiceWorkerEventType.TRANSCRIPTION_COMPLETED, trace_id=trace_id, summary={"backend_id": turn.transcription.backend_id, "text_present": bool(turn.transcription.text)}),
            self._record(VoiceWorkerEventType.ASSISTANT_TURN_STARTED, trace_id=trace_id, summary={"policy_decision": turn.policy_decision.decision}),
            self._record(VoiceWorkerEventType.TTS_STARTED, trace_id=trace_id, summary={"backend_id": turn.speech.backend_id if turn.speech else "none"}),
            self._record(VoiceWorkerEventType.PLAYBACK_STARTED, trace_id=trace_id),
        )
        if turn.speech and turn.speech.audio_ref:
            self.audio.play_audio(device_id=self.config.audio.output_device_id, audio_ref=turn.speech.audio_ref, sample_rate=turn.speech.sample_rate)
        playback = self.audio.stop_playback()
        self._playback_status = "completed"
        final = self._record(VoiceWorkerEventType.PLAYBACK_FINISHED, trace_id=trace_id)
        turn.playback = VoicePlaybackResult(trace_id=trace_id, status="completed", audio_ref=turn.playback.audio_ref, backend_id=turn.playback.backend_id)  # type: ignore[misc]
        capture_summary = {
            "pre_roll_ms": ring.pre_roll_ms,
            "tail_padding_ms": self.config.vad.tail_padding_ms,
            "max_utterance_ms": self.config.vad.max_utterance_ms,
            "partial_transcript_count": partials.safe_projection()["partial_count"],
            "final_transcript_event": turn.transcription.status == "succeeded" and bool(turn.transcription.text),
            "early_speech": early_speech.model_dump(mode="json"),
        }
        return VoiceWorkerTurnRunResult(turn=turn, events=events + more_events + (final,), playback=playback.model_copy(update={"status": "completed"}), capture_summary=capture_summary)

    def run_live_capture_cycle(
        self,
        *,
        trace_id: str,
        trigger: str,
        max_frame_count: int,
        vad_decider: Callable[[Any, int], VADDecision],
        assistant_turn_runner: Callable[[str], Any],
        policy_decider: Callable[[str], Any],
    ) -> VoiceWorkerTurnRunResult:
        frames = tuple(
            self.audio.capture_frames(
                device_id=self.config.audio.input_device_id,
                sample_rate=self.config.audio.sample_rate,
                channel_count=self.config.audio.channel_count,
                frame_count=max_frame_count,
            )
        )
        pre_roll_frames: list[Any] = []
        speech_frame_count = 0
        captured_frame_count = 0
        speech_started = False
        finalized_reason = "chunk.not_finalized"
        aggregator = ChunkAggregator(max_utterance_ms=self.config.vad.max_utterance_ms, silence_cutoff_ms=self.config.vad.silence_timeout_ms, tail_padding_ms=self.config.vad.tail_padding_ms)
        ring = AudioRingBuffer(max_frames=max(1, max_frame_count), pre_roll_ms=0)
        events: list[VoiceWorkerEvent] = []

        for index, frame in enumerate(frames[:max_frame_count]):
            captured_frame_count += 1
            vad = vad_decider(frame, index)
            ring.append(frame)
            if not speech_started and not vad.is_speech:
                pre_roll_frames.append(frame)
                pre_roll_frames = pre_roll_frames[-2:]
                continue
            if not speech_started and vad.is_speech:
                speech_started = True
                ring = AudioRingBuffer(max_frames=max(1, len(pre_roll_frames) + max_frame_count), pre_roll_ms=sum(item.duration_ms for item in pre_roll_frames))
                for pre_roll_frame in pre_roll_frames:
                    ring.append(pre_roll_frame)
                events.append(self._record(VoiceWorkerEventType.VAD_SPEECH_STARTED, trace_id=trace_id, summary={"pre_roll_ms": ring.pre_roll_ms}))
            if speech_started:
                ring.append(frame)
                if vad.is_speech:
                    speech_frame_count += 1
                state = aggregator.accept(frame, vad)
                if state.finalized:
                    finalized_reason = state.reason_code
                    break

        capture_summary: dict[str, object] = {
            "trigger": trigger,
            "captured_frame_count": captured_frame_count,
            "speech_frame_count": speech_frame_count,
            "pre_roll_ms": ring.pre_roll_ms,
            "tail_padding_ms": self.config.vad.tail_padding_ms,
            "max_utterance_ms": self.config.vad.max_utterance_ms,
            "segment_finalized_reason": finalized_reason,
            "prevents_runaway_recording": True,
            "assistant_dispatch_started": False,
        }
        playback = PlaybackAdapterResult(status="stopped", reason_code="live_capture.not_dispatched")
        if not speech_started or finalized_reason == "chunk.finalized.max_utterance_duration":
            if speech_started:
                events.append(self._record(VoiceWorkerEventType.VAD_SPEECH_ENDED, trace_id=trace_id, summary={"reason_code": finalized_reason, "duration_ms": sum(frame.duration_ms for frame in ring.frames)}))
            return VoiceWorkerTurnRunResult(turn=None, events=tuple(events), playback=playback, capture_summary=capture_summary)

        events.append(self._record(VoiceWorkerEventType.VAD_SPEECH_ENDED, trace_id=trace_id, summary={"reason_code": finalized_reason, "duration_ms": sum(frame.duration_ms for frame in ring.frames)}))
        events.append(self._record(VoiceWorkerEventType.TRANSCRIPTION_STARTED, trace_id=trace_id))
        turn = self.voice_runtime.run_voice_turn(
            VoiceTurnRequest.manual(trace_id=trace_id, audio_ref_id=f"memory://voice/captured/{trace_id}"),
            assistant_turn_runner=assistant_turn_runner,
            policy_decider=policy_decider,
        )
        partials = PartialTranscriptBuffer(max_items=4)
        if turn.transcription.text:
            partials.add(turn.transcription.text)
        capture_summary.update({"partial_transcript_count": partials.safe_projection()["partial_count"], "final_transcript_event": turn.transcription.status == "succeeded" and bool(turn.transcription.text), "assistant_dispatch_started": True})
        events.extend(
            (
                self._record(VoiceWorkerEventType.TRANSCRIPTION_COMPLETED, trace_id=trace_id, summary={"backend_id": turn.transcription.backend_id, "text_present": bool(turn.transcription.text)}),
                self._record(VoiceWorkerEventType.ASSISTANT_TURN_STARTED, trace_id=trace_id, summary={"policy_decision": turn.policy_decision.decision}),
                self._record(VoiceWorkerEventType.TTS_STARTED, trace_id=trace_id, summary={"backend_id": turn.speech.backend_id if turn.speech else "none"}),
                self._record(VoiceWorkerEventType.PLAYBACK_STARTED, trace_id=trace_id),
            )
        )
        if turn.speech and turn.speech.audio_ref:
            self.audio.play_audio(device_id=self.config.audio.output_device_id, audio_ref=turn.speech.audio_ref, sample_rate=turn.speech.sample_rate)
        playback = self.audio.stop_playback().model_copy(update={"status": "completed"})
        self._playback_status = "completed"
        final = self._record(VoiceWorkerEventType.PLAYBACK_FINISHED, trace_id=trace_id)
        turn.playback = VoicePlaybackResult(trace_id=trace_id, status="completed", audio_ref=turn.playback.audio_ref, backend_id=turn.playback.backend_id)  # type: ignore[misc]
        return VoiceWorkerTurnRunResult(turn=turn, events=tuple(events) + (final,), playback=playback, capture_summary=capture_summary)

    def _handle_health(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        return self._record(
            VoiceWorkerEventType.HEALTH_REPORTED,
            trace_id=self._trace_id_for(command),
            summary={"health": self.health().model_dump(mode="json")},
        )

    def _handle_version(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        return self._record(
            VoiceWorkerEventType.VERSION_REPORTED,
            trace_id=self._trace_id_for(command),
            summary={"version": self.version().safe_projection()},
        )

    def _handle_start(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        self._state = VoiceWorkerLifecycleState.RUNNING
        self._heartbeat = VoiceWorkerHeartbeat.now(lifecycle_state=self._state)
        summary: dict[str, Any] = {"explicit_user_triggered": True}
        if self.config.wakeword.enabled:
            wakeword_health = self.start_wakeword_supervisor(explicit_user_triggered=True)
            summary["wakeword_supervisor"] = wakeword_health.safe_projection()
        return self._record(VoiceWorkerEventType.MIC_STARTED, trace_id=self._trace_id_for(command), summary=summary)

    def _handle_stop(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        self.audio.stop_playback()
        self._state = VoiceWorkerLifecycleState.STOPPED
        self._playback_status = "stopped"
        self._queued_tts_count = 0
        # Clean shutdown of the wakeword supervisor on explicit worker stop so
        # the supervisor loop never outlives an explicit user worker stop.
        self.wakeword_supervisor.clean_shutdown()
        return self._record(VoiceWorkerEventType.MIC_STOPPED, trace_id=self._trace_id_for(command))

    def _handle_pause(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        self._state = VoiceWorkerLifecycleState.PAUSED
        self._heartbeat = VoiceWorkerHeartbeat.now(lifecycle_state=self._state)
        return self._record(VoiceWorkerEventType.MIC_STOPPED, trace_id=self._trace_id_for(command), summary={"paused": True})

    def _handle_resume(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        self._state = VoiceWorkerLifecycleState.RUNNING
        self._heartbeat = VoiceWorkerHeartbeat.now(lifecycle_state=self._state)
        return self._record(VoiceWorkerEventType.MIC_STARTED, trace_id=self._trace_id_for(command), summary={"resumed": True})

    def _handle_reload_config(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        wakeword = self.config.wakeword.model_copy(update={
            "enabled": bool(command.payload.get("wakeword_enabled", self.config.wakeword.enabled)),
            "threshold": float(command.payload.get("wakeword_threshold", self.config.wakeword.threshold)),
        })
        audio_updates = {
            key: command.payload[key]
            for key in ("input_device_id", "output_device_id", "sample_rate", "channel_count", "frame_duration_ms")
            if key in command.payload
        }
        audio = self.config.audio.model_copy(update=audio_updates)
        self.config = self.config.model_copy(update={"wakeword": wakeword, "audio": audio})
        # Keep the wakeword supervisor in sync with the new config so its asset
        # readiness, phrase, and threshold checks remain correct.
        self.wakeword_supervisor.update_config(self.config)
        return self._record(
            VoiceWorkerEventType.MIC_STARTED,
            trace_id=self._trace_id_for(command),
            summary={"config_reloaded": True, "audio_config_reloaded": bool(audio_updates)},
        )

    def _handle_test_mic(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        level = self.audio.test_mic_level(device_id=command.payload.get("device_id") or self.config.audio.input_device_id, duration_ms=250)
        return self._record(VoiceWorkerEventType.MIC_STARTED, trace_id=self._trace_id_for(command), summary=level.model_dump(mode="json"))

    def _handle_test_playback(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        playback = self.audio.play_audio(device_id=command.payload.get("device_id") or self.config.audio.output_device_id, audio_ref="memory://voice/test/playback", sample_rate=24_000)
        if command.payload.get("simulate_barge_in"):
            playback = self.audio.interrupt_playback(reason_code="barge_in.user_speech_detected")
            self._playback_status = "interrupted"
            self._queued_tts_count = 0
            return self._record(VoiceWorkerEventType.BARGE_IN_DETECTED, trace_id=self._trace_id_for(command), summary=playback.model_dump(mode="json"))
        self._playback_status = "completed"
        return self._record(VoiceWorkerEventType.PLAYBACK_FINISHED, trace_id=self._trace_id_for(command), summary=playback.model_dump(mode="json"))

    def _handle_test_wakeword(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        trace_id = self._trace_id_for(command)
        self.asset_manager.discover_installed()
        if not self.config.wakeword.enabled:
            self._error = VoiceWorkerErrorEnvelope.safe_error(trace_id=trace_id, reason_code="wakeword_not_enabled", message="Wakeword is disabled.")
            return self._record(VoiceWorkerEventType.ERROR, trace_id=trace_id, summary={"wakeword_ready": False})
        if not self.asset_manager.is_ready(model_id="hey-marvex", backend_id=self.config.wakeword.backend_id, model_kind="wakeword"):
            self._error = VoiceWorkerErrorEnvelope.safe_error(trace_id=trace_id, reason_code="wakeword_model_not_installed", message="Hey Marvex wakeword model asset is not installed under the voice asset root.")
            return self._record(VoiceWorkerEventType.ERROR, trace_id=trace_id, summary={"wakeword_ready": False, "exact_blocker": "wakeword_model_not_installed"})
        frames = tuple(
            self.audio.capture_frames(
                device_id=self.config.audio.input_device_id,
                sample_rate=self.config.audio.sample_rate,
                channel_count=self.config.audio.channel_count,
                frame_count=4,
            )
        )
        detection = self.backend_runtime.test_wakeword(
            trace_id=trace_id,
            backend_id=self.config.wakeword.backend_id,
            frames=frames,
            phrase=self.config.wakeword.phrase,
            threshold=self.config.wakeword.threshold,
        )
        if not detection.detected:
            self._error = VoiceWorkerErrorEnvelope.safe_error(trace_id=trace_id, reason_code=detection.reason_code, message="Hey Marvex wakeword was not detected by the configured runtime.")
            return self._record(VoiceWorkerEventType.ERROR, trace_id=trace_id, summary={**detection.safe_projection(), "wakeword_ready": True})
        self._error = None
        return self._record(VoiceWorkerEventType.WAKEWORD_DETECTED, trace_id=trace_id, summary={**detection.safe_projection(), "wakeword_ready": True})

    def _handle_test_stt(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        trace_id = self._trace_id_for(command)
        audio_ref_id = command.payload.get("audio_ref_id")
        if audio_ref_id is None:
            frames = tuple(
                self.audio.capture_frames(
                    device_id=self.config.audio.input_device_id,
                    sample_rate=self.config.audio.sample_rate,
                    channel_count=self.config.audio.channel_count,
                    frame_count=4,
                )
            )
            audio_ref_id = self.backend_runtime.remember_captured_frames(trace_id=trace_id, frames=frames)
        result = self.backend_runtime.test_stt(
            trace_id=trace_id,
            backend_id=str(command.payload.get("backend_id") or self.config.active_stt_backend_id),
            audio_ref_id=str(audio_ref_id),
        )
        if result.status == "failed" and result.safe_error is not None:
            reason = result.safe_error.details.get("reason_code", "stt_backend_not_ready")
            self._error = VoiceWorkerErrorEnvelope.safe_error(trace_id=trace_id, reason_code=reason, message="STT backend test did not complete.")
        else:
            self._error = None
        return self._record(VoiceWorkerEventType.TRANSCRIPTION_COMPLETED, trace_id=trace_id, summary={**transcription_summary(result), "audio_ref_present": True})

    def _handle_test_tts(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        trace_id = self._trace_id_for(command)
        result = self.backend_runtime.test_tts(
            trace_id=trace_id,
            backend_id=str(command.payload.get("backend_id") or self.config.active_tts_backend_id),
            voice_id=str(command.payload.get("voice_id") or self.config.active_voice_id),
            text=str(command.payload.get("text") or "Voice test."),
        )
        if result.status == "failed" and result.safe_error is not None:
            reason = result.safe_error.details.get("reason_code", "tts_backend_not_ready")
            self._error = VoiceWorkerErrorEnvelope.safe_error(trace_id=trace_id, reason_code=reason, message="TTS backend test did not complete.")
        else:
            self._error = None
        event = self._record(VoiceWorkerEventType.TTS_STARTED, trace_id=trace_id, summary=synthesis_summary(result))
        if result.status == "succeeded" and result.audio_ref:
            self._record(VoiceWorkerEventType.PLAYBACK_STARTED, trace_id=trace_id, summary={"audio_ref_present": True})
            playback = self.audio.play_audio(
                device_id=self.config.audio.output_device_id,
                audio_ref=result.audio_ref,
                sample_rate=result.sample_rate,
            )
            self._playback_status = playback.status
            self._record(VoiceWorkerEventType.PLAYBACK_FINISHED, trace_id=trace_id, summary=playback.model_dump(mode="json"))
        return event

    def _handle_speak(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        """Synthesize and play an assistant reply (docs/TODO/04).

        Closes the voice loop: the shell submits the recognized transcript as a
        chat turn, then sends the reply text here to be spoken. Synthesizes via
        the active TTS backend and plays through the audio adapter. No raw
        generated audio is persisted.
        """

        trace_id = self._trace_id_for(command)
        text = str(command.payload.get("text") or "").strip()
        if not text:
            self._error = VoiceWorkerErrorEnvelope.safe_error(trace_id=trace_id, reason_code="speak_text_required", message="Speak requires non-empty text.")
            return self._record(VoiceWorkerEventType.ERROR, trace_id=trace_id, summary={"reason_code": "speak_text_required"})
        result = self.backend_runtime.test_tts(
            trace_id=trace_id,
            backend_id=str(command.payload.get("backend_id") or self.config.active_tts_backend_id),
            voice_id=str(command.payload.get("voice_id") or self.config.active_voice_id),
            text=text,
        )
        if result.status == "failed" and result.safe_error is not None:
            reason = result.safe_error.details.get("reason_code", "tts_backend_not_ready")
            self._error = VoiceWorkerErrorEnvelope.safe_error(trace_id=trace_id, reason_code=reason, message="Speak synthesis did not complete.")
            return self._record(VoiceWorkerEventType.ERROR, trace_id=trace_id, summary={"reason_code": reason, "speak": True})
        self._error = None
        event = self._record(VoiceWorkerEventType.TTS_STARTED, trace_id=trace_id, summary={**synthesis_summary(result), "speak": True})
        if result.status == "succeeded" and result.audio_ref:
            # Barge-in monitors the mic; skip it while the continuous wake loop
            # owns the input device (the loop's own listening covers barge-in
            # at the architecture level once unified). Play to completion then.
            if bool(command.payload.get("barge_in")) and not self._continuous_active:
                self._speak_with_barge_in(trace_id=trace_id, audio_ref=result.audio_ref, sample_rate=result.sample_rate)
            else:
                self._record(VoiceWorkerEventType.PLAYBACK_STARTED, trace_id=trace_id, summary={"audio_ref_present": True, "speak": True})
                playback = self.audio.play_audio(
                    device_id=self.config.audio.output_device_id,
                    audio_ref=result.audio_ref,
                    sample_rate=result.sample_rate,
                )
                self._playback_status = playback.status
                self._record(VoiceWorkerEventType.PLAYBACK_FINISHED, trace_id=trace_id, summary={**playback.model_dump(mode="json"), "speak": True})
        return event

    def _speak_with_barge_in(self, *, trace_id: str, audio_ref: str, sample_rate: int) -> None:
        """Play a reply non-blocking while monitoring the mic; interrupt on speech.

        Starts playback without blocking, then polls ~100ms mic frames through
        the VAD decider. If the user starts talking, playback is interrupted
        (BARGE_IN_DETECTED) so they can take over the conversation. If no
        barge-in occurs, playback runs to completion. NOTE: real deployments
        need acoustic echo cancellation so the assistant's own audio doesn't
        self-trigger; that's a hardware/driver concern outside this loop.
        """

        begin = getattr(self.audio, "begin_playback", None)
        active = getattr(self.audio, "playback_active", None)
        if not callable(begin) or not callable(active):
            # Adapter doesn't support non-blocking playback; fall back to blocking.
            self._record(VoiceWorkerEventType.PLAYBACK_STARTED, trace_id=trace_id, summary={"audio_ref_present": True, "speak": True, "barge_in": False})
            playback = self.audio.play_audio(device_id=self.config.audio.output_device_id, audio_ref=audio_ref, sample_rate=sample_rate)
            self._playback_status = playback.status
            self._record(VoiceWorkerEventType.PLAYBACK_FINISHED, trace_id=trace_id, summary={**playback.model_dump(mode="json"), "speak": True})
            return

        self._record(VoiceWorkerEventType.PLAYBACK_STARTED, trace_id=trace_id, summary={"audio_ref_present": True, "speak": True, "barge_in": True})
        begin(device_id=self.config.audio.output_device_id, audio_ref=audio_ref, sample_rate=sample_rate)
        self._playback_status = "playing"
        vad_decider = self._resolve_vad_decider()
        frame_ms = max(1, self.config.audio.frame_duration_ms)
        max_poll = max(1, self.config.vad.max_utterance_ms // frame_ms)
        guard = 0
        interrupted = False
        while active() and guard < max_poll:
            guard += 1
            batch = tuple(
                self.audio.capture_frames(
                    device_id=self.config.audio.input_device_id,
                    sample_rate=self.config.audio.sample_rate,
                    channel_count=self.config.audio.channel_count,
                    frame_count=1,
                )
            )
            if batch and vad_decider(batch[0]):
                self.audio.interrupt_playback(reason_code="barge_in.user_speech_detected")
                self._playback_status = "interrupted"
                self._queued_tts_count = 0
                self._record(VoiceWorkerEventType.BARGE_IN_DETECTED, trace_id=trace_id, summary={"speak": True, "reason_code": "barge_in.user_speech_detected"})
                interrupted = True
                break
        if not interrupted:
            self._playback_status = "completed"
            self._record(VoiceWorkerEventType.PLAYBACK_FINISHED, trace_id=trace_id, summary={"speak": True, "status": "completed", "barge_in": True})

    def _handle_listen(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        """Capture one follow-up utterance on demand (no wake required).

        Enables continuous multi-turn voice: after the assistant speaks, the
        shell calls `listen` to capture the user's next utterance and emit its
        transcript (TRANSCRIPTION_COMPLETED), which the shell turns into the
        next chat turn. If the user says nothing, capture bails on silence and
        no transcript is emitted, so the loop idles back to wake-word mode.
        """

        trace_id = self._trace_id_for(command)
        if self._continuous_active:
            # The continuous wake loop owns the mic; a chunked capture here would
            # conflict on the single input device. The wake loop already
            # captures wake-triggered commands, so re-wake drives the next turn.
            return self._record(
                VoiceWorkerEventType.VAD_SPEECH_ENDED,
                trace_id=trace_id,
                summary={"reason_code": "continuous_capture_active", "listen": True},
            )
        before = len(self._events)
        self._run_post_wake_capture(parent_trace_id=trace_id)
        if len(self._events) > before:
            return self._events[-1]
        return self._record(
            VoiceWorkerEventType.VAD_SPEECH_ENDED,
            trace_id=trace_id,
            summary={"reason_code": "no_speech", "listen": True},
        )

    def _handle_install_model(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        result = self.asset_manager.install_local(VoiceModelInstallRequest.model_validate(command.payload))
        return self._record(VoiceWorkerEventType.MIC_STARTED, trace_id=self._trace_id_for(command), summary=result.model_dump(mode="json"))

    def _handle_download_model(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        result = self.asset_manager.download(VoiceModelDownloadRequest.model_validate(command.payload))
        return self._record(VoiceWorkerEventType.MIC_STARTED, trace_id=self._trace_id_for(command), summary=result.model_dump(mode="json"))

    def _handle_switch_stt_backend(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        self.config = self.config.model_copy(update={"active_stt_backend_id": str(command.payload.get("backend_id") or self.config.active_stt_backend_id)})
        return self._record(VoiceWorkerEventType.TRANSCRIPTION_STARTED, trace_id=self._trace_id_for(command), summary={"active_stt_backend_id": self.config.active_stt_backend_id})

    def _handle_switch_tts_backend(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        self.config = self.config.model_copy(update={"active_tts_backend_id": str(command.payload.get("backend_id") or self.config.active_tts_backend_id)})
        return self._record(VoiceWorkerEventType.TTS_STARTED, trace_id=self._trace_id_for(command), summary={"active_tts_backend_id": self.config.active_tts_backend_id})

    def _handle_switch_active_voice(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        self.config = self.config.model_copy(update={"active_voice_id": str(command.payload.get("voice_id") or self.config.active_voice_id)})
        return self._record(VoiceWorkerEventType.TTS_STARTED, trace_id=self._trace_id_for(command), summary={"active_voice_id": self.config.active_voice_id})

    def _handle_cancel(self, command: VoiceWorkerCommand) -> VoiceWorkerEvent:
        self.audio.stop_playback()
        self._playback_status = "stopped"
        self._queued_tts_count = 0
        return self._record(
            VoiceWorkerEventType.CANCELLED,
            trace_id=self._trace_id_for(command),
            summary={
                "cancellation": {
                    "schema_version": command.schema_version,
                    "trace_id": self._trace_id_for(command),
                    "command_id": command.command_id,
                    "reason_code": str(command.payload.get("reason_code") or "cancelled"),
                    "raw_audio_persisted": False,
                    "raw_transcript_persisted": False,
                }
            },
        )

    def _record(self, event_type: VoiceWorkerEventType, *, trace_id: str, summary: dict[str, Any] | None = None) -> VoiceWorkerEvent:
        event = VoiceWorkerEvent(event_id=f"voice-worker-event-{len(self._events) + 1}", event_type=event_type, trace_id=trace_id, summary=summary or {})
        self._events.append(event)
        return event

    def _telemetry_summary(self) -> dict[str, object]:
        event_counts: dict[str, int] = {}
        for event in self._events:
            event_counts[event.event_type.value] = event_counts.get(event.event_type.value, 0) + 1
        wakeword_health = self.wakeword_supervisor.health()
        return {
            "event_count": len(self._events),
            "event_counts": event_counts,
            "worker_lifecycle_events": sum(1 for event in self._events if event.summary.get("explicit_user_triggered") is True or "paused" in event.summary or "resumed" in event.summary),
            "mic_capture_events": sum(1 for event in self._events if event.event_type == VoiceWorkerEventType.MIC_STARTED and "peak_level" in event.summary),
            "wakeword_detections": sum(1 for event in self._events if event.event_type == VoiceWorkerEventType.WAKEWORD_DETECTED),
            "vad_speech_segments": sum(1 for event in self._events if event.event_type == VoiceWorkerEventType.VAD_SPEECH_ENDED),
            "stt_events": sum(1 for event in self._events if event.event_type == VoiceWorkerEventType.TRANSCRIPTION_COMPLETED),
            "tts_events": sum(1 for event in self._events if event.event_type == VoiceWorkerEventType.TTS_STARTED),
            "playback_events": sum(1 for event in self._events if event.event_type in {VoiceWorkerEventType.PLAYBACK_STARTED, VoiceWorkerEventType.PLAYBACK_FINISHED, VoiceWorkerEventType.BARGE_IN_DETECTED}),
            "barge_in_events": sum(1 for event in self._events if event.event_type == VoiceWorkerEventType.BARGE_IN_DETECTED),
            "error_events": sum(1 for event in self._events if event.event_type == VoiceWorkerEventType.ERROR),
            "wakeword_tick_count": wakeword_health.tick_count,
            "wakeword_last_tick_at": wakeword_health.last_tick_at,
            "durations_counts_only": True,
            "raw_audio_persisted": False,
            "raw_transcript_persisted": False,
        }
