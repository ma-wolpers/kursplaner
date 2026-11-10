"""Einziger Weg, eine plan-bezogene Schreibaktion des Hauptfensters nachverfolgbar auszuführen.

Früher trugen vier Controller (Aktionen, Spaltentausch, Editor, Umwandlungen) je
eine eigene, leicht abweichende Kopie dieser Brücke vom App-Zustand zum
`TrackedWriteUseCase`. Die Controller delegieren jetzt nur noch hierher; eigene
Nacharbeiten (z. B. Registry-Neuaufbau im Aktions-Controller) bleiben beim Aufrufer.
"""

from __future__ import annotations

import pathlib
from typing import Callable, TypeVar

TResult = TypeVar("TResult")


def run_plan_tracked_write(
    app,
    tracked_write_uc,
    *,
    label: str,
    action: Callable[[], TResult],
    extra_before: list[pathlib.Path] | None = None,
    extra_after: list[pathlib.Path] | None = None,
    extra_after_from_result: Callable[[TResult], list[pathlib.Path]] | None = None,
    include_day_index: int | None = None,
) -> TResult:
    """Führt *action* als einen Undo-Eintrag über Plan, Auswahl und Zusatzpfade aus.

    Ohne geöffneten Plan läuft die Aktion unverfolgt (kein Plan-Snapshot möglich).
    Erfasst werden die Plandatei, die verlinkten Dateien der ausgewählten Spalten
    und *extra_before*; *include_day_index* nimmt zusätzlich eine Spalte auf, die
    gerade bearbeitet, aber nicht ausgewählt ist (Zelleditor).

    Args:
        app: Hauptfenster (``current_table``, ``day_columns``, ``selected_day_indices``).
        tracked_write_uc: `TrackedWriteUseCase`.
        label: Sichtbarer Name im Verlauf.
        action: Die schreibende Aktion.
        extra_before: Zusätzlich vorher zu sichernde Dateien.
        extra_after: Zusätzlich nachher zu prüfende Dateien.
        extra_after_from_result: Leitet weitere Nachher-Pfade aus dem Ergebnis ab.
        include_day_index: Weitere Spaltenposition für den Vorher-Snapshot.

    Returns:
        Das Ergebnis von *action*.
    """
    if app.current_table is None:
        return action()
    selected_day_indices = set(app.selected_day_indices)
    if include_day_index is not None:
        selected_day_indices.add(include_day_index)
    return tracked_write_uc.run_tracked_action(
        label=label,
        action=action,
        table=app.current_table,
        day_columns=app.day_columns,
        selected_day_indices=selected_day_indices,
        extra_before=extra_before,
        extra_after=extra_after,
        extra_after_from_result=extra_after_from_result,
    )
