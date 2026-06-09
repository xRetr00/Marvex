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
    "MARVEX",
)

DEFAULT_BOOST = 2.0
DEFAULT_THRESHOLD = 0.10


def format_keyword_line(pieces: list[str], *, boost: float, threshold: float, text: str) -> str:
    tokens = " ".join(pieces).strip()
    return f"{tokens} :{boost:g} #{threshold:g} @{text}"


# ARPAbet phonemes for the coined wake word (not in the en.phone lexicon used by
# the phoneme-based zh-en KWS model). "Marvex" => MAR-veks. Verified to detect.
COINED_PHONEMES: dict[str, tuple[str, ...]] = {
    "HEY": (
        "HH EY1",
        "HH EY0",
        "HH EH1",
        "HH EH0",
        "HH HH EY1",
    ),
    "MARVEX": (
        "M AA1 R V EH1 K S",
        "M AA1 R V EH0 K S",
        "M AA1 R V IH0 K S",
        "M AA0 R V EH1 K S",
        "M AE1 R V EH1 K S",
        "M AA1 R V AH0 K S",
        "M AA1 R V IH1 K S",
        "M AA1 R V EH1 K",
        "M AA1 R V IH0 K",
        "M AA1 R F EH1 K S",
        "M AA1 R V EH1 G S",
        "M ER1 V EH1 K S",
    ),
    "MARVECKS": ("M AA1 R V EH1 K S",),
    "MARVIX": ("M AA1 R V IH1 K S",),
}


def find_kws_model_dir(root: Path) -> Path | None:
    """Locate the KWS model dir. Supports both families: BPE (has bpe.model) and
    phoneme (has en.phone). Searches recursively for the sherpa nested layout."""
    root = Path(root)
    for marker in ("bpe.model", "en.phone"):
        if (root / marker).is_file():
            return root
        for found in root.rglob(marker):
            return found.parent
    return None


def _bpe_pieces(model_dir: Path, phrases: tuple[str, ...]) -> list[tuple[str, list[str]]]:
    bpe = model_dir / "bpe.model"
    if not bpe.is_file():
        return []
    import sentencepiece as spm

    sp = spm.SentencePieceProcessor()
    sp.load(str(bpe))
    return [(phrase, [str(p) for p in sp.encode(phrase, out_type=str)]) for phrase in phrases]


def _phoneme_pieces(model_dir: Path, phrases: tuple[str, ...]) -> list[tuple[str, list[str]]]:
    en_phone = model_dir / "en.phone"
    if not en_phone.is_file():
        return []
    lexicon: dict[str, str] = {}
    for line in en_phone.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            lexicon[parts[0].upper()] = " ".join(parts[1:])
    out: list[tuple[str, list[str]]] = []
    for phrase in phrases:
        word_options: list[tuple[str, ...]] = []
        ok = True
        for word in phrase.upper().split():
            options = COINED_PHONEMES.get(word) or ((lexicon[word],) if word in lexicon else ())
            if not options:
                ok = False
                break
            word_options.append(options)
        if not ok:
            continue
        import itertools

        variant = 0
        for combo in list(itertools.product(*word_options))[:64]:
            phones: list[str] = []
            for spelled in combo:
                phones.extend(spelled.split())
            if phones:
                alias = phrase if variant == 0 else f"{phrase}_{variant}"
                out.append((alias, phones))
                variant += 1
    return out


def generate(model_dir: Path, *, phrases: tuple[str, ...] = DEFAULT_PHRASES, boost: float = DEFAULT_BOOST, threshold: float = DEFAULT_THRESHOLD) -> Path:
    # BPE model (gigaspeech) or phoneme model (zh-en) - encode with whichever the
    # model provides so the keyword tokens match what the model emits.
    pieces = _bpe_pieces(model_dir, phrases) or _phoneme_pieces(model_dir, phrases)
    if not pieces:
        raise FileNotFoundError(f"No usable tokenizer (bpe.model or en.phone) in {model_dir}")

    keyword_lines = [format_keyword_line(toks, boost=boost, threshold=threshold, text=text) for text, toks in pieces]
    raw_lines = [text for text, _ in pieces]

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
