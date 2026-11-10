"""Einziger Hauptfenster-Refresh nach Schreibvorgängen: nur neu lesen und zeichnen, was sich änderte.

Drei Einstiege, ein Kern (`_rederive_and_patch`):

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
- `refresh_after_history_step(app, entry)` – nach Undo/Redo. Der Verlaufseintrag kennt
  die zurückgeschriebenen Dateien genau. Liegen alle im geöffneten Kurs (Plandatei,
  verlinkte Einheiten bzw. deren Ordner, Sequenzordner), wird nur die Plandatei neu
  gelesen und nur die betroffenen Zeilen neu abgeleitet; sonst (z. B. eine UB-Datei,
  geänderte Zeilenzahl oder Plan-Metadaten) meldet die Funktion ``False`` und der
  Aufrufer lädt wie bisher alles neu (`reload_keeping_view`).

Das Neuzeichnen läuft immer über den Diff-Refresh
(`grid_change_refresh.refresh_grid_changes`): nur Spalten mit geänderter `DayColumn`
oder Auswahl, Felder mit geändertem Layout, deren Köpfe plus `next_unit`; Kursliste,
Ladedialog und Widget-Neuaufbau entfallen (außer die Sequenzfeld-Zeilen entstehen
oder verschwinden).
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from kursplaner.adapters.gui.grid_change_refresh import capture_grid_snapshot, refresh_grid_changes
from kursplaner.core.domain.sequence_planning import sequence_directory_for_plan
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


def _belongs_to_open_course(path: Path, *, plan_path: Path, linked: set[Path], sequence_dir: Path) -> bool:
    """Ob eine zurückgeschriebene Datei nur den geöffneten Kurs betrifft."""
    lesson_dirs = {link.parent for link in linked}
    return path == plan_path or path in linked or path.parent in lesson_dirs or path.parent == sequence_dir


def refresh_after_history_step(app, entry) -> bool:
    """Zeigt den Stand nach einem Undo/Redo-Schritt gezielt an, wenn das sicher geht.

    Args:
        app: Hauptfenster.
        entry: Angewendeter `CommandEntry` (``None`` bei mehreren Schritten → unbekannt).

    Returns:
        ``True``, wenn gezielt aktualisiert wurde; ``False``, wenn nur ein voller Reload
        sicher ist (kein Plan offen, Datei außerhalb des Kurses, Struktur geändert).
    """
    table = getattr(app, "current_table", None)
    if table is None or entry is None or not entry.deltas:
        return False
    raw = list(getattr(app, "raw_day_columns", ()))
    plan_path = table.markdown_path.resolve()
    linked = {day.link.resolve() for day in raw if isinstance(day.link, Path)}
    written = [delta.path.resolve() for delta in entry.deltas]
    sequence_dir = sequence_directory_for_plan(table).resolve()
    if not all(
        _belongs_to_open_course(path, plan_path=plan_path, linked=linked, sequence_dir=sequence_dir) for path in written
    ):
        return False

    changed = LoadPlanDetailUseCase.rows_linking(raw, written)
    if plan_path in written:
        fresh = app.gui_dependencies.load_plan_detail_usecase.load_table(plan_path)
        if len(fresh.rows) != len(table.rows) or fresh.headers != table.headers or fresh.metadata != table.metadata:
            return False
        changed |= {idx for idx, (old, new) in enumerate(zip(table.rows, fresh.rows)) if old != new}
        app.current_table = fresh
    refresh_after_write(app, changed_rows=changed)
    return True
