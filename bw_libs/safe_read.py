"""Shared safe-read helpers and exception hierarchy for tolerant file access.

Read-side counterpart to the ``atomic_write_*`` helpers in ``bw_libs.app_paths``:
centralizes the "read file, fall back to a default on any failure" pattern that
was previously duplicated as ad-hoc ``except Exception:`` blocks across repositories.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, TypeVar, cast

T = TypeVar("T")


class RepositoryReadError(RuntimeError):
    """Base for tolerated read/parse failures in read-side repositories."""


class FileReadError(RepositoryReadError):
    """Raised when a file cannot be read from disk (missing, permissions, I/O error)."""


class FileParseError(RepositoryReadError):
    """Raised when file content cannot be parsed (decode, JSON, or format error)."""


def read_text(path: Path, *, encoding: str = "utf-8") -> str:
    """Read a file's text content, raising FileReadError on any I/O failure."""
    try:
        return path.read_text(encoding=encoding)
    except OSError as exc:
        raise FileReadError(f"Failed to read {path}") from exc


def read_json(path: Path, *, encoding: str = "utf-8") -> object:
    """Read and parse a JSON file, raising FileReadError/FileParseError on failure."""
    text = read_text(path, encoding=encoding)
    try:
        return json.loads(text)
    except ValueError as exc:
        raise FileParseError(f"Failed to parse JSON in {path}") from exc


def read_or_default(read_fn: Callable[[], T], default: T) -> T:
    """Call read_fn, returning default if any exception occurs.

    Central, single point for the "best-effort read, tolerate any failure"
    pattern used across read-side repositories, regardless of whether read_fn
    performs a raw file read, a JSON parse, or a domain-specific parse (e.g.
    YAML frontmatter) on already-read content.
    """
    try:
        return read_fn()
    except Exception:
        return default


def read_text_or_default(path: Path, default: str | None, *, encoding: str = "utf-8") -> str | None:
    """Read a file's text content, returning default if reading fails."""
    return read_or_default(lambda: read_text(path, encoding=encoding), default)


def read_json_or_default(path: Path, default: T, *, encoding: str = "utf-8") -> T:
    """Read and parse a JSON file, returning default if reading or parsing fails."""
    return read_or_default(lambda: cast(T, read_json(path, encoding=encoding)), default)
