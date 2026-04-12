#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kursplaner.core.domain.plan_table import PlanTableData  # noqa: E402
from kursplaner.core.usecases.plan_overview_query_usecase import PlanOverviewQueryUseCase  # noqa: E402
from kursplaner.infrastructure.repositories.lesson_index_repository import FileSystemLessonIndexRepository  # noqa: E402
from kursplaner.infrastructure.repositories.lesson_repository import FileSystemLessonRepository  # noqa: E402


def _write_lesson(path: Path, number: int) -> None:
    content = (
        "---\n"
        "Stundentyp: Unterricht\n"
        "Dauer: 2\n"
        "Kompetenzen:\n"
        '  - ""\n'
        f"Stundenthema: Thema {number}\n"
        'Stundenziel: ""\n'
        "Material:\n"
        '  - ""\n'
        f"Oberthema: Ober {number % 5}\n"
        "---\n\n# Inhalt\n"
    )
    path.write_text(content, encoding="utf-8")


def _build_plan_table(root: Path, rows: int) -> PlanTableData:
    lesson_dir = root / "FachA" / "Einheiten"
    lesson_dir.mkdir(parents=True, exist_ok=True)

    table_rows: list[list[str]] = []
    for idx in range(1, rows + 1):
        lesson_name = f"stunde-{idx}"
        _write_lesson(lesson_dir / f"{lesson_name}.md", idx)
        table_rows.append([f"2026-03-{(idx % 28) + 1:02d}", "2", f"[[{lesson_name}]]"])

    return PlanTableData(
        markdown_path=root / "FachA" / "FachA.md",
        headers=["datum", "stunden", "inhalt"],
        rows=table_rows,
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={},
    )


def run_benchmark(rows: int, iterations: int) -> tuple[float, float]:
    with tempfile.TemporaryDirectory(prefix="overview-bench-") as temp_dir:
        root = Path(temp_dir) / "Unterricht"
        table = _build_plan_table(root, rows)

        lesson_repo = FileSystemLessonRepository()
        index_repo = FileSystemLessonIndexRepository()
        index_repo.rebuild_index(root)

        usecase = PlanOverviewQueryUseCase(lesson_repo=lesson_repo, lesson_index_repo=index_repo)

        start = time.perf_counter()
        for _ in range(iterations):
            usecase.summarize_plan(table)
        duration = time.perf_counter() - start

        avg_ms = (duration / iterations) * 1000.0
        return duration, avg_ms


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark for PlanOverviewQueryUseCase.")
    parser.add_argument("--rows", type=int, default=200, help="Number of plan rows to generate")
    parser.add_argument("--iterations", type=int, default=200, help="Number of summarize iterations")
    parser.add_argument(
        "--max-avg-ms",
        type=float,
        default=None,
        help="Optional guard: fail with exit code 2 when avg ms per call is above this threshold",
    )
    args = parser.parse_args()

    total, avg_ms = run_benchmark(rows=args.rows, iterations=args.iterations)
    print(f"rows={args.rows} iterations={args.iterations}")
    print(f"total_seconds={total:.6f}")
    print(f"avg_ms_per_call={avg_ms:.3f}")

    if args.max_avg_ms is not None and avg_ms > args.max_avg_ms:
        print(f"benchmark_guard=failed avg_ms_per_call={avg_ms:.3f} max_avg_ms={args.max_avg_ms:.3f}")
        return 2

    if args.max_avg_ms is not None:
        print(f"benchmark_guard=passed avg_ms_per_call={avg_ms:.3f} max_avg_ms={args.max_avg_ms:.3f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
