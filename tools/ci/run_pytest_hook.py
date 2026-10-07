#!/usr/bin/env python3
"""pre-push-Hook: fuehrt eine schnelle Auswahl zentraler Tests aus."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Repo-Wurzel (tools/ci/<datei> -> zwei Ebenen hoch), unabhaengig vom Ablageort.
ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    """Startet pytest fuer die Kern-Testauswahl in der Repo-Wurzel und liefert dessen Exit-Code."""
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/test_main_window_intents.py",
        "tests/test_lesson_index_repository.py",
        "tests/test_plan_overview_with_index.py",
    ]
    result = subprocess.run(cmd, cwd=str(ROOT), check=False)
    return int(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
