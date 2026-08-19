"""Regressionstest fuer die fachliche Invariante hinter dem Inhalt/Thema-Ausfall-Bug.

`PlanRegularLessonUseCase.execute_write` ruft `sync_thema_ausfall_to_plan_row`
(schreibt den Themenfolge-Link nach `Thema/Ausfall`) und direkt danach
`LessonTransferUseCase.relink_row_to_stem` (schreibt den Einheiten-Link nach
`Inhalt`) auf. Vor dem Fix ueberschrieb `relink_row_to_stem` wegen eines
hartkodierten Spaltenindex `Thema/Ausfall` mit dem Einheiten-Link. Dieser Test
exerziert den vollstaendigen Write-Flow ueber echte `PlanTableData`- und
`LessonTransferUseCase`-Instanzen (nicht nur Stubs), um genau diese Invariante
end-to-end zu beweisen -- vorher hatte weder `sync_thema_ausfall_to_plan_row`
noch `PlanRegularLessonUseCase.execute_write` noch `relink_row_to_stem` direkte
Testabdeckung.
"""

from pathlib import Path
from typing import Any, cast

from kursplaner.core.domain.plan_table import LessonYamlData, PlanTableData
from kursplaner.core.usecases.lesson_commands_usecase import LessonCommandsUseCase
from kursplaner.core.usecases.lesson_transfer_usecase import LessonTransferUseCase
from kursplaner.core.usecases.plan_regular_lesson_usecase import PlanRegularLessonUseCase
from kursplaner.infrastructure.repositories.plan_table_file_repository import sync_thema_ausfall_to_plan_row


class _LessonRepoStub:
    def __init__(self, initial: dict[Path, dict[str, object]]):
        self.data: dict[Path, dict[str, object]] = {path: dict(values) for path, values in initial.items()}
        self.link_for_row: dict[int, Path] = {}

    def resolve_row_link_path(self, table: PlanTableData, row_index: int) -> Path | None:
        return self.link_for_row.get(row_index)

    def load_lesson_yaml(self, path: Path) -> LessonYamlData:
        return LessonYamlData(lesson_path=path, data=dict(self.data[path]))

    def save_lesson_yaml(self, lesson: LessonYamlData) -> None:
        self.data[lesson.lesson_path] = dict(lesson.data)


class _LessonFileRepoStub:
    pass


class _PlanRepoStub:
    def __init__(self):
        self.save_calls = 0

    def sync_thema_ausfall_to_plan_row(
        self, table: PlanTableData, row_index: int, yaml_data: dict[str, object], group_name: str
    ) -> None:
        sync_thema_ausfall_to_plan_row(table, row_index, yaml_data=yaml_data, group_name=group_name)

    def save_plan_table(self, table: PlanTableData) -> None:
        self.save_calls += 1


