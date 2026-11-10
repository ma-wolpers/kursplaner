"""Einziger Hauptfenster-Refresh nach Schreibvorgängen: nur neu lesen und zeichnen, was sich änderte.

Zwei Einstiege, ein Kern (`_rederive_and_patch`):

- `refresh_after_write(app, selected_index=, changed_rows=)` – nach Grid-/Toolbar-Aktionen
  (Spaltentausch, UB, Einfügen, Leeren, Umbenennen, Umwandlungen, Verlängern, …).
  Früher trugen drei Controller je eine Kopie davon, die stets den ganzen Plan neu
  einlas und jede Zelle neu stylte. *changed_rows* (Tabellenzeilen, ``DayColumn.row_index``)
  übergibt nur, wer die geänderten Zeilen beweisbar kennt (Spaltentausch: genau die
  zwei getauschten Planzeilen, keine Datei geschrieben); sonst ``None`` = voll einlesen.
- `refresh_after_files_written(app, paths)` – nach Schreibvorgängen außerhalb des Grids
  (Sequenzleiter). Zeilen, deren Einheit unter den geschriebenen Dateien ist
  (`LoadPlanDetailUseCase.rows_linking`), werden inkrementell neu gelesen; ist die
  Plandatei selbst dabei, werden alle Tagesspalten aus der – bereits geänderten –
  Tabelle im Speicher neu abgeleitet. Trifft keine Zeile, bleibt das Grid unangetastet.

Das Neuzeichnen läuft in beiden Fällen über den Diff-Refresh
(`grid_change_refresh.refresh_grid_changes`): nur Spalten mit geänderter `DayColumn`
oder Auswahl, Felder mit geändertem Layout, alle Köpfe; Kursliste, Ladedialog und
Widget-Neuaufbau entfallen (außer die Sequenz-Spannen ändern sich).
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from kursplaner.adapters.gui.grid_change_refresh import capture_grid_snapshot, refresh_grid_changes
from kursplaner.core.usecases.load_plan_detail_usecase import LoadPlanDetailUseCase


def _rederive_and_patch(app, changed_rows: set[int] | None, *, selected_index: int | None = None) -> None:
    """Leitet `day_columns` neu ab (voll oder für *changed_rows*) und patcht das Grid per Diff."""
    before = capture_grid_snapshot(app)
    app._collect_day_columns(changed_rows)
    if isinstance(selected_index, int) and 0 <= selected_index < len(app.day_columns):
        app.selected_day_indices = {selected_index}
        app._update_selected_column_label()
    refresh_grid_changes(app, before)


def refresh_after_write(app, *, selected_index: int | None = None, changed_rows: set[int] | None = None) -> None:
    """Aktualisiert Hauptfenster und Kurskennzahlen nach einer plan-bezogenen Schreibaktion.

    Args:
        app: Hauptfenster.
        selected_index: Spaltenposition, die danach allein ausgewählt sein soll.
        changed_rows: Beweisbar einzige geänderte Tabellenzeilen; ``None`` = unbekannt.
    """
    _rederive_and_patch(app, changed_rows, selected_index=selected_index)
    app._update_selected_lesson_metrics()


def refresh_after_files_written(app, paths: Iterable[Path]) -> None:
    """Aktualisiert das Hauptfenster nur für die Zeilen der geschriebenen Dateien.

    Args:
        app: Hauptfenster (braucht ``current_table``, ``raw_day_columns``,
            ``_collect_day_columns`` und ``action_controller``).
        paths: Von der Aktion geschriebene Dateien (Einheiten und/oder Sequenzdatei).
    """
    paths = list(paths)
    table = app.current_table
    if table is not None and table.markdown_path.resolve() in {path.resolve() for path in paths}:
        _rederive_and_patch(app, None)
        return
    rows = LoadPlanDetailUseCase.rows_linking(list(getattr(app, "raw_day_columns", ())), paths)
    if table is not None and rows:
        _rederive_and_patch(app, rows)  # aktualisiert auch die Aktionsknöpfe (Undo)
        return
    app.action_controller.update_action_controls()
