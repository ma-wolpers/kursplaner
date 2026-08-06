import pytest

from bw_libs.safe_read import (
    FileParseError,
    FileReadError,
    read_json,
    read_json_or_default,
    read_or_default,
    read_text,
    read_text_or_default,
)


def test_read_text_returns_content(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("hello", encoding="utf-8")

    assert read_text(path) == "hello"


def test_read_text_raises_file_read_error_when_missing(tmp_path):
    path = tmp_path / "missing.txt"

    with pytest.raises(FileReadError):
        read_text(path)


def test_read_json_returns_parsed_payload(tmp_path):
    path = tmp_path / "file.json"
    path.write_text('{"a": 1}', encoding="utf-8")

    assert read_json(path) == {"a": 1}


def test_read_json_raises_file_read_error_when_missing(tmp_path):
    path = tmp_path / "missing.json"

    with pytest.raises(FileReadError):
        read_json(path)


def test_read_json_raises_file_parse_error_on_corrupt_content(tmp_path):
    path = tmp_path / "file.json"
    path.write_text("not json", encoding="utf-8")

    with pytest.raises(FileParseError):
        read_json(path)


def test_read_or_default_returns_result_on_success():
    assert read_or_default(lambda: 42, default=0) == 42


def test_read_or_default_returns_default_on_any_exception():
    def _raise():
        raise ValueError("boom")

    assert read_or_default(_raise, default="fallback") == "fallback"


def test_read_text_or_default_returns_default_when_missing(tmp_path):
    path = tmp_path / "missing.txt"

    assert read_text_or_default(path, default=None) is None


def test_read_text_or_default_returns_content_on_success(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("hello", encoding="utf-8")

    assert read_text_or_default(path, default=None) == "hello"


def test_read_json_or_default_returns_default_on_corrupt_content(tmp_path):
    path = tmp_path / "file.json"
    path.write_text("not json", encoding="utf-8")

    assert read_json_or_default(path, default=None) is None


def test_read_json_or_default_returns_payload_on_success(tmp_path):
    path = tmp_path / "file.json"
    path.write_text('{"a": 1}', encoding="utf-8")

    assert read_json_or_default(path, default=None) == {"a": 1}
