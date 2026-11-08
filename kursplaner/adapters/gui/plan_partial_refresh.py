"""Gezielter Hauptfenster-Refresh nach Schreibvorgängen außerhalb des Grids (Sequenzleiter).

Früher lud jede Leiter-Aktion (Verschieben, Strg+↑/↓, Umbenennen, …) das ganze
Hauptfenster neu wie Strg+R: alle Kurspläne zweimal parsen, Ladedialog, kompletter
Plan-Reload und Neuaufbau aller Grid-Widgets. Hier wird nur neu gelesen, was die
Aktion geschrieben hat:

1. Zeilen, deren Einheit unter den geschriebenen Dateien ist
   (`LoadPlanDetailUseCase.rows_linking` – dieselbe Vergleichsregel wie der
   inkrementelle Neuaufbau, der Zeilen mit derselben Datei selbst ergänzt).
2. `app._collect_day_columns(rows)` – inkrementell; danach laufen Sequenz-Sync und
   `_publish_sequence_plans`, d. h. eine offene Leiter lädt genau einmal neu.
3. `app._refresh_grid_content()` – Zellen und Köpfe aktualisieren, kein Widget-Neuaufbau.

Trifft keine Zeile (z. B. nur die Ablage der Sequenzdatei geändert), bleibt das
Grid unangetastet; der Aufrufer lädt die Leiter dann selbst.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from kursplaner.core.usecases.load_plan_detail_usecase import LoadPlanDetailUseCase


def refresh_after_files_written(app, paths: Iterable[Path]) -> None:
    """Aktualisiert das Hauptfenster nur für die Zeilen der geschriebenen Dateien.

    Args:
        app: Hauptfenster (braucht ``current_table``, ``raw_day_columns``,
            ``_collect_day_columns``, ``_refresh_grid_content`` und ``action_controller``).
        paths: Von der Aktion geschriebene Dateien (Einheiten und/oder Sequenzdatei).
    """
    rows = LoadPlanDetailUseCase.rows_linking(list(getattr(app, "raw_day_columns", ())), paths)
    if app.current_table is not None and rows:
        app._collect_day_columns(rows)
        app._refresh_grid_content()  # aktualisiert auch die Aktionsknöpfe (Undo)
        return
    app.action_controller.update_action_controls()
