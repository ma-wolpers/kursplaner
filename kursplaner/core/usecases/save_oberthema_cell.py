"""Speichern der Oberthema-Zelle im Grid (ausdrückliche Korrektur, kanonische Liste).

Ausgelagert aus `SaveCellValueUseCase`, damit dessen Modul unter dem
Dateigrößen-Limit bleibt. Die Zelle folgt der etablierten Listenfeld-Konvention:
Der Aufrufer parst den Zelltext mit dem bestehenden Listen-Parser (`` | ``,
``;``, Leerzeilen trennen Einträge); Duplikate und Leereinträge entfernt die
zentrale Normalisierung (`normalize_oberthemen`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from kursplaner.core.domain.oberthema_values import OBERTHEMA_INVALID_MARKER, OBERTHEMA_KEY, normalize_oberthemen
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.ports.repositories import PlanRepository
from kursplaner.core.usecases.lesson_edit_usecase import LessonEditUseCase


@dataclass(frozen=True)
class OberthemaCellOutcome:
    """Ergebnis des Oberthema-Zellen-Saves (spiegelt `SaveCellValueResult`)."""

    proceed: bool
    lesson_path: Path | None = None
    error_message: str | None = None


def save_oberthema_cell(
    *,
    plan_repo: PlanRepository,
    lesson_edit: LessonEditUseCase,
    table: PlanTableData,
    row_index: int,
    raw_value: str,
    entries: Sequence[str],
    lesson_path: Path | None,
    allow_yaml_save: bool,
) -> OberthemaCellOutcome | None:
    """Speichert die Oberthema-Zelle einer Einheit.

    * Unveränderter Warnmarker eines ungültigen Werts → nichts wird geschrieben.
    * Einheit ohne Datei → nur die Plantabelle (höchstens ein Thema).
    * Einheit mit Datei → `LessonEditUseCase.set_lesson_oberthemen` als
      ausdrückliche Korrektur (darf einen ungültigen Plattenwert ersetzen).

    Args:
        plan_repo: Port der Planungstabelle.
        lesson_edit: Use Case für YAML-Feldänderungen.
        table: Geladene Planungstabelle.
        row_index: Zeile der Einheit.
        raw_value: Unveränderter Zelltext.
        entries: Bereits geparste Listeneinträge des Zelltexts.
        lesson_path: Verlinkte Stunden-Datei oder ``None``.
        allow_yaml_save: Bestätigung des YAML-Schreibens.

    Returns:
        Ein fertiges Ergebnis, oder ``None``, wenn der allgemeine Ablauf des
        Aufrufers (Abbruch ohne Bestätigung) greifen soll.
    """
    if raw_value.strip() == OBERTHEMA_INVALID_MARKER:
        return OberthemaCellOutcome(proceed=True, lesson_path=lesson_path)

    group_name = str(table.metadata.get("Lerngruppe", ""))
    topics = normalize_oberthemen(entries, group_name)
    if lesson_path is None:
        if len(topics) > 1:
            return OberthemaCellOutcome(
                proceed=False, error_message="Eine Unterrichtseinheit kann nur ein Oberthema haben."
            )
        plan_repo.sync_thema_ausfall_to_plan_row(
            table,
            row_index,
            yaml_data={"Stundentyp": "Unterricht", OBERTHEMA_KEY: topics},
            group_name=group_name,
        )
        plan_repo.save_plan_table(table)
        return OberthemaCellOutcome(proceed=True)

    if not allow_yaml_save:
        return None
    try:
        lesson_edit.set_lesson_oberthemen(lesson_path, topics, group_name)
    except RuntimeError as exc:
        return OberthemaCellOutcome(proceed=False, error_message=str(exc))
    return OberthemaCellOutcome(proceed=True, lesson_path=lesson_path)
