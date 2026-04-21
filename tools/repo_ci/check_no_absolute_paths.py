#!/usr/bin/env python3
"""Fail CI when tracked JSON content contains absolute filesystem paths."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

TRACKED_JSON_GLOBS = (
    "config/*.json",
    "kursplaner/resources/**/*.json",
)

RELEVANT_PATH_PREFIXES = (
    "config/",
    "kursplaner/core/config/",
    "tools/repo_ci/",
    ".github/workflows/",
)

RELEVANT_EXACT_PATHS = {
    "tools/repo_ci/check_no_absolute_paths.py",
    ".github/workflows/repo-path-guardrails.yml",
    "kursplaner/core/config/path_store.py",
}

_WINDOWS_ABSOLUTE_RE = re.compile(r"^[a-zA-Z]:[\\/]")
_UNC_RE = re.compile(r"^[\\/]{2}[^\\/]+[\\/][^\\/]+")
_POSIX_ABSOLUTE_RE = re.compile(r"^/")


def _run_git(args: list[str]) -> str | None:
    """Run git command in repository root and return stdout when successful."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(ROOT),
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    return result.stdout


def _paths_from_git_stdout(stdout: str | None) -> set[str]:
    """Normalize and split path output from git commands."""
    if not stdout:
        return set()
    return {
        line.strip().replace("\\", "/")
        for line in stdout.splitlines()
        if line.strip()
    }


def _staged_files() -> set[str]:
    """Return staged file paths for local pre-commit runs."""
    return _paths_from_git_stdout(_run_git(["diff", "--cached", "--name-only"]))


def _ci_changed_files() -> set[str]:
    """Return changed file paths in GitHub Actions for push and PR runs."""
    if os.getenv("GITHUB_ACTIONS", "").lower() != "true":
        return set()

    base_ref = (os.getenv("GITHUB_BASE_REF") or "").strip()
    if base_ref:
        _run_git(["fetch", "--no-tags", "--depth=1", "origin", base_ref])
        return _paths_from_git_stdout(_run_git(["diff", "--name-only", f"origin/{base_ref}...HEAD"]))

    before_sha = (os.getenv("GITHUB_EVENT_BEFORE") or "").strip()
    if before_sha and before_sha != "0000000000000000000000000000000000000000":
        return _paths_from_git_stdout(_run_git(["diff", "--name-only", f"{before_sha}...HEAD"]))

    return set()


def _changed_paths_for_relevance() -> set[str]:
    """Prefer staged files locally; use CI diff fallback on Actions."""
    staged = _staged_files()
    if staged:
        return staged
    return _ci_changed_files()


def _has_relevant_changes(paths: set[str]) -> bool:
    """Only run path guardrail when related files changed, otherwise skip fast."""
    if not paths:
        return True

    for path in paths:
        normalized = path.replace("\\", "/")
        if normalized in RELEVANT_EXACT_PATHS:
            return True
        if any(normalized.startswith(prefix) for prefix in RELEVANT_PATH_PREFIXES):
            return True
    return False


def _tracked_files_for_glob(pattern: str) -> list[str]:
    """Collect tracked files matching a git pathspec glob pattern."""
    output = _run_git(["ls-files", pattern])
    if output is None:
        return []
    return [line.strip().replace("\\", "/") for line in output.splitlines() if line.strip()]


def _iter_json_leaf_strings(value: object, dotted_path: str = "$"):
    """Yield all string leaf values from nested JSON payloads."""
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{dotted_path}.{key}"
            yield from _iter_json_leaf_strings(child, child_path)
        return

    if isinstance(value, list):
        for index, child in enumerate(value):
            child_path = f"{dotted_path}[{index}]"
            yield from _iter_json_leaf_strings(child, child_path)
        return

    if isinstance(value, str):
        yield dotted_path, value


def _looks_like_absolute_path(text: str) -> bool:
    """Return True when a string looks like an absolute filesystem path."""
    stripped = text.strip()
    if not stripped:
        return False

    if stripped.startswith(("http://", "https://", "data:", "mailto:")):
        return False

    return bool(
        _WINDOWS_ABSOLUTE_RE.match(stripped)
        or _UNC_RE.match(stripped)
        or _POSIX_ABSOLUTE_RE.match(stripped)
    )


def _validate_file(rel_path: str) -> list[str]:
    """Validate one tracked JSON file and return all absolute-path violations."""
    path = ROOT / rel_path
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"{rel_path}: invalid json ({exc})"]

    violations: list[str] = []
    for dotted_path, text in _iter_json_leaf_strings(payload):
        if _looks_like_absolute_path(text):
            violations.append(f"{rel_path}: absolute path at {dotted_path} -> {text}")
    return violations


def main() -> int:
    """Execute guardrail check and return CI-friendly process code."""
    changed_paths = _changed_paths_for_relevance()
    if not _has_relevant_changes(changed_paths):
        print("Path guardrail check skipped (no guardrail-relevant changed files).")
        return 0

    files: set[str] = set()
    for pattern in TRACKED_JSON_GLOBS:
        files.update(_tracked_files_for_glob(pattern))

    if not files:
        print("No tracked JSON files found for path guardrail check.")
        return 0

    errors: list[str] = []
    for rel_path in sorted(files):
        errors.extend(_validate_file(rel_path))

    if errors:
        print("Absolute JSON paths are not allowed:")
        for item in errors:
            print(f" - {item}")
        return 1

    print("Path guardrail check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
