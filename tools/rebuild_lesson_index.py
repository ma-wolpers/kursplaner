#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from kursplaner.adapters.bootstrap.wiring import build_gui_dependencies


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild lesson index for an Unterricht root directory.")
    parser.add_argument("unterricht_dir", help="Path to the Unterricht directory root")
    args = parser.parse_args()

    unterricht_dir = Path(args.unterricht_dir).expanduser().resolve()
    if not unterricht_dir.exists() or not unterricht_dir.is_dir():
        print(f"Invalid unterricht_dir: {unterricht_dir}")
        return 2

    deps = build_gui_dependencies()
    deps.rebuild_lesson_index.execute(unterricht_dir)
    print(f"Lesson index rebuilt: {unterricht_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
