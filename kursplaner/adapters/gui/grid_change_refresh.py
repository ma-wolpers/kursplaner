"""Diff-Refresh des Plan-Grids: aktualisiert nur, was sich nachweislich geändert hat.

Das Grid ist eine reine Funktion aus `app.day_columns`, Feld-Layouts, Auswahl,
`next_unit`-Index und Sequenz-Spannen. Statt nach jedem Schreibvorgang alle
Zellen aller Zeilen neu zu stylen (`GridRenderer.refresh_grid_content`), vergleicht
dieses Modul einen Vorher-Snapshot (vor `_collect_day_columns`) mit dem Nachher-Stand
und patcht genau die Differenz. Das ist exakt per Konstruktion, nicht per
Aufrufer-Behauptung:

- Zellwerte hängen nur von ihrer eigenen `DayColumn` ab (`field_value`); eine
  unveränderte, gleiche `DayColumn` (frozen Dataclass) braucht keinen Patch.
- Zeilenhöhe und -label (`GridRenderer._row_layout`) werden rein aus den Daten
  berechnet; bleibt das Layout eines Felds gleich, bleibt auch seine Zeilenhöhe
  gleich (alle Zellen einer Zeile tragen dieselbe Höhe).
- Ein Spaltenkopf hängt nur an seiner eigenen `DayColumn` (Terminart, Datum, UB,
  datumslos), der Spaltenauswahl und dem `next_unit`-Index; neu gestylt werden die
  geänderten Spalten plus alte und neue `next_unit`-Spalte.
- Sequenz-Spannzellen (Sequenzziel/Leitkompetenzen) baut `refresh_grid_content()` nie
  nach; ändert sich ihre Signatur (Lauf-Grenzen, sichtbare Positionen, Werte), werden
  nur sie ersetzt (`GridRenderer.remount_sequence_fields`). Nur wenn die Sequenzfeld-
  Zeilen ganz entstehen oder verschwinden, verschieben sich alle Zeilen → Neuaufbau.

Fallbacks: anderes Spalten-Tupel oder unpassende Widget-Struktur → bisheriger
`refresh_grid_content()` (der selbst auf einen Neuaufbau zurückfällt).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GridSnapshot:
    """Grid-relevanter Zustand zu einem Zeitpunkt (vor bzw. nach einem Schreibvorgang)."""

    row_indices: tuple[int, ...]
    day_columns: tuple
    row_layouts: tuple[tuple[str, tuple], ...]
    sequence_spans: tuple
    selected_days: frozenset[int]
    selected_cell_day: int | None
    next_unit_index: int | None


def _sequence_spans(app, row_indices: tuple[int, ...]) -> tuple:
    """Signatur der Sequenz-Spannzellen: Thema, sichtbare Positionen, Feldwerte."""
    position = {row_index: idx for idx, row_index in enumerate(row_indices)}
    return tuple(
        (
            view.run.oberthema,
            tuple(position.get(row_index) for row_index in view.run.member_row_indices),
            view.sequenzziel,
            tuple(view.leitkompetenzen),
        )
        for view in (getattr(app, "topic_sequence_plans", None) or ())
    )


def capture_grid_snapshot(app) -> GridSnapshot:
    """Erfasst den aktuellen Grid-relevanten Zustand des Hauptfensters.

    Vor einem Schreibvorgang aufrufen, solange `day_columns` und der Layout-Cache
    noch den angezeigten Stand tragen.
    """
    day_columns = tuple(app.day_columns)
    row_indices = tuple(day.row_index for day in day_columns)
    selected_cell = app.ui_state.selected_cell
    return GridSnapshot(
        row_indices=row_indices,
        day_columns=day_columns,
        row_layouts=tuple(app.grid_renderer.row_layout_snapshot().items()),
        sequence_spans=_sequence_spans(app, row_indices),
        selected_days=frozenset(app.selected_day_indices),
        selected_cell_day=selected_cell.day_index if selected_cell is not None else None,
        next_unit_index=app.grid_renderer.next_unit_index,
    )


def _changed_columns(before: GridSnapshot, after: GridSnapshot) -> list[int]:
    """Spaltenpositionen mit geänderter `DayColumn` oder geänderter Spalten-/Zellauswahl."""
    changed = {idx for idx, (old, new) in enumerate(zip(before.day_columns, after.day_columns)) if old != new}
    changed |= before.selected_days | after.selected_days
    changed |= {day for day in (before.selected_cell_day, after.selected_cell_day) if day is not None}
    return sorted(idx for idx in changed if 0 <= idx < len(after.day_columns))


def refresh_grid_changes(app, before: GridSnapshot) -> None:
    """Bringt das Grid vom Stand *before* auf den aktuellen Stand – mit minimaler Arbeit.

    Endet wie `refresh_grid_content()` mit genau einem `update_action_controls()`.

    Args:
        app: Hauptfenster.
        before: Snapshot aus `capture_grid_snapshot()` vor dem Schreibvorgang.
    """
    if app._is_rebuilding_grid:
        return
    renderer = app.grid_renderer
    after = capture_grid_snapshot(app)
    if after.sequence_spans != before.sequence_spans and app.sequence_fields_visible_var.get():
        if bool(after.sequence_spans) != bool(before.sequence_spans):
            # Sequenzfeld-Zeilen entstehen/verschwinden: alle Feldzeilen rücken um zwei.
            app._rebuild_grid()
            return
        renderer.remount_sequence_fields()
    if not app.header_labels or after.row_indices != before.row_indices or not renderer._grid_structure_matches_state():
        app._refresh_grid_content()
        return

    next_unit_index = app.overview_controller._next_lesson_column_index()
    renderer.set_next_unit_index(next_unit_index)
    old_layouts = dict(before.row_layouts)
    for field_key, layout in after.row_layouts:
        if old_layouts.get(field_key) != layout:
            renderer.update_row_style(field_key)
    changed = _changed_columns(before, after)
    for day_index in changed:
        renderer.update_column_cells(day_index)
    # Ein Kopf hängt nur an seiner `DayColumn`, der Auswahl und dem `next_unit`-Index.
    header_columns = set(changed) | {idx for idx in (before.next_unit_index, next_unit_index) if idx is not None}
    for day_index in sorted(header_columns):
        renderer.apply_header_style(day_index)
    app._on_grid_inner_configure()
    app.action_controller.update_action_controls()
