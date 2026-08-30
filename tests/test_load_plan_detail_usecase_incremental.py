"""Tests für `LoadPlanDetailUseCase.build_day_columns_incremental` (Perf-Fix Item 1, 2026-08-29).

Kernaussage, die diese Tests beweisen müssen: der Einzelzeilen-Patch liefert
für dieselbe Plattenlage exakt dasselbe Ergebnis wie ein voller
`build_day_columns()`-Aufruf (Korrektheitsgleichheit), liest dabei aber
unveränderte Zeilen NICHT neu von der Platte (bewiesen über Objekt-Identität
mit der vorherigen `DayColumn`-Liste — kein Mock nötig, echte Dateien in
`tmp_path`).
"""

from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.plan_table import LessonYamlData, PlanTableData
from kursplaner.core.usecases.load_plan_detail_usecase import LoadPlanDetailUseCase
from kursplaner.infrastructure.repositories.lesson_repository import FileSystemLessonRepository

_METADATA = {"Lerngruppe": "[[GK blau-1]]"}


def _write_lesson(repo: FileSystemLessonRepository, path: Path, *, stundenthema: str, oberthema: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lesson = LessonYamlData(
        lesson_path=path,
        data={
            "Stundentyp": "Unterricht",
            "Dauer": "2",
            "Stundenthema": stundenthema,
            "Oberthema": oberthema,
            "Stundenziel": "",
            "Kompetenzen": [],
            "Material": [],
        },
    )
    repo.save_lesson_yaml(lesson)


def _build_table(plan_path: Path, links: list[str], metadata: dict | None = None) -> PlanTableData:
    rows = [[f"0{i + 1}-03-26", link, ""] for i, link in enumerate(links)]
    return PlanTableData(
        markdown_path=plan_path,
        headers=["Datum", "Inhalt", "Thema/Ausfall"],
        rows=rows,
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=True,
        metadata=dict(metadata if metadata is not None else _METADATA),
    )


def _setup(tmp_path: Path, num_rows: int = 3) -> tuple[LoadPlanDetailUseCase, PlanTableData, FileSystemLessonRepository, Path]:
    plan_dir = tmp_path / "Mathe Kurs"
    plan_path = plan_dir / "Mathe Kurs.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text("# Kursplan\n", encoding="utf-8")

    repo = FileSystemLessonRepository()
    for i in range(num_rows):
        _write_lesson(repo, plan_dir / "Einheiten" / f"lesson_{i}.md", stundenthema=f"Thema {i}")

    links = [f"[[lesson_{i}]]" for i in range(num_rows)]
    table = _build_table(plan_path, links)
    usecase = LoadPlanDetailUseCase(plan_repo=None, lesson_repo=repo)
    return usecase, table, repo, plan_dir


def test_incremental_matches_full_rebuild_for_single_row_edit(tmp_path):
    usecase, table, repo, plan_dir = _setup(tmp_path)
    baseline = usecase.build_day_columns(table)

    _write_lesson(repo, plan_dir / "Einheiten" / "lesson_1.md", stundenthema="Geänderter Titel")

    incremental = usecase.build_day_columns_incremental(table, baseline, {1})
    ground_truth = usecase.build_day_columns(table)

    assert incremental == ground_truth
    assert incremental[1].yaml.get("Stundenthema") == "Geänderter Titel"


def test_incremental_reuses_unchanged_rows_by_identity_and_rebuilds_only_the_changed_one(tmp_path):
    usecase, table, repo, plan_dir = _setup(tmp_path)
    baseline = usecase.build_day_columns(table)

    _write_lesson(repo, plan_dir / "Einheiten" / "lesson_1.md", stundenthema="Geänderter Titel")

    incremental = usecase.build_day_columns_incremental(table, baseline, {1})

    assert incremental[0] is baseline[0]
    assert incremental[2] is baseline[2]
    assert incremental[1] is not baseline[1]


def test_incremental_with_empty_changed_set_returns_previous_columns_unchanged(tmp_path):
    usecase, table, repo, plan_dir = _setup(tmp_path)
    baseline = usecase.build_day_columns(table)

    result = usecase.build_day_columns_incremental(table, baseline, set())

    assert result == baseline
    assert all(a is b for a, b in zip(result, baseline))


def test_incremental_with_no_previous_state_does_full_rebuild(tmp_path):
    usecase, table, repo, plan_dir = _setup(tmp_path)

    result = usecase.build_day_columns_incremental(table, None, {0})
    ground_truth = usecase.build_day_columns(table)

    assert result == ground_truth


def test_incremental_falls_back_to_full_rebuild_when_row_count_differs(tmp_path):
    usecase, table, repo, plan_dir = _setup(tmp_path, num_rows=3)
    baseline = usecase.build_day_columns(table)

    _write_lesson(repo, plan_dir / "Einheiten" / "lesson_3.md", stundenthema="Vierte Einheit")
    bigger_table = _build_table(table.markdown_path, [f"[[lesson_{i}]]" for i in range(4)])

    result = usecase.build_day_columns_incremental(bigger_table, baseline, {3})
    ground_truth = usecase.build_day_columns(bigger_table)

    assert len(result) == 4
    assert result == ground_truth


def test_incremental_falls_back_to_full_rebuild_when_group_name_changes(tmp_path):
    usecase, table, repo, plan_dir = _setup(tmp_path)
    baseline = usecase.build_day_columns(table)

    changed_group_table = _build_table(
        table.markdown_path,
        [f"[[lesson_{i}]]" for i in range(3)],
        metadata={"Lerngruppe": "[[GK gelb-2]]"},
    )

    result = usecase.build_day_columns_incremental(changed_group_table, baseline, {0})
    ground_truth = usecase.build_day_columns(changed_group_table)

    assert result == ground_truth
    assert all(day.group_name == "GK gelb-2" for day in result)


def test_incremental_rebuilds_all_rows_sharing_the_same_linked_file(tmp_path):
    """Randfall: zwei Zeilen verlinken dieselbe Stunden-Datei (von

    `FileSystemLessonRepository.load_lessons_for_rows()` an anderer Stelle
    bereits als möglich behandelt). Nur Zeile 0 als geändert gemeldet, aber
    Zeile 1 teilt sich dieselbe Datei und muss deshalb ebenfalls neu gebaut
    werden statt aus dem alten Bestand zu kommen.
    """
    plan_dir = tmp_path / "Mathe Kurs"
    plan_path = plan_dir / "Mathe Kurs.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text("# Kursplan\n", encoding="utf-8")

    repo = FileSystemLessonRepository()
    _write_lesson(repo, plan_dir / "Einheiten" / "lesson_shared.md", stundenthema="Geteiltes Thema")
    _write_lesson(repo, plan_dir / "Einheiten" / "lesson_2.md", stundenthema="Thema 2")

    table = _build_table(plan_path, ["[[lesson_shared]]", "[[lesson_shared]]", "[[lesson_2]]"])
    usecase = LoadPlanDetailUseCase(plan_repo=None, lesson_repo=repo)
    baseline = usecase.build_day_columns(table)

    _write_lesson(repo, plan_dir / "Einheiten" / "lesson_shared.md", stundenthema="Aktualisiertes Thema")

    incremental = usecase.build_day_columns_incremental(table, baseline, {0})

    assert incremental[0] is not baseline[0]
    assert incremental[1] is not baseline[1]  # teilt sich die Datei mit Zeile 0
    assert incremental[2] is baseline[2]  # unbeteiligt, wiederverwendet
    assert incremental[0].yaml.get("Stundenthema") == "Aktualisiertes Thema"
    assert incremental[1].yaml.get("Stundenthema") == "Aktualisiertes Thema"
