#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PATTERN = re.compile(r"\bkursplaner\.infrastructure\b")

# Allowed locations relative to repo root where infra imports are acceptable
ALLOWED_REL_PATHS = {
    "kursplaner/adapters/bootstrap/wiring.py",
}

EXCLUDE_DIRS = {".git", ".venv", "venv", "node_modules", ".github"}


def is_excluded(path: Path) -> bool:
    for part in path.parts:
        if part in EXCLUDE_DIRS:
            return True
    return False


def main() -> int:
    violations: list[tuple[Path, int, str]] = []

    for py in ROOT.rglob("*.py"):
        if is_excluded(py.relative_to(ROOT)):
            continue
        # allow scripts under tools and tests to import infra (tests may need to import)
        rel = py.relative_to(ROOT).as_posix()
        # allow tests and tooling
        if rel.startswith("tests/") or rel.startswith("tools/"):
            continue
        # allow files inside the infrastructure package to import infra internals
        if rel.startswith("kursplaner/infrastructure/"):
            continue

        try:
            text = py.read_text(encoding="utf-8")
        except Exception:
            continue

        for m in PATTERN.finditer(text):
            # if file is in allowed list, skip
            if rel in ALLOWED_REL_PATHS:
                continue
            # record violation line
            lineno = text.count("\n", 0, m.start()) + 1
            snippet = text.splitlines()[lineno - 1].strip()
            violations.append((py, lineno, snippet))

    if violations:
        print("Forbidden imports of kursplaner.infrastructure found:")
        for path, lineno, line in violations:
            print(f" - {path.relative_to(ROOT)}:{lineno}: {line}")
        return 2

    print("No forbidden infra imports found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
