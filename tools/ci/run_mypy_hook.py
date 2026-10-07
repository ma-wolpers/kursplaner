#!/usr/bin/env python3
"""pre-push-Hook: Typpruefung der Lesson-Index-Kernmodule mit mypy."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Repo-Wurzel (tools/ci/<datei> -> zwei Ebenen hoch), unabhaengig vom Ablageort.
ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    """Startet mypy fuer die Lesson-Index-Kernmodule in der Repo-Wurzel und liefert dessen Exit-Code."""
    files = [
        "kursplaner/core/ports/repositories.py",
        "kursplaner/core/usecases/rebuild_lesson_index_usecase.py",
        "kursplaner/core/usecases/invalidate_lesson_index_usecase.py",
        "kursplaner/infrastructure/repositories/lesson_index_repository.py",
    ]
    cmd = [
        sys.executable,
        "-m",
        "mypy",
        "--follow-imports=skip",
        *files,
    ]
    result = subprocess.run(cmd, cwd=str(ROOT), check=False)
    return int(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
