from __future__ import annotations

from packages.ui_directives import directives_from_tool_calls, parse_ui_directives


def test_plain_text_yields_no_directives() -> None:
    directives, clean = parse_ui_directives("The capital of France is Paris.")
    assert directives == []
    assert clean == "The capital of France is Paris."


def test_parses_product_block_and_strips_it() -> None:
    text = (
        "Here are the best laptops:\n"
        "```marvex:ui\n"
        '{"directives":[{"kind":"product","products":['
        '{"title":"Dell XPS 15","price":1299,"rating":4.5,"badge":"new"},'
        '{"title":"MacBook Air","price":999}]}]}\n'
        "```\n"
    )
    directives, clean = parse_ui_directives(text)
    assert len(directives) == 1
    assert directives[0]["kind"] == "product"
    assert len(directives[0]["products"]) == 2
    assert directives[0]["products"][0]["title"] == "Dell XPS 15"
    assert directives[0]["products"][0]["price"] == 1299.0
    assert "marvex:ui" not in clean
    assert clean.startswith("Here are the best laptops")


def test_parses_info_image_plan() -> None:
    text = (
        "```marvex:ui\n"
        '{"directives":['
        '{"kind":"info","title":"Weather","body":"Sunny, 22C"},'
        '{"kind":"image","src":"https://x/y.png","title":"Chart"},'
        '{"kind":"plan","steps":["Gather files","Summarize","Email"]}]}\n'
        "```"
    )
    directives, _ = parse_ui_directives(text)
    kinds = [d["kind"] for d in directives]
    assert kinds == ["info", "image", "plan"]
    assert directives[2]["steps"] == ["Gather files", "Summarize", "Email"]


def test_invalid_json_block_is_ignored() -> None:
    directives, clean = parse_ui_directives("```marvex:ui\nnot json\n```\nhello")
    assert directives == []
    assert clean == "hello"


def test_invalid_directive_shapes_are_dropped() -> None:
    text = '```marvex:ui\n{"directives":[{"kind":"product","products":[]},{"kind":"bogus"}]}\n```'
    directives, _ = parse_ui_directives(text)
    assert directives == []


def test_tool_calls_map_to_directives() -> None:
    calls = [
        {"name": "show_info", "arguments": {"title": "Hi", "body": "there"}},
        {"name": "show_product", "arguments": '{"products":[{"title":"X","price":10}]}'},
        {"name": "not_a_ui_tool", "arguments": {}},
    ]
    directives = directives_from_tool_calls(calls)
    assert [d["kind"] for d in directives] == ["info", "product"]
    assert directives[1]["products"][0]["title"] == "X"
