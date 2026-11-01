"""Merkt sich die Sicht auf den geöffneten Kursplan über ein manuelles Neuladen hinweg.

Die Auswahl wird über die Tabellenzeile (``DayColumn.row_index``) gemerkt, nicht
über die Position in ``day_columns``: Das Neuladen baut diese gefilterte Liste neu
auf, bei geänderten ausgeblendeten Zeilen zeigte eine Position auf eine fremde Spalte.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanViewState:
    """Was der Nutzer im geöffneten Plan zuletzt vor sich hatte.

    Attributes:
        course_iid: Eintrag des Kurses in der Kursliste (Pfad der Plan-Datei).
        selected_row: Tabellenzeile der gewählten Spalte; ``None`` ohne Auswahl.
        selected_field: Feld der gewählten Zelle; ``None``, wenn nur die Spalte gewählt ist.
        scroll_x: Horizontale Scrollposition als Anteil von 0 bis 1.
        scroll_y: Vertikale Scrollposition als Anteil von 0 bis 1.
    """

    course_iid: str
    selected_row: int | None
    selected_field: str | None
    scroll_x: float
    scroll_y: float


def capture_plan_view(app) -> PlanViewState | None:
    """Hält die aktuelle Sicht auf den geöffneten Plan fest.

    Args:
        app: Hauptfenster.

    Returns:
        Der Zustand, oder ``None``, wenn gerade kein Plan offen ist.
    """
    if not app.is_detail_view or app.current_table is None:
        return None

    selected_cell = app.ui_state.selected_cell
    if selected_cell is not None:
        day_index, selected_field = selected_cell.day_index, selected_cell.field_key
    else:
        day_index, selected_field = min(app.selected_day_indices, default=None), None

    selected_row = None
    if day_index is not None and 0 <= day_index < len(app.day_columns):
        selected_row = app.day_columns[day_index].row_index
    return PlanViewState(
        course_iid=str(app.current_table.markdown_path),
        selected_row=selected_row,
        selected_field=selected_field if selected_row is not None else None,
        scroll_x=app.viewport_sync_h.xview_range()[0],
        scroll_y=app.viewport_sync.yview_range()[0],
    )


def restore_plan_view(app, state: PlanViewState) -> None:
    """Stellt Auswahl und Scrollposition im frisch geladenen Plan wieder her.

    Gibt es die gemerkte Spalte nicht mehr oder ist sie jetzt ausgeblendet, bleibt
    der Plan ohne Auswahl. Ist die Zelle nicht mehr bearbeitbar, bleibt die Spalte
    gewählt. Gescrollt wird erst im Leerlauf, wenn das neue Layout steht.

    Args:
        app: Hauptfenster mit dem bereits neu geladenen Plan.
        state: Zustand aus :func:`capture_plan_view`.
    """
    app.ui_state.set_selection_level(app.ui_state.SELECTION_LEVEL_COLUMN)
    for day_index, day in enumerate(app.day_columns):
        if day.row_index == state.selected_row:
            app.selection_controller.set_single_column_selection(day_index)
            if state.selected_field is not None:
                app.selection_controller.set_selected_cell(state.selected_field, day_index)
            break
    app.action_controller.update_action_controls()

    def _restore_scroll() -> None:
        """Setzt beide Achsen; die Viewport-Klassen begrenzen die Werte selbst."""
        app.viewport_sync_h.xview_moveto(state.scroll_x)
        app.viewport_sync.yview_moveto(state.scroll_y)

    app.after_idle(_restore_scroll)
