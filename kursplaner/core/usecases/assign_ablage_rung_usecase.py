"""Use Case: eine Ablage-Sprosse („??“) einer Plan-Zeile zuordnen – ein Undo-Eintrag (§37).

Zweistufig, damit die GUI vor dem Schreiben warnen kann:

1. `check` liefert einen Fehler (LZK/Hospitation/Ausfall, keine Ablage-Sprosse,
   leere Sprosse, Einheit nicht lesbar) oder die Warnungen, was überschrieben
   wird (`sequence_ladder_assign.overwrite_warnings`), und ob eine
   Unterrichtsdatei angelegt wird.
2. `execute` prüft erneut und schreibt in **einem** `run_tracked_file_action`:
   ggf. neue Unterrichtsdatei + Plan-Link (Pfad vorab über
   `LessonRepository.new_lesson_path`, damit Undo/Rollback sie wieder entfernen),
   Oberthema der Sequenz (`LessonEditUseCase.set_lesson_oberthemen`), Ziele,
   Kompetenzen, Ideen und die Ablage ohne die Sprosse (`ladder_writes`).

Die Regeln stehen in `sequence_ladder_assign`, die Schreibschritte in
`sequence_ladder_writes`; hier wird nur gelesen, geprüft und orchestriert.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.day_column import DayColumn, day_for_row
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.sequence_ladder import LadderRung
from kursplaner.core.domain.sequence_ladder_assign import (
    assign_target_error,
    merge_rung_into_unit,
    overwrite_warnings,
)
from kursplaner.core.domain.sequence_ladder_codec import LadderFormatError
from kursplaner.core.domain.sequence_ladder_homes import AblageHome, UnitContent, UnitHome, term_home
from kursplaner.core.domain.topic_sequence_runs import TopicSequenceRun
from kursplaner.core.ports.repositories import LessonRepository, PlanRepository, SequencePlanRepository
from kursplaner.core.usecases.edit_sequence_ladder_usecase import EditSequenceLadderResult
from kursplaner.core.usecases.lesson_edit_usecase import LessonEditUseCase
from kursplaner.core.usecases.load_sequence_ladder_usecase import sequence_term_days
from kursplaner.core.usecases.sequence_ladder_source import LadderSnapshot, SequenceLadderSource
from kursplaner.core.usecases.sequence_ladder_writes import LadderWriters, ladder_writes
from kursplaner.core.usecases.tracked_write_usecase import TrackedWriteUseCase

ASSIGN_LABEL = "Sprosse einer Einheit zuordnen"
"""Name des Schritts im Undo-Verlauf."""

FOLLOWING_ROWS = 6
"""So viele Plan-Zeilen nach dem letzten Termin werden als Ziel angeboten."""


@dataclass(frozen=True)
class AssignTargets:
    """Angebotene Zielzeilen: der Vorschlag (erste Zeile nach der Sequenz) zuerst."""

    days: tuple[DayColumn, ...]
    suggested_row: int | None


@dataclass(frozen=True)
class AssignCheck:
    """Ergebnis der Prüfung vor dem Schreiben."""

    error: str | None = None
    warnings: tuple[str, ...] = ()
    creates_file: bool = False


@dataclass(frozen=True)
class _Prepared:
    snapshot: LadderSnapshot
    ablage_index: int
    rung: LadderRung
    day: DayColumn
    unit_path: Path | None
    old: UnitContent


class AssignAblageRungUseCase:
    """Prüft und schreibt das Zuordnen einer Ablage-Sprosse."""

    def __init__(
        self,
        *,
        source: SequenceLadderSource,
        sequence_plan_repo: SequencePlanRepository,
        lesson_repo: LessonRepository,
        lesson_edit: LessonEditUseCase,
        plan_repo: PlanRepository,
        tracked_write: TrackedWriteUseCase,
    ) -> None:
        """Initialisiert den Use Case mit Lesequelle, Schreibwegen und Undo-Orchestrierung."""
        self._source = source
        self._lessons = lesson_repo
        self._lesson_edit = lesson_edit
        self._plans = plan_repo
        self._tracked_write = tracked_write
        self._writers = LadderWriters(lesson_edit=lesson_edit, lessons=lesson_repo, sequences=sequence_plan_repo)

    @staticmethod
    def targets(*, runs: Sequence[TopicSequenceRun], day_columns: Sequence[DayColumn]) -> AssignTargets:
        """Zielzeilen: Vorschlag, dann die Termine der Sequenz, dann die übrigen Folgezeilen."""
        terms = sequence_term_days(day_columns, runs)
        last = max((day.row_index for day in terms), default=-1)
        following = sorted((d for d in day_columns if d.row_index > last), key=lambda d: d.row_index)
        following = following[:FOLLOWING_ROWS]
        suggested = following[0] if following else None
        ordered = ([suggested] if suggested else []) + list(terms) + following[1:]
        return AssignTargets(tuple(ordered), suggested.row_index if suggested else None)

    def check(
        self,
        *,
        sequence_path: Path,
        oberthema: str,
        runs: Sequence[TopicSequenceRun],
        day_columns: Sequence[DayColumn],
        rung: int,
        target_row: int,
    ) -> AssignCheck:
        """Prüft das Zuordnen von Sprosse *rung* zu Zeile *target_row*, ohne zu schreiben."""
        prepared = self._prepare(sequence_path, runs, day_columns, rung, target_row)
        if isinstance(prepared, str):
            return AssignCheck(error=prepared)
        if prepared.unit_path is None:
            return AssignCheck(creates_file=True)
        return AssignCheck(
            warnings=overwrite_warnings(prepared.rung, prepared.old, prepared.day.oberthema(), oberthema)
        )

    def execute(
        self,
        *,
        table: PlanTableData,
        sequence_path: Path,
        oberthema: str,
        runs: Sequence[TopicSequenceRun],
        day_columns: Sequence[DayColumn],
        rung: int,
        target_row: int,
    ) -> EditSequenceLadderResult:
        """Ordnet zu (nach erneuter Prüfung); ein Undo-Eintrag über Plan, Einheit und Sequenzdatei.

        Args:
            table: Geöffnete Planung (wird beim Anlegen einer Einheit verlinkt und gespeichert).
            sequence_path: Sequenzdatei.
            oberthema: Oberthema der Sequenz (bekommt die Ziel-Einheit).
            runs: Alle Läufe mit diesem Pfad.
            day_columns: Alle Tagesspalten des Plans.
            rung: Index der Ablage-Sprosse in der Leiter.
            target_row: Tabellenzeile des Ziels.
        """
        prepared = self._prepare(sequence_path, runs, day_columns, rung, target_row)
        if isinstance(prepared, str):
            return EditSequenceLadderResult(False, None, prepared)
        creates = prepared.unit_path is None
        path = prepared.unit_path or self._lessons.new_lesson_path(table)
        old_ablage = prepared.snapshot.ablage.trimmed()
        writes = ladder_writes(
            self._writers,
            sequence_path=sequence_path,
            old_units={path: prepared.old},
            new_units={path: merge_rung_into_unit(prepared.rung, prepared.old)},
            old_ablage=old_ablage,
            new_ablage=old_ablage.without_rung(prepared.ablage_index).trimmed(),
        )
        saved_row = list(table.rows[target_row])

        def action() -> None:
            try:
                if creates:
                    hours = max(1, prepared.day.stunden())
                    self._lessons.create_linked_lesson_file(table, target_row, "", hours, lesson_path=path)
                    self._plans.save_plan_table(table)
                self._lesson_edit.set_lesson_oberthemen(path, [oberthema], prepared.day.group_name)
                for write in writes:
                    write.run()
            except Exception:
                table.rows[target_row][:] = saved_row  # Speicherstand wie die zurückgesetzte Datei
                raise

        paths = [path, sequence_path] + ([table.markdown_path] if creates else [])
        try:
            self._tracked_write.run_tracked_file_action(label=ASSIGN_LABEL, paths=paths, action=action)
        except (OSError, RuntimeError, ValueError) as exc:
            return EditSequenceLadderResult(False, None, f"Nichts gespeichert – alle Dateien sind unverändert: {exc}")
        return EditSequenceLadderResult(True, None, written=tuple(paths))

    def _prepare(
        self,
        sequence_path: Path,
        runs: Sequence[TopicSequenceRun],
        day_columns: Sequence[DayColumn],
        rung: int,
        target_row: int,
    ) -> _Prepared | str:
        """Liest frisch und prüft alle Regeln; Fehlertext oder vorbereiteter Zustand."""
        try:
            snapshot = self._source.read(sequence_path, sequence_term_days(day_columns, runs))
        except (LadderFormatError, OSError) as exc:
            return str(exc)
        home = snapshot.homes.home(rung)
        if not isinstance(home, AblageHome):
            return "Nur Sprossen ohne Termin („??“) können einer Einheit zugeordnet werden."
        content = snapshot.ladder.rung(rung)
        if content.is_empty:
            return "Die Sprosse ist leer – es gibt nichts zuzuordnen."
        day = day_for_row(day_columns, target_row)
        if day is None:
            return "Die gewählte Zeile gibt es im Plan nicht (mehr)."
        error = assign_target_error(day)
        if error:
            return error
        target = term_home(day)
        if not isinstance(target, UnitHome):
            return _Prepared(snapshot, home.number - 1, content, day, None, UnitContent())
        try:
            old = self._source.read_unit(target.lesson_path)
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return f"Die Einheit der Zeile ist nicht lesbar: {exc}"
        return _Prepared(snapshot, home.number - 1, content, day, target.lesson_path, old)
