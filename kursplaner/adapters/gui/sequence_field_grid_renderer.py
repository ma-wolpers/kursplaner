from __future__ import annotations

from typing import Callable

from bw_gui.runtime import ui
from bw_gui.theming import theme_label_token

from kursplaner.adapters.gui.ui_intents import UiIntent

CreateTextCell = Callable[..., ui.Text]


class SequenceFieldGridRenderer:
    """Rendert die über mehrere Tages-Spalten spannenden Sequenzziel-/Leitkompetenz-Zeilen.

    Ausgelagert aus `GridRenderer`, weil dieses Sub-Feature in sich
    geschlossen ist: es bekommt seinen benötigten Zustand (Zeilenindex,
    Spalten-Mapping, Höhen-Sammelstruktur) explizit übergeben statt frei auf
    den gesamten Grid-Rebuild-Zustand zuzugreifen (siehe
    `docs/ARCHITEKTUR_KERN.md`-Ausnahmetabelle zur Begründung des Splits).
    Zellerzeugung bleibt bei `GridRenderer._create_text_cell`, damit Styling
    (Theme, Zeilenhöhe, Mausrad-Bindung) an genau einer Stelle bleibt; diese
    Klasse bekommt sie nur als Callback injiziert.
    """

    def __init__(self, app, create_text_cell: CreateTextCell) -> None:
        """Initialisiert den Renderer mit App-Kontext und Zellerzeugungs-Callback.

        Args:
            app: Hauptfenster-Kontext (liefert `day_columns`, `topic_sequence_plans`,
                Grid-Container-Widgets, `sequence_field_widgets`).
            create_text_cell: Gebundene `GridRenderer._create_text_cell`-Methode,
                mit der einzelne Zellen im einheitlichen Grid-Stil erzeugt werden.
        """
        self.app = app
        self._create_text_cell = create_text_cell

    def render(
        self,
        row_idx: int,
        day_grid_columns: dict[int, int],
        row_pixel_heights: dict[int, int],
    ) -> int:
        """Rendert die spannenden Sequenzziel-/Leitkompetenz-Zeilen, falls Sequenzen erkannt wurden.

        Wird nur aufgerufen, wenn `sequence_fields_visible_var` aktiv ist. Baut
        pro erkannter Sequenz (`self.app.topic_sequence_plans`) ein oder mehrere
        über die zugehörigen Tages-Spalten spannende Text-Widgets; nicht von
        einer Sequenz abgedeckte, sichtbare Tages-Spalten erhalten eine
        deaktivierte Leerzelle, damit das Rasterbild vollständig bleibt.

        Args:
            row_idx: Nächster freier Grid-Zeilenindex.
            day_grid_columns: Abbildung von `day_index` (Position in
                `self.app.day_columns`) auf die tatsächliche Tk-Grid-Spalte.
            row_pixel_heights: Sammelstruktur für Zeilenhöhen, wird ergänzt.

        Returns:
            Der nächste freie Grid-Zeilenindex nach den Sequenzfeld-Zeilen.
        """
        if not self.app.topic_sequence_plans:
            return row_idx

        row_index_to_grid_col: dict[int, int] = {}
        grid_col_is_cancel: dict[int, bool] = {}
        for day_index, day in enumerate(self.app.day_columns):
            if not isinstance(day, dict):
                continue
            try:
                stable_row_index = int(day.get("row_index", -1))
            except (TypeError, ValueError):
                continue
            grid_col = day_grid_columns.get(day_index)
            if grid_col is not None:
                row_index_to_grid_col[stable_row_index] = grid_col
                grid_col_is_cancel[grid_col] = bool(day.get("is_cancel", False))

        for field_key, label_text in (("Sequenzziel", "Sequenzziel"), ("Leitkompetenz", "Leitkompetenz")):
            row_idx = self._render_one_row(
                row_idx=row_idx,
                field_key=field_key,
                label_text=label_text,
                row_index_to_grid_col=row_index_to_grid_col,
                grid_col_is_cancel=grid_col_is_cancel,
                row_pixel_heights=row_pixel_heights,
            )
        return row_idx

    @staticmethod
    def _run_span(row_index_to_grid_col: dict[int, int], first_row_index: int, last_row_index: int) -> range | None:
        """Berechnet die volle Grid-Spaltenspanne eines Sequenzlaufs.

        `grid_col` wird in `_rebuild_grid()` streng monoton in `row_index`-
        Reihenfolge vergeben (ein Zähler über die geordnete `layout_items`-
        Liste, Marker- wie Tages-Elemente inklusive). Für eine
        zusammenhängende `row_index`-Spanne deckt deshalb
        `[min(grid_cols), max(grid_cols)]` immer die volle Spanne ab —
        inklusive dazwischenliegender Marker-Spalten (ausgeblendete
        Spaltenarten) und übersprungener Ausfall-Zeilen. Kein Fall für
        `compute_contiguous_spans()` (das wäre nur nötig, wenn Mitglieder
        unabhängig voneinander lückenhaft sein könnten).

        Returns:
            `range(min_grid_col, max_grid_col + 1)`, oder `None`, wenn kein
            Mitglied des Laufs eine sichtbare Grid-Spalte hat.
        """
        grid_cols = [
            row_index_to_grid_col[row_index]
            for row_index in range(first_row_index, last_row_index + 1)
            if row_index in row_index_to_grid_col
        ]
        if not grid_cols:
            return None
        return range(min(grid_cols), max(grid_cols) + 1)

    def _render_one_row(
        self,
        *,
        row_idx: int,
        field_key: str,
        label_text: str,
        row_index_to_grid_col: dict[int, int],
        grid_col_is_cancel: dict[int, bool],
        row_pixel_heights: dict[int, int],
    ) -> int:
        """Rendert genau eine Sequenzfeld-Zeile (Sequenzziel ODER Leitkompetenz).

        Ein Lauf spannt sich immer über genau eine zusammenhängende Zelle
        (siehe `_run_span()`) — auch über dazwischenliegende Marker-Spalten
        (ausgeblendete Spaltenarten) hinweg.

        Args:
            grid_col_is_cancel: Abbildung von Tk-Grid-Spalte auf `is_cancel`,
                genutzt um sequenzlose Ausfall-Spalten (Oberthema ringsherum
                weicht ab, keine Überspannung) mit der überall im Grid
                verwendeten Ausfall-Tönung statt neutral-grau darzustellen.
        """
        field_label = ui.Label(
            self.app.fixed_inner,
            text=label_text,
            anchor="w",
            justify="left",
            font=("Segoe UI", 9, "bold"),
            padx=8,
            pady=3,
            relief="solid",
            borderwidth=1,
        )
        theme_label_token(field_label, bg_token="panel_strong")
        field_label.grid(row=row_idx, column=0, sticky="nsew")
        row_pixel_heights[row_idx] = max(row_pixel_heights.get(row_idx, 0), int(field_label.winfo_reqheight()))

        covered_grid_cols: set[int] = set()
        for view in self.app.topic_sequence_plans:
            full_span = self._run_span(row_index_to_grid_col, view.run.first_row_index, view.run.last_row_index)
            if full_span is None:
                continue
            covered_grid_cols.update(full_span)
            value = view.sequenzziel if field_key == "Sequenzziel" else view.leitkompetenz
            widget_key = (field_key, view.run.first_row_index)

            cell = self._create_text_cell(
                self.app.grid_inner,
                value,
                editable=True,
                canceled=False,
                unresolved_link=False,
                height_lines=self.app.collapsed_row_lines,
            )
            cell.grid(row=row_idx, column=full_span.start, columnspan=len(full_span), sticky="nsew")
            self._bind_events(cell, field_key=field_key, first_row_index=view.run.first_row_index)
            self.app.sequence_field_widgets[widget_key] = cell
            row_pixel_heights[row_idx] = max(row_pixel_heights.get(row_idx, 0), int(cell.winfo_reqheight()))

        for grid_col in sorted(set(row_index_to_grid_col.values()) - covered_grid_cols):
            blank_cell = self._create_text_cell(
                self.app.grid_inner,
                "",
                editable=False,
                canceled=grid_col_is_cancel.get(grid_col, False),
                unresolved_link=False,
                height_lines=self.app.collapsed_row_lines,
            )
            blank_cell.grid(row=row_idx, column=grid_col, sticky="nsew")

        return row_idx + 1

    def _bind_events(self, cell: ui.Text, *, field_key: str, first_row_index: int) -> None:
        """Bindet den Editier-Lebenszyklus einer spannenden Sequenzfeld-Zelle.

        Spiegelt das Muster normaler Grid-Zellen (`GRID_CELL_CLICK` /
        `GRID_EDITOR_FOCUS_IN` / `GRID_COMMIT_CELL` / `GRID_EDITOR_FOCUS_OUT`),
        jedoch mit `sequence_field_key`/`sequence_row_index` als Payload, da
        eine Sequenzfeld-Zelle mehrere Tages-Spalten gleichzeitig repräsentiert
        und daher nicht über `(field_key, day_index)` identifizierbar ist.
        """
        cell.bind(
            "<Button-1>",
            lambda _e, fk=field_key, ri=first_row_index: self.app._handle_ui_intent(
                UiIntent.GRID_SEQUENCE_FIELD_CLICK, sequence_field_key=fk, sequence_row_index=ri
            ),
        )
        cell.bind(
            "<FocusIn>",
            lambda _e, fk=field_key, ri=first_row_index: self.app._handle_ui_intent(
                UiIntent.GRID_SEQUENCE_FIELD_FOCUS_IN, sequence_field_key=fk, sequence_row_index=ri
            ),
        )
        cell.bind(
            "<FocusOut>",
            lambda _e, fk=field_key, ri=first_row_index: self.app._handle_ui_intent(
                UiIntent.GRID_COMMIT_SEQUENCE_FIELD, sequence_field_key=fk, sequence_row_index=ri
            ),
        )
        cell.bind(
            "<FocusOut>",
            lambda _e, fk=field_key, ri=first_row_index: self.app._handle_ui_intent(
                UiIntent.GRID_SEQUENCE_FIELD_FOCUS_OUT, sequence_field_key=fk, sequence_row_index=ri
            ),
            add="+",
        )
