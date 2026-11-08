"""Dialogablauf „Ablage-Sprosse einer Plan-Zeile zuordnen“ (ohne Tk, Dialoge über `LadderDialogs`).

Zeile wählen → `AssignAblageRungUseCase.check` → Fehler zeigen oder Warnung bestätigen
lassen → `execute`. Alle Regeln und Texte der Warnungen kommen aus Use Case und
Domain (`sequence_ladder_assign`); hier stehen nur Dialogtexte und die Auswahlliste.
Den Abschluss (Fehler, Refresh, Neuladen) macht der Controller über `_finish`,
wie bei jeder anderen Leiter-Aktion.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

from kursplaner.adapters.gui.sequence_ladder_board_mapping import term_label
from kursplaner.core.domain.day_column import DayColumn
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.sequence_ladder_assign import needs_new_unit
from kursplaner.core.domain.topic_sequence_runs import TopicSequenceRun
from kursplaner.core.usecases.assign_ablage_rung_usecase import AssignAblageRungUseCase
from kursplaner.core.usecases.edit_sequence_ladder_usecase import EditSequenceLadderResult
from kursplaner.core.usecases.load_sequence_ladder_usecase import rung_info

TITLE = "Sprosse zuordnen"
SUGGESTION_SUFFIX = " · Vorschlag"
NEW_UNIT_HINT = "leer – es wird eine Unterrichtsdatei angelegt"

ChoiceOptions = Sequence[tuple[str, str, str]]
"""``(key, label, description)`` je angebotener Zeile."""


class AssignDialogs(Protocol):
    """Dialoge des Ablaufs (Teil von `LadderDialogs`)."""

    def choose(self, title: str, prompt: str, options: ChoiceOptions) -> str | None:
        """Eine Option wählen; ``None`` bei Abbruch."""
        ...

    def confirm(self, title: str, message: str) -> bool:
        """Ja/Nein-Rückfrage."""
        ...

    def show_error(self, title: str, message: str) -> None:
        """Fehler zeigen."""
        ...

    def show_info(self, title: str, message: str) -> None:
        """Hinweis zeigen."""
        ...


def target_options(days: Sequence[DayColumn], suggested_row: int | None) -> list[tuple[str, str, str]]:
    """Auswahl-Optionen: Termin-Text (`term_label`), Vorschlag markiert, Beschreibung aus Thema bzw. Hinweis."""
    options = []
    for day in days:
        label = term_label(rung_info(day)) + (SUGGESTION_SUFFIX if day.row_index == suggested_row else "")
        description = NEW_UNIT_HINT if needs_new_unit(day) else day.header_content()
        options.append((str(day.row_index), label, description))
    return options


class AssignRungFlow:
    """Führt den Zuordnen-Dialog für eine Sequenz."""

    def __init__(
        self,
        *,
        usecase: AssignAblageRungUseCase,
        dialogs: AssignDialogs,
        sequence_path: Path,
        table: Callable[[], PlanTableData | None],
    ) -> None:
        """Bindet Use Case, Dialoge, Sequenzdatei und den Zugriff auf die geöffnete Planung."""
        self._usecase, self._dialogs = usecase, dialogs
        self._sequence_path, self._table = sequence_path, table

    def __call__(
        self, rung: int, context: tuple[str, Sequence[TopicSequenceRun], Sequence[DayColumn]]
    ) -> EditSequenceLadderResult | None:
        """Fragt Ziel und ggf. Bestätigung ab und ordnet zu; ``None`` bei Abbruch oder Fehler.

        Args:
            rung: Index der Ablage-Sprosse.
            context: Oberthema, Läufe und Tagesspalten des geöffneten Kurses.
        """
        oberthema, runs, days = context
        table = self._table()
        if table is None:
            return None
        targets = self._usecase.targets(runs=runs, day_columns=days)
        if not targets.days:
            self._dialogs.show_info(TITLE, "Im Plan gibt es keine Zeile, der die Sprosse zugeordnet werden kann.")
            return None
        prompt = f"Welcher Plan-Zeile soll Sprosse {rung + 1} zugeordnet werden?"
        key = self._dialogs.choose(TITLE, prompt, target_options(targets.days, targets.suggested_row))
        if key is None:
            return None
        row = int(key)
        check = self._usecase.check(
            sequence_path=self._sequence_path,
            oberthema=oberthema,
            runs=runs,
            day_columns=days,
            rung=rung,
            target_row=row,
        )
        if check.error:
            self._dialogs.show_error(TITLE, check.error)
            return None
        if check.warnings:
            message = "In der Einheit ändert sich:\n\n" + "\n\n".join(check.warnings) + "\n\nTrotzdem zuordnen?"
            if not self._dialogs.confirm(TITLE, message):
                return None
        return self._usecase.execute(
            table=table,
            sequence_path=self._sequence_path,
            oberthema=oberthema,
            runs=runs,
            day_columns=days,
            rung=rung,
            target_row=row,
        )
