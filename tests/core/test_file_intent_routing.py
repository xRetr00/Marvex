"""Tests for the file-capability intent parser.

The Core service previously routed "what is the pdf files on my desktop?" to
``file.read`` against the literal "Desktop" path, which the tool worker then
rejected with a generic "blocked by policy" message. These tests pin down the
intent-detection heuristics so the same regression doesn't slip back.
"""

from packages.core.orchestration.file_intent import file_request_from_input


def test_question_form_pdf_files_on_desktop_routes_to_list():
    req = file_request_from_input("What is the PDF files on my desktop?")
    assert req["capability"] == "list"
    assert req["capability_id"] == "file.list"
    assert req["arguments"]["path"] == "Desktop"
    assert req["extension"] == ".pdf"


def test_what_files_in_downloads_routes_to_list():
    req = file_request_from_input("what files are in downloads")
    assert req["capability"] == "list"
    assert req["arguments"]["path"] == "Downloads"


def test_show_me_files_on_desktop_routes_to_list():
    req = file_request_from_input("show me the files on my desktop")
    assert req["capability"] == "list"
    assert req["arguments"]["path"] == "Desktop"


def test_explicit_read_file_keeps_read_capability():
    req = file_request_from_input("read file C:/notes/today.md")
    assert req["capability"] == "read"
    assert req["capability_id"] == "file.read"


def test_search_keyword_still_routes_to_search():
    req = file_request_from_input("search for invoice in Documents")
    # "documents" + "files? Actually phrase contains 'invoice in documents' which has 'in documents',
    # is_list_intent requires "files" + dir or one of the list_markers. This isn't a list intent
    # because it doesn't say 'files'. Falls through to "search" since lowered contains "search".
    assert req["capability"] == "search"
    assert req["capability_id"] == "file.search"


def test_document_in_directory_routes_to_rg_search():
    req = file_request_from_input("find the report document on my desktop")
    assert req["capability"] == "search"
    assert req["capability_id"] == "file.rg"


def test_bare_pdf_files_on_my_desktop_phrasing_lists_with_extension_filter():
    req = file_request_from_input("pdf files on my desktop")
    assert req["capability"] == "list"
    assert req["arguments"]["path"] == "Desktop"
    assert req["extension"] == ".pdf"


def test_open_file_explicit_verb_keeps_read_capability():
    req = file_request_from_input("open file notes/today.md")
    assert req["capability"] == "read"
