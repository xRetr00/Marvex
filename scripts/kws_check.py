"""Replay a WAV through the installed KWS model and report wake-word detections.

Triage tool for "Hey Marvex never fires". Point it at the dumped mic audio
(MARVEX_VOICE_DEBUG_DUMP) and the installed wake-word model dir; it runs the
exact sherpa-onnx KeywordSpotter with the model's bpe-generated keywords and
prints how many times the wake word is detected.

  python scripts/kws_check.py --wav dump.wav --model-dir <voice-assets>/wakeword/hey-marvex

If the dumped audio DOES detect here but not live, the live streaming feed is the
problem. If it does NOT detect here either, the audio content/format is.
"""

from __future__ import annotations

import argparse
import glob
import struct
import sys
import wave
from pathlib import Path


def _say(text: str) -> None:
    # Console-safe (Windows cp1252 can't print sentencepiece marker chars).
    sys.stdout.write(text.encode("ascii", "replace").decode("ascii") + "\n")


def _find(model_dir: Path, pattern: str) -> Path | None:
    matches = sorted(glob.glob(str(model_dir / "**" / pattern), recursive=True))
    int8 = [m for m in matches if "int8" in m]
    chosen = (int8 or matches)
    return Path(chosen[0]) if chosen else None


def _generate_keywords(model_dir: Path, tokens: Path, phrase: str) -> Path | None:
    bpe = _find(model_dir, "bpe.model")
    if bpe is None:
        return None
    try:
        import sentencepiece as spm
    except Exception:
        return None
    sp = spm.SentencePieceProcessor()
    sp.load(str(bpe))
    pieces = sp.encode(phrase.upper(), out_type=str)
    line = " ".join(str(p) for p in pieces) + " :2.0 #0.2 @WAKE"
    out = model_dir / "kws_check_keywords.txt"
    out.write_text(line + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay a WAV through the KWS model.")
    parser.add_argument("--wav", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--phrase", default="Hey Marvex")
    parser.add_argument("--keywords", default=None, help="Optional explicit keywords.txt")
    parser.add_argument("--threshold", type=float, default=0.25)
    parser.add_argument("--chunk-ms", type=int, default=300)
    args = parser.parse_args(argv)

    import sherpa_onnx

    model_dir = Path(args.model_dir)
    enc = _find(model_dir, "encoder*.onnx")
    dec = _find(model_dir, "decoder*.onnx")
    joi = _find(model_dir, "joiner*.onnx")
    tok = _find(model_dir, "tokens.txt")
    if not all((enc, dec, joi, tok)):
        print(f"[ERROR] model files missing under {model_dir}", file=sys.stderr)
        return 2
    _say(f"encoder={enc.name} ({enc.stat().st_size}) decoder={dec.name} joiner={joi.name}")

    keywords = Path(args.keywords) if args.keywords else _generate_keywords(model_dir, tok, args.phrase)
    if keywords is None:
        print("[ERROR] could not build keywords (need sentencepiece + bpe.model, or pass --keywords)", file=sys.stderr)
        return 2
    _say(f"keywords: {keywords.read_text(encoding='utf-8').strip()}")

    handle = wave.open(args.wav, "rb")
    n, sr = handle.getnframes(), handle.getframerate()
    raw = handle.readframes(n)
    samples = [s / 32768.0 for s in struct.unpack("<%dh" % n, raw)]
    peak = max((abs(s) for s in samples), default=0.0)
    _say(f"wav: {round(n / sr, 2)}s @ {sr}Hz, peak float {round(peak, 3)}")

    ks = sherpa_onnx.KeywordSpotter(
        tokens=str(tok), encoder=str(enc), decoder=str(dec), joiner=str(joi),
        keywords_file=str(keywords), num_threads=1, keywords_threshold=args.threshold, provider="cpu",
    )
    stream = ks.create_stream()
    chunk = max(1, int(sr * args.chunk_ms / 1000))
    hits = []
    for i in range(0, len(samples), chunk):
        stream.accept_waveform(sr, samples[i:i + chunk])
        while ks.is_ready(stream):
            ks.decode_stream(stream)
        result = ks.get_result(stream)
        if result:
            hits.append((round(i / sr, 2), result))
            ks.reset_stream(stream)
    _say(f"DETECTIONS: {hits}")
    _say("RESULT: " + ("DETECTED" if hits else "NOT DETECTED"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
