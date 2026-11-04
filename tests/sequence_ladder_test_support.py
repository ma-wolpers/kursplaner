"""Synthetische Sequenz für Leiter-Tests: echte Einheiten-Dateien, Termine, Sequenzdatei, Undo-Kette.

Nur erfundene Daten in ``tmp_path``. Aufbau einer Sequenz „Brüche“ mit den
Terminen aus *kinds* (``"U"`` Unterricht ``.md``, ``"E"`` Unterricht ``.ebw``,
``"L"`` LZK, ``"A"`` Ausfall), chronologisch = Sprossen von unten.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from day_column_factory import make_day_column
from test_sequence_plan_repository import _build_table

from kursplaner.core.domain.day_column import DayColumn
from kursplaner.core.domain.topic_sequence_runs import TopicSequenceRun
from kursplaner.core.usecases.command_executor_usecase import CommandExecutorUseCase
from kursplaner.core.usecases.edit_sequence_ladder_usecase import EditSequenceLadderUseCase
from kursplaner.core.usecases.history_usecase import HistoryUseCase
from kursplaner.core.usecases.lesson_edit_usecase import LessonEditUseCase
from kursplaner.core.usecases.load_sequence_ladder_usecase import LoadSequenceLadderUseCase
from kursplaner.core.usecases.sequence_ladder_source import SequenceLadderSource
from kursplaner.core.usecases.tracked_write_usecase import TrackedWriteUseCase
from kursplaner.infrastructure.repositories.command_repository import FileSystemCommandRepository
from kursplaner.infrastructure.repositories.lesson_repository import FileSystemLessonRepository
from kursplaner.infrastructure.repositories.sequence_plan_repository import FileSystemSequencePlanRepository

EBW_MARKER = "document_type: kurzentwurf"


def write_unit(
    path: Path,
    *,
    ziel: str = "",
    teilziele: tuple[str, ...] = (),
    kompetenzen: tuple[str, ...] = (),
    body: str = "# Verlauf\n\nEinstieg\n",
) -> None:
    """Schreibt eine Unterrichts-Einheit über den echten Kursplaner-Schreibweg (``.ebw`` mit Marker)."""
    marker = f"{EBW_MARKER}\n" if path.suffix == ".ebw" else ""
    minimal = f"Stundentyp: Unterricht\nDauer: 2\nStundenthema: {path.stem}\n{marker}"
    path.write_text(f"---\n{minimal}---\n\n{body}", encoding="utf-8")
    fields = {
        "Oberthema": "Brüche",
        "Stundenziel": ziel,
        "Teilziele": list(teilziele),
        "Kompetenzen": list(kompetenzen),
    }
    LessonEditUseCase(FileSystemLessonRepository()).set_lesson_fields(path, fields)


@dataclass
class LadderEnv:
    """Alles für einen Leiter-Test."""

    sequence_path: Path
    units: list[Path]
    days: list[DayColumn]
    runs: list[TopicSequenceRun]
    history: HistoryUseCase
    sequence_repo: FileSystemSequencePlanRepository
    load: LoadSequenceLadderUseCase
    edit: EditSequenceLadderUseCase

    @property
    def context(self) -> tuple[str, list[TopicSequenceRun], list[DayColumn]]:
        """Controller-Kontext (Oberthema, Läufe, Tagesspalten)."""
        return "Brüche", self.runs, self.days

    def execute(self, operation):
        """Leiter-Operation über den echten Edit-Use-Case."""
        return self.edit.execute(
            sequence_path=self.sequence_path, runs=self.runs, day_columns=self.days, operation=operation
        )

    def view(self):
        """Ansicht über den echten Lade-Use-Case."""
        return self.load.execute(
            sequence_path=self.sequence_path, oberthema="Brüche", runs=self.runs, day_columns=self.days
        )


def make_ladder_env(tmp_path: Path, kinds: str = "", **unit_contents: dict) -> LadderEnv:
    """Baut die Sequenz; *unit_contents* je Einheit ``u<n>`` (n = Termin-Index) als `unit_text`-Argumente."""
    plan_dir = tmp_path / "M GK test-1 26-2"
    plan_dir.mkdir()
    plan_path = plan_dir / "M GK test-1 26-2.md"
    plan_path.write_text("# Kursplan\n", encoding="utf-8")
    einheiten = plan_dir / "Einheiten"
    einheiten.mkdir()
    sequence_repo = FileSystemSequencePlanRepository()
    sequence_path = sequence_repo.ensure_sequence_document(table=_build_table(plan_path), sequence_name="Brüche")
    units: list[Path] = []
    days: list[DayColumn] = []
    for index, kind in enumerate(kinds):
        datum = f"{index + 2:02d}-11-26"
        if kind == "A":
            days.append(make_day_column(row_index=index, datum=datum, thema_ausfall="X Krank"))
            continue
        stem = f"u{index}"
        if kind == "L":
            path = einheiten / f"{stem}.md"
            path.write_text("---\nStundentyp: LZK\nDauer: 2\nStundenthema: Test\nOberthema: Brüche\n---\n", "utf-8")
            yaml = {"Stundentyp": "LZK", "Oberthema": "Brüche"}
        else:
            path = einheiten / f"{stem}{'.ebw' if kind == 'E' else '.md'}"
            write_unit(path, **unit_contents.get(stem, {}))
            yaml = {"Stundentyp": "Unterricht", "Oberthema": "Brüche"}
            units.append(path)
        days.append(make_day_column(row_index=index, datum=datum, inhalt=f"[[{stem}]]", link=path, yaml=yaml))
    runs = [TopicSequenceRun("Brüche", tuple(day.row_index for day in days if not day.is_cancel()))] if days else []
    lesson_repo = FileSystemLessonRepository()
    history = HistoryUseCase(CommandExecutorUseCase(command_repo=FileSystemCommandRepository()))
    source = SequenceLadderSource(sequence_plan_repo=sequence_repo, lesson_repo=lesson_repo)
    edit = EditSequenceLadderUseCase(
        source=source,
        sequence_plan_repo=sequence_repo,
        lesson_repo=lesson_repo,
        lesson_edit=LessonEditUseCase(lesson_repo=lesson_repo),
        tracked_write=TrackedWriteUseCase(history),
    )
    return LadderEnv(sequence_path, units, days, runs, history, sequence_repo, LoadSequenceLadderUseCase(source), edit)