def _table() -> PlanTableData:
    return PlanTableData(
        markdown_path=Path("li2.md"),
        headers=["Datum", "Inhalt", "Thema/Ausfall"],
        rows=[["01-09-25", "[[ab12cd]]", "[[li2 Vorheriges Thema]]"]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={"Lerngruppe": "[[li2]]"},
    )


def test_relink_after_oberthema_sync_leaves_themenfolge_link_untouched(tmp_path):
    """Kernszenario: Einheit bereits verlinkt, Oberthema-Eingabe im Dialog gesetzt."""
    lesson_path = tmp_path / "Einheiten" / "ab12cd.md"
    lesson_path.parent.mkdir(parents=True)
    lesson_path.write_text("---\nStundentyp: Unterricht\n---\n", encoding="utf-8")

    lesson_repo = _LessonRepoStub({lesson_path: {"Stundentyp": "Unterricht", "Stundenthema": "Alt"}})
    lesson_repo.link_for_row[0] = lesson_path

    plan_repo = _PlanRepoStub()
    lesson_commands = LessonCommandsUseCase(lesson_repo=cast(Any, lesson_repo))
    lesson_transfer = LessonTransferUseCase(
        lesson_repo=cast(Any, lesson_repo),
        lesson_file_repo=cast(Any, _LessonFileRepoStub()),
    )

    usecase = PlanRegularLessonUseCase(
        lesson_repo=cast(Any, lesson_repo),
        lesson_commands=lesson_commands,
        plan_repo=cast(Any, plan_repo),
        lesson_transfer=lesson_transfer,
        subject_sources=cast(Any, None),
        lesson_context_query=cast(Any, None),
    )

    table = _table()

    result = usecase.execute_write(
        table=table,
        row_index=0,
        topic="Kodierung",
        stunden_raw="2",
        oberthema_input="Kodierung",
        stundenziel_input="",
        was_lzk=False,
        content_before="",
        kompetenzen_refs=[],
        inhalte_refs=[],
        methodik_refs=[],
        allow_create_link=True,
        allow_yaml_save=True,
        allow_sections_save=True,
        allow_plan_save=True,
    )

    assert result.proceed is True

    # Die fachliche Invariante: sync_thema_ausfall_to_plan_row schreibt den
    # Themenfolge-Link, relink_row_to_stem (danach aufgerufen) darf ihn nicht
    # ueberschreiben -- das ist genau der vorher bestehende Bug.
    assert table.thema_ausfall(0) == "[[li2 Kodierung]]"

    # Inhalt traegt jetzt den kanonischen Dataview-Link zur Einheit.
    assert table.inhalt(0) == '`= link("ab12cd", [[ab12cd]].Stundenthema)`'

    assert plan_repo.save_calls == 1


def test_relink_after_creating_new_link_leaves_themenfolge_link_untouched(tmp_path):
    """Zweitszenario: Zeile hat noch keinen Link, execute_write legt ihn im selben Flow an."""
    lesson_dir = tmp_path / "Einheiten"
    lesson_dir.mkdir(parents=True)

    lesson_repo = _LessonRepoStub({})

    def _create_regular_lesson_link(table: PlanTableData, row_index: int, topic: str, default_hours: int) -> Path:
        new_path = lesson_dir / "neu1a.md"
        new_path.write_text("---\nStundentyp: Unterricht\n---\n", encoding="utf-8")
        lesson_repo.data[new_path] = {"Stundentyp": "Unterricht", "Stundenthema": topic}
        lesson_repo.link_for_row[row_index] = new_path
        table.set_inhalt(row_index, "")
        return new_path

    lesson_commands = LessonCommandsUseCase(lesson_repo=cast(Any, lesson_repo))
    lesson_commands.create_regular_lesson_link = _create_regular_lesson_link  # type: ignore[method-assign]

    plan_repo = _PlanRepoStub()
    lesson_transfer = LessonTransferUseCase(
        lesson_repo=cast(Any, lesson_repo),
        lesson_file_repo=cast(Any, _LessonFileRepoStub()),
    )

    usecase = PlanRegularLessonUseCase(
        lesson_repo=cast(Any, lesson_repo),
        lesson_commands=lesson_commands,
        plan_repo=cast(Any, plan_repo),
        lesson_transfer=lesson_transfer,
        subject_sources=cast(Any, None),
        lesson_context_query=cast(Any, None),
    )

    table = _table()
    table.rows[0][1] = ""
    table.rows[0][2] = "[[li2 Vorheriges Thema]]"

    result = usecase.execute_write(
        table=table,
        row_index=0,
        topic="Kodierung",
        stunden_raw="2",
        oberthema_input="Kodierung",
        stundenziel_input="",
        was_lzk=False,
        content_before="",
        kompetenzen_refs=[],
        inhalte_refs=[],
        methodik_refs=[],
        allow_create_link=True,
        allow_yaml_save=True,
        allow_sections_save=True,
        allow_plan_save=True,
    )

    assert result.proceed is True
    assert table.thema_ausfall(0) == "[[li2 Kodierung]]"
    assert table.inhalt(0) == '`= link("neu1a", [[neu1a]].Stundenthema)`'
