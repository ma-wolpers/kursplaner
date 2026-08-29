#!/usr/bin/env python3
"""Benchmark: build_day_columns() (voller Rebuild) vs. build_day_columns_incremental()

(Einzelzeilen-Patch) fuer den Hot Path "eine Zelle bearbeiten" (Kursplaner Item 1,
Performance-Fix 2026-08-29). Folgt derselben Struktur wie
`overview_query_benchmark.py` (synthetische Lesson-Dateien in einem
Temp-Verzeichnis, kein echter Plan).
"""

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
from kursplaner.core.usecases.load_plan_detail_usecase import LoadPlanDetailUseCase  # noqa: E402
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
        table_rows.append([f"2026-03-{(idx % 28) + 1:02d}", f"[[{lesson_name}]]", ""])

    return PlanTableData(
        markdown_path=root / "FachA" / "FachA.md",
        headers=["Datum", "Inhalt", "Thema/Ausfall"],
        rows=table_rows,
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={"Lerngruppe": "[[GK blau-1]]"},
    )


def run_benchmark(rows: int, edits: int) -> dict[str, float]:
    """Simuliert *edits* aufeinanderfolgende Einzelzell-Edits an wechselnden Zeilen,

    in drei Szenarien, damit die Beiträge von Primärfix (Item 1a) und
    Cache-Ergänzung (Item 1b) einzeln sichtbar werden -- ein reiner
    "voller Rebuild MIT Cache"-Vergleich würde den eigentlichen Effekt des
    Einzelzeilen-Patches unterschätzen, da der Cache bereits einen Großteil
    der vorher wiederholten YAML-Lesevorgänge abfängt:

    1. `full_no_cache`: voller Rebuild, JEDE Zeile über eine frische
       `FileSystemLessonRepository`-Instanz gelesen (kein Cache-Vorteil über
       mehrere Aufrufe hinweg) -- entspricht dem Verhalten vor dem
       gesamten Item-1-Fix.
    2. `full_with_cache`: voller Rebuild, aber mit derselben, über alle
       Edits hinweg wiederverwendeten Repository-Instanz -- isolierter
       Beitrag von Item 1b (Datei-signaturbasierter Cache) allein.
    3. `incremental_with_cache`: der tatsächlich ausgelieferte Zustand
       (Item 1a + 1b zusammen) -- Einzelzeilen-Patch über eine
       wiederverwendete Repository-Instanz.

    Returns:
        Dict mit den drei Gesamtzeiten (Sekunden) unter den obigen Namen.
    """
    with tempfile.TemporaryDirectory(prefix="day-columns-bench-") as temp_dir:
        root = Path(temp_dir) / "Unterricht"
        table = _build_plan_table(root, rows)
        lessons_dir = root / "FachA" / "Einheiten"

        # 1) Voller Rebuild ohne Cache -- entspricht dem Zustand vor Item 1.
        start = time.perf_counter()
        for i in range(edits):
            row_index = i % rows
            _write_lesson(lessons_dir / f"stunde-{row_index + 1}.md", row_index + 1000)
            no_cache_usecase = LoadPlanDetailUseCase(plan_repo=None, lesson_repo=FileSystemLessonRepository())
            no_cache_usecase.build_day_columns(table)
        full_no_cache = time.perf_counter() - start

        # 2) Voller Rebuild mit Cache (Item 1b isoliert).
        cached_repo = FileSystemLessonRepository()
        cached_usecase = LoadPlanDetailUseCase(plan_repo=None, lesson_repo=cached_repo)
        cached_usecase.build_day_columns(table)  # Kaltstart fuellt den Cache, nicht mitgezaehlt

        start = time.perf_counter()
        for i in range(edits):
            row_index = i % rows
            _write_lesson(lessons_dir / f"stunde-{row_index + 1}.md", row_index + 2000)
            cached_usecase.build_day_columns(table)
        full_with_cache = time.perf_counter() - start

        # 3) Einzelzeilen-Patch mit Cache -- der tatsaechlich ausgelieferte Zustand.
        incr_repo = FileSystemLessonRepository()
        incr_usecase = LoadPlanDetailUseCase(plan_repo=None, lesson_repo=incr_repo)
        previous = incr_usecase.build_day_columns(table)  # Kaltstart, nicht mitgezaehlt

        start = time.perf_counter()
        for i in range(edits):
            row_index = i % rows
            _write_lesson(lessons_dir / f"stunde-{row_index + 1}.md", row_index + 3000)
            previous = incr_usecase.build_day_columns_incremental(table, previous, {row_index})
        incremental_with_cache = time.perf_counter() - start

        return {
            "full_no_cache": full_no_cache,
            "full_with_cache": full_with_cache,
            "incremental_with_cache": incremental_with_cache,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=100, help="Anzahl Planzeilen (verlinkte Stunden-Dateien)")
    parser.add_argument("--edits", type=int, default=20, help="Anzahl simulierter Einzelzell-Edits")
    args = parser.parse_args()

    results = run_benchmark(rows=args.rows, edits=args.edits)
    edits = args.edits

    print(f"rows={args.rows} edits={edits}")
    for label, total_s in results.items():
        print(f"{label}: {total_s / edits * 1000:.3f} ms/edit")

    speedup_cache_alone = results["full_no_cache"] / results["full_with_cache"]
    speedup_full = results["full_no_cache"] / results["incremental_with_cache"]
    speedup_incremental_alone = results["full_with_cache"] / results["incremental_with_cache"]
    print(f"speedup durch Cache allein (1b):            x{speedup_cache_alone:.1f}")
    print(f"speedup durch Einzelzeilen-Patch allein (1a), bei bereits warmem Cache: x{speedup_incremental_alone:.1f}")
    print(f"speedup gesamt (1a+1b) vs. Zustand vor Item 1:                         x{speedup_full:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
