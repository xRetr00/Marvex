"""Generate the "Hey Marvex" keyword files for the sherpa-onnx KWS model.

The shipped sherpa-onnx KWS model is a *generic* open-vocabulary keyword spotter
and :code:`keywords.txt` only contains sample phrases (HELLO WORLD, HI GOOGLE,
HEY SIRI ...). This script re-writes ``keywords.txt`` (BPE-tokenised) and
``keywords_raw.txt`` (human phrases) so the wake word is actually "Hey Marvex"
and a few pronunciation variants, tokenised with the model's own ``bpe.model``.

sherpa-onnx keyword line format:  ``<tok> <tok> ... :<boost> #<threshold> @<text>``
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Uppercase because the gigaspeech BPE model is upper-cased. Variants widen
# recall for the "Hey Marvex" wake phrase.
DEFAULT_PHRASES: tuple[str, ...] = (
    "HEY MARVEX",
    "HI MARVEX",
    "HELLO MARVEX",
    "OK MARVEX",
    "HEY MARVECKS",
    "HEY MARVIX",
)

DEFAULT_BOOST = 1.5
DEFAULT_THRESHOLD = 0.20


def format_keyword_line(pieces: list[str], *, boost: float, threshold: float, text: str) -> str:
    tokens = " ".join(pieces).strip()
    return f"{tokens} :{boost:g} #{threshold:g} @{text}"


def find_kws_model_dir(root: Path) -> Path | None:
    """Locate the directory containing the KWS model (has bpe.model + tokens.txt),
    searching recursively so the sherpa archive's nested layout is tolerated."""
    root = Path(root)
    if (root / "bpe.model").is_file():
        return root
    for bpe in root.rglob("bpe.model"):
        return bpe.parent
    return None


def generate(model_dir: Path, *, phrases: tuple[str, ...] = DEFAULT_PHRASES, boost: float = DEFAULT_BOOST, threshold: float = DEFAULT_THRESHOLD) -> Path:
    import sentencepiece as spm

    bpe = model_dir / "bpe.model"
    if not bpe.is_file():
        raise FileNotFoundError(f"bpe.model not found in {model_dir}")
    sp = spm.SentencePieceProcessor()
    sp.load(str(bpe))

    keyword_lines: list[str] = []
    raw_lines: list[str] = []
    for phrase in phrases:
        pieces = sp.encode(phrase, out_type=str)
        keyword_lines.append(format_keyword_line(pieces, boost=boost, threshold=threshold, text=phrase))
        raw_lines.append(phrase)

    keywords_path = model_dir / "keywords.txt"
    keywords_path.write_text("\n".join(keyword_lines) + "\n", encoding="utf-8")
    (model_dir / "keywords_raw.txt").write_text("\n".join(raw_lines) + "\n", encoding="utf-8")
    return keywords_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Hey Marvex KWS keyword files.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--asset-root", help="Voice-asset root to search for the KWS model.")
    group.add_argument("--model-dir", help="Exact KWS model dir (contains bpe.model).")
    args = parser.parse_args(argv)

    if args.model_dir:
        model_dir: Path | None = Path(args.model_dir)
    else:
        model_dir = find_kws_model_dir(Path(args.asset_root))
    if model_dir is None or not model_dir.is_dir():
        print("ERROR: KWS model dir (with bpe.model) not found.", file=sys.stderr)
        return 1

    keywords = generate(model_dir)
    print(f"Wrote Hey Marvex keywords to {keywords}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
