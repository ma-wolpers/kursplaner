"""Dialogablauf „Ablage-Sprosse einer Plan-Zeile zuordnen“ (ohne Tk, Dialoge über `LadderDialogs`).

Zeile wählen (chronologische Liste, `AssignAblageRungUseCase.targets`) → bei einer
Einheit ohne Oberthema „einfügen oder übernehmen?“ → `check` → Fehler zeigen bzw.
Verschieben oder Überschreiben bestätigen lassen → `execute`.

Darstellung der Liste (`target_options`): aufeinanderfolgende Termine dieser
Sequenz werden zu **einer** ausgegrauten Zeile zusammengefasst; LZK/Hospitation/
Ausfall stehen ausgegraut mit Grund an ihrer Stelle; der Vorschlag steht an
seiner chronologischen Stelle, hervorgehoben und mit dem Startfokus. Alle Regeln
(Zielart, Verschieben, Warnungen) kommen aus Use Case und Domain; hier stehen nur
Dialogtexte. Den Abschluss (Fehler, Refresh, Neuladen) macht der Controller über
`_finish`, wie bei jeder anderen Leiter-Aktion.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from kursplaner.adapters.gui.sequence_ladder_board_mapping import term_label
from kursplaner.core.domain.day_column import DayColumn
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.sequence_ladder_assign import TargetKind
from kursplaner.core.domain.sequence_ladder_homes import locked_reason, rung_kind
from kursplaner.core.domain.topic_sequence_runs import TopicSequence
from kursplaner.core.usecases.assign_ablage_rung_usecase import (
    AssignAblageRungUseCase,
    AssignCheck,
    AssignTarget,
    AssignTargets,
)
from kursplaner.core.usecases.edit_sequence_ladder_usecase import EditSequenceLadderResult
from kursplaner.core.usecases.load_sequence_ladder_usecase import rung_info

TITLE = "Sprosse zuordnen"
SUGGESTION_PREFIX = "Vorschlag: "
MEMBER_HINT = "gehört schon zu dieser Sequenz"
NEW_UNIT_HINT = "leer – eine Unterrichtsdatei wird angelegt"
INSERT_HINT = "wird eingefügt, die folgenden Einheiten rücken nach hinten"
LOOSE_HINT = "ohne Oberthema – einfügen oder übernehmen"


@dataclass(frozen=True)
class ChoiceItem:
    """Eine Option im Auswahldialog (Tk-frei; `TkLadderDialogs` bildet sie auf bw-gui ab)."""

    key: str
    label: str
    description: str = ""
    enabled: bool = True
    emphasized: bool = False


class AssignDialogs(Protocol):
    """Dialoge des Ablaufs (Teil von `LadderDialogs`)."""

    def choose(self, title: str, prompt: str, options: Sequence[ChoiceItem]) -> str | None:
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


def _day_label(day: DayColumn) -> str:
    return term_label(rung_info(day))


def _members_item(members: Sequence[DayColumn], first_number: int) -> ChoiceItem:
    """Eine ausgegraute Zeile für aufeinanderfolgende Termine dieser Sequenz."""
    last_number = first_number + len(members) - 1
    numbers = f"Sprosse {first_number}" if len(members) == 1 else f"Sprossen {first_number}–{last_number}"
    dates = _day_label(members[0]) if len(members) == 1 else f"{_day_label(members[0])} – {_day_label(members[-1])}"
    return ChoiceItem(f"member:{members[0].row_index}", f"{numbers} · {dates}", MEMBER_HINT, enabled=False)


def _description(target: AssignTarget) -> str:
    day, kind = target.day, target.kind
    if kind is TargetKind.BLOCKED:
        return locked_reason(rung_kind(day))
    if kind is TargetKind.FREE:
        return NEW_UNIT_HINT
    topic = day.header_content()
    if kind is TargetKind.LOOSE_UNIT:
        return f"{topic} – {LOOSE_HINT}" if topic else LOOSE_HINT.capitalize()
    sequence = f"Sequenz „{day.oberthema()}“" if day.oberthema() else ""
    what = " · ".join(part for part in (topic, sequence) if part)
    return f"{what} – {INSERT_HINT}" if what else INSERT_HINT.capitalize()


def target_options(targets: AssignTargets) -> list[ChoiceItem]:
    """Auswahlliste chronologisch: eigene Termine zusammengefasst und ausgegraut, Vorschlag hervorgehoben."""
    items: list[ChoiceItem] = []
    members: list[DayColumn] = []
    number = 1

    def flush() -> None:
        nonlocal number
        if members:
            items.append(_members_item(members, number))
            number += len(members)
            members.clear()

    for target in targets.targets:
        if target.kind is TargetKind.MEMBER:
            members.append(target.day)
            continue
        flush()
        suggested = target.day.row_index == targets.suggested_row
        label = (SUGGESTION_PREFIX if suggested else "") + _day_label(target.day)
        items.append(ChoiceItem(str(target.day.row_index), label, _description(target), target.selectable, suggested))
    flush()
    return items


def shift_message(day: DayColumn, shifted: int) -> str:
    """Rückfrage vor dem Einfügen mit Verschieben."""
    units = "1 Einheit rückt" if shifted == 1 else f"{shifted} Einheiten rücken"
    return f"Ab {_day_label(day)} {units} um einen Termin nach hinten. LZKs bleiben stehen.\n\nEinfügen?"


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
        self, rung: int, context: tuple[TopicSequence, Sequence[DayColumn]]
    ) -> EditSequenceLadderResult | None:
        """Fragt Ziel und ggf. Bestätigung ab und ordnet zu; ``None`` bei Abbruch oder Fehler.

        Args:
            rung: Index der Ablage-Sprosse.
            context: Sequenz und Tagesspalten des geöffneten Kurses (`LadderContext`).
        """
        sequence, days = context
        table = self._table()
        if table is None:
            return None
        targets = self._usecase.targets(sequence=sequence, day_columns=days)
        if not any(target.selectable for target in targets.targets):
            self._dialogs.show_info(TITLE, "Im Plan gibt es keine Zeile, der die Sprosse zugeordnet werden kann.")
            return None
        prompt = f"Wohin soll Sprosse {rung + 1}? Die Liste steht in zeitlicher Reihenfolge."
        key = self._dialogs.choose(TITLE, prompt, target_options(targets))
        target = next((t for t in targets.targets if str(t.day.row_index) == key and t.selectable), None)
        if target is None:
            return None
        request = dict(
            table=table,
            sequence_path=self._sequence_path,
            sequence=sequence,
            day_columns=days,
            rung=rung,
            target_row=target.day.row_index,
        )
        merge = False
        if target.kind is TargetKind.LOOSE_UNIT:
            choice = self._ask_merge(self._usecase.check(**request))
            if choice is None:
                return None
            merge = choice
        check = self._usecase.check(**request, merge=merge)
        if not self._confirmed(check, target):
            return None
        return self._usecase.execute(**request, merge=merge)

    def _ask_merge(self, insert_preview: AssignCheck) -> bool | None:
        """Einheit ohne Oberthema: ``False`` = einfügen, ``True`` = übernehmen, ``None`` = Abbruch."""
        can_insert = not insert_preview.error
        n = insert_preview.shifted
        insert_hint = insert_preview.error or (
            f"Neue Einheit; {n} Einheit(en) rücken um einen Termin nach hinten, LZKs bleiben stehen."
        )
        options = [
            ChoiceItem("insert", "Einfügen", insert_hint, enabled=can_insert, emphasized=can_insert),
            ChoiceItem(
                "merge",
                "In diese Einheit übernehmen",
                "Ziele und Kompetenzen der Einheit werden ersetzt, Material und Ideen angehängt.",
            ),
        ]
        key = self._dialogs.choose(TITLE, "Die Zeile hat schon eine Einheit ohne Oberthema.", options)
        return None if key is None else key == "merge"

    def _confirmed(self, check: AssignCheck, target: AssignTarget) -> bool:
        """Fehler zeigen bzw. Verschieben (andere Sequenz) oder Überschreiben bestätigen lassen."""
        if check.error:
            self._dialogs.show_error(TITLE, check.error)
            return False
        if check.shifted and target.kind is TargetKind.OCCUPIED:
            return self._dialogs.confirm(TITLE, shift_message(target.day, check.shifted))
        if check.warnings:
            message = "In der Einheit ändert sich:\n\n" + "\n\n".join(check.warnings) + "\n\nTrotzdem zuordnen?"
            return self._dialogs.confirm(TITLE, message)
        return True
