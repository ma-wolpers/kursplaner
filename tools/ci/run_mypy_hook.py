#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def main() -> int:
    files = [
        "Code/kursplaner/kursplaner/core/ports/repositories.py",
        "Code/kursplaner/kursplaner/core/usecases/rebuild_lesson_index_usecase.py",
        "Code/kursplaner/kursplaner/core/usecases/invalidate_lesson_index_usecase.py",
        "Code/kursplaner/kursplaner/infrastructure/repositories/lesson_index_repository.py",
    ]
    cmd = [sys.executable, "-m", "mypy", *files]
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
