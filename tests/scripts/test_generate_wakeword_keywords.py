from pathlib import Path

from scripts.generate_wakeword_keywords import find_kws_model_dir, format_keyword_line


def test_format_keyword_line() -> None:
    line = format_keyword_line(["▁HE", "Y", "▁MA", "R", "VE", "X"], boost=1.5, threshold=0.2, text="HEY MARVEX")
    assert line == "▁HE Y ▁MA R VE X :1.5 #0.2 @HEY MARVEX"


def test_find_kws_model_dir_direct(tmp_path: Path) -> None:
    (tmp_path / "bpe.model").write_bytes(b"x")
    assert find_kws_model_dir(tmp_path) == tmp_path


def test_find_kws_model_dir_nested(tmp_path: Path) -> None:
    nested = tmp_path / "sherpa-onnx-kws-zipformer" / "inner"
    nested.mkdir(parents=True)
    (nested / "bpe.model").write_bytes(b"x")
    assert find_kws_model_dir(tmp_path) == nested


def test_find_kws_model_dir_absent(tmp_path: Path) -> None:
    assert find_kws_model_dir(tmp_path) is None
