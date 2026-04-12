#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PROJECT_DIR = ROOT / "Code" / "kursplaner"


def main() -> int:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/test_main_window_intents.py",
        "tests/test_lesson_index_repository.py",
        "tests/test_plan_overview_with_index.py",
    ]
    result = subprocess.run(cmd, cwd=str(PROJECT_DIR), check=False)
    return int(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
