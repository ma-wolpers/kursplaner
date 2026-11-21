"""Use Case: eine Ablage-Sprosse („??“) einer Plan-Zeile zuordnen – ein Undo-Eintrag (§37).

Zweistufig, damit die GUI vor dem Schreiben fragen kann:

1. `targets` liefert die Zielzeilen **chronologisch** (vom ersten Termin der Sequenz
   bis `FOLLOWING_ROWS` nach dem letzten), je Zeile mit ihrer Art
   (`sequence_ladder_assign.target_kind`) und den Vorschlag (erste wählbare Zeile
   nach dem letzten Termin).
2. `check` liefert einen Fehler oder die Folgen: neue Unterrichtsdatei, Zahl der
   verschobenen Einheiten (Vorschau aus `PlanCommandsUseCase.plan_shift`) bzw. die
   Überschreib-Warnungen beim Übernehmen.
3. `execute` prüft erneut und schreibt in **einem** `run_tracked_file_action`.

Je Zielart genau ein Weg (`_prepare` ist die einzige Entscheidungsstelle):

- `FREE` → Unterrichtsdatei anlegen und verlinken, dann übernehmen.
- `OCCUPIED`, `LOOSE_UNIT` → ab der Zeile alles einen Termin nach hinten
  (LZKs bleiben, `PlanCommandsUseCase.shift_existing_lessons_forward`), dann wie `FREE`.
- `LOOSE_UNIT` mit ``merge=True`` → Inhalt in die vorhandene Einheit übernehmen.

Danach erhält die Einheit das Oberthema der Sequenz und gehört damit zur Sequenz,
egal wo sie steht (`topic_sequence_runs.compute_topic_sequences`). Pfad neuer Dateien
vorab über `LessonRepository.new_lesson_path`, damit Undo/Rollback sie entfernen.
Die Regeln stehen in `sequence_ladder_assign`, die Schreibschritte in
`sequence_ladder_writes`; hier wird nur gelesen, geprüft und orchestriert.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.day_column import DayColumn, day_for_row
from kursplaner.core.domain.plan_row_payload import Move
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.sequence_ladder import LadderRung
from kursplaner.core.domain.sequence_ladder_assign import (
    SELECTABLE_KINDS,
    TargetKind,
    assign_target_error,
    merge_rung_into_unit,
    overwrite_warnings,
    target_kind,
)
from kursplaner.core.domain.sequence_ladder_codec import LadderFormatError
from kursplaner.core.domain.sequence_ladder_homes import AblageHome, UnitContent, UnitHome, term_home
from kursplaner.core.domain.topic_sequence_runs import TopicSequence
from kursplaner.core.ports.repositories import LessonRepository, PlanRepository, SequencePlanRepository
from kursplaner.core.usecases.edit_sequence_ladder_usecase import EditSequenceLadderResult
from kursplaner.core.usecases.lesson_edit_usecase import LessonEditUseCase
from kursplaner.core.usecases.load_sequence_ladder_usecase import sequence_term_days
from kursplaner.core.usecases.plan_commands_usecase import PlanCommandsUseCase
from kursplaner.core.usecases.sequence_ladder_source import LadderSnapshot, SequenceLadderSource
from kursplaner.core.usecases.sequence_ladder_writes import LadderWriters, ladder_writes
from kursplaner.core.usecases.tracked_write_usecase import TrackedWriteUseCase

ASSIGN_LABEL = "Sprosse einer Einheit zuordnen"
"""Name des Schritts im Undo-Verlauf."""

FOLLOWING_ROWS = 6
"""So viele Plan-Zeilen nach dem letzten Termin werden als Ziel angeboten."""

MEMBER_ERROR = "Die Zeile gehört schon zu dieser Sequenz."
NO_FREE_SLOT_ERROR = "Bis zum Planende ist kein Termin frei – die folgenden Einheiten können nicht nach hinten rücken."


@dataclass(frozen=True)
class AssignTarget:
    """Eine angebotene Zielzeile mit ihrer Art (`target_kind`)."""

    day: DayColumn
    kind: TargetKind

    @property
    def selectable(self) -> bool:
        """``True``, wenn die Zeile gewählt werden kann."""
        return self.kind in SELECTABLE_KINDS


@dataclass(frozen=True)
class AssignTargets:
    """Zielzeilen chronologisch; ``suggested_row`` = erste wählbare Zeile nach dem letzten Termin."""

    targets: tuple[AssignTarget, ...]
    suggested_row: int | None


@dataclass(frozen=True)
class AssignCheck:
    """Ergebnis der Prüfung vor dem Schreiben."""

    error: str | None = None
    warnings: tuple[str, ...] = ()
    creates_file: bool = False
    shifted: int = 0


@dataclass(frozen=True)
class _Prepared:
    snapshot: LadderSnapshot
    ablage_index: int
    rung: LadderRung
    day: DayColumn
    unit_path: Path | None
    old: UnitContent
    moves: tuple[Move, ...] | None = None


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
        plan_commands: PlanCommandsUseCase,
        tracked_write: TrackedWriteUseCase,
    ) -> None:
        """Initialisiert den Use Case mit Lesequelle, Schreibwegen, Verschiebeweg und Undo-Orchestrierung."""
        self._source = source
        self._lessons = lesson_repo
        self._lesson_edit = lesson_edit
        self._plans = plan_repo
        self._plan_commands = plan_commands
        self._tracked_write = tracked_write
        self._writers = LadderWriters(lesson_edit=lesson_edit, lessons=lesson_repo, sequences=sequence_plan_repo)

    @staticmethod
    def targets(*, sequence: TopicSequence, day_columns: Sequence[DayColumn]) -> AssignTargets:
        """Zielzeilen chronologisch vom ersten Termin bis `FOLLOWING_ROWS` nach dem letzten."""
        terms = {day.row_index for day in sequence_term_days(day_columns, sequence)}
        days = sorted(day_columns, key=lambda d: d.row_index)
        first = min(terms, default=-1)
        last = max(terms, default=-1)
        after = [day for day in days if day.row_index > last][:FOLLOWING_ROWS]
        shown = [day for day in days if first <= day.row_index <= last] + after
        targets = tuple(AssignTarget(day, target_kind(day, terms)) for day in shown)
        suggested = next((t.day.row_index for t in targets if t.day.row_index > last and t.selectable), None)
        return AssignTargets(targets, suggested)

    def check(
        self,
        *,
        table: PlanTableData,
        sequence_path: Path,
        sequence: TopicSequence,
        day_columns: Sequence[DayColumn],
        rung: int,
        target_row: int,
        merge: bool = False,
    ) -> AssignCheck:
        """Prüft das Zuordnen von Sprosse *rung* zu Zeile *target_row*, ohne zu schreiben.

        *merge* nur bei `LOOSE_UNIT`: Inhalt in die vorhandene Einheit übernehmen statt einzufügen.
        """
        prepared = self._prepare(table, sequence_path, sequence, day_columns, rung, target_row, merge)
        if isinstance(prepared, str):
            return AssignCheck(error=prepared)
        if prepared.unit_path is None:
            return AssignCheck(creates_file=True, shifted=len(prepared.moves or ()))
        return AssignCheck(
            warnings=overwrite_warnings(prepared.rung, prepared.old, prepared.day.oberthema(), sequence.oberthema)
        )

    def execute(
        self,
        *,
        table: PlanTableData,
        sequence_path: Path,
        sequence: TopicSequence,
        day_columns: Sequence[DayColumn],
        rung: int,
        target_row: int,
        merge: bool = False,
    ) -> EditSequenceLadderResult:
        """Ordnet zu (nach erneuter Prüfung); ein Undo-Eintrag über Plan, Einheit und Sequenzdatei.

        Args:
            table: Geöffnete Planung (wird beim Einfügen/Anlegen geändert und gespeichert).
            sequence_path: Sequenzdatei.
            sequence: Die Sequenz; ihr Oberthema bekommt die Ziel-Einheit.
            day_columns: Alle Tagesspalten des Plans.
            rung: Index der Ablage-Sprosse in der Leiter.
            target_row: Tabellenzeile des Ziels.
            merge: Bei `LOOSE_UNIT` übernehmen statt einfügen.
        """
        prepared = self._prepare(table, sequence_path, sequence, day_columns, rung, target_row, merge)
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
        saved_rows = [list(row) for row in table.rows]

        def action() -> None:
            try:
                if creates:
                    if prepared.moves and not self._plan_commands.shift_existing_lessons_forward(table, target_row):
                        raise RuntimeError(NO_FREE_SLOT_ERROR)
                    hours = max(1, prepared.day.stunden())
                    self._lessons.create_linked_lesson_file(table, target_row, "", hours, lesson_path=path)
                    self._plans.save_plan_table(table)
                self._lesson_edit.set_lesson_oberthemen(path, [sequence.oberthema], prepared.day.group_name)
                for write in writes:
                    write.run()
            except Exception:
                table.rows[:] = saved_rows  # Speicherstand wie die zurückgesetzten Dateien
                raise

        paths = [path, sequence_path] + ([table.markdown_path] if creates else [])
        try:
            self._tracked_write.run_tracked_file_action(label=ASSIGN_LABEL, paths=paths, action=action)
        except (OSError, RuntimeError, ValueError) as exc:
            return EditSequenceLadderResult(False, None, f"Nichts gespeichert – alle Dateien sind unverändert: {exc}")
        return EditSequenceLadderResult(True, None, written=tuple(paths))

    def _prepare(
        self,
        table: PlanTableData,
        sequence_path: Path,
        sequence: TopicSequence,
        day_columns: Sequence[DayColumn],
        rung: int,
        target_row: int,
        merge: bool,
    ) -> _Prepared | str:
        """Liest frisch, prüft alle Regeln und entscheidet den Weg; Fehlertext oder vorbereiteter Zustand."""
        terms = sequence_term_days(day_columns, sequence)
        try:
            snapshot = self._source.read(sequence_path, terms)
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
        kind = target_kind(day, {term.row_index for term in terms})
        if kind is TargetKind.MEMBER:
            return MEMBER_ERROR
        if kind is TargetKind.BLOCKED:
            return assign_target_error(day) or MEMBER_ERROR
        index = home.number - 1
        if kind is TargetKind.FREE:
            return _Prepared(snapshot, index, content, day, None, UnitContent())
        if merge and kind is TargetKind.LOOSE_UNIT:
            return self._prepare_merge(snapshot, index, content, day)
        moves = self._plan_commands.plan_shift(table, target_row)
        if moves is None:
            return NO_FREE_SLOT_ERROR
        return _Prepared(snapshot, index, content, day, None, UnitContent(), moves)

    def _prepare_merge(self, snapshot: LadderSnapshot, index: int, content: LadderRung, day: DayColumn):
        """Übernehmen in eine vorhandene Einheit ohne Oberthema (bisheriger Weg mit Überschreib-Warnungen)."""
        target = term_home(day)
        if not isinstance(target, UnitHome):
            return "Die Zeile hat keine Unterrichtsdatei, in die übernommen werden kann."
        try:
            old = self._source.read_unit(target.lesson_path)
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            return f"Die Einheit der Zeile ist nicht lesbar: {exc}"
        return _Prepared(snapshot, index, content, day, target.lesson_path, old)
