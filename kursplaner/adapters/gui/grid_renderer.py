from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path
from kursplaner.core.domain.day_column import DayColumn

ensure_bw_gui_on_path()
from bw_gui.runtime import ui
from datetime import datetime

from kursplaner.adapters.gui.help_catalog import LESSON_BUILDER_HELP
from bw_gui.theming import (
    canvas_fill,
    canvas_tinted_fill,
    theme_canvas,
    theme_label_tinted,
    theme_label_token,
    theme_text,
    theme_text_tinted,
    theme_widget_border,
)

from kursplaner.adapters.gui.hover_tooltip import HoverTooltip
from kursplaner.adapters.gui.sequence_field_grid_renderer import (
    SEQUENCE_FIELD_ROW_ORDER,
    SequenceFieldGridRenderer,
    compute_row_index_to_grid_col,
)
from kursplaner.adapters.gui.ui_intents import UiIntent
from kursplaner.adapters.gui.ui_theme import HOSPITATION_SEED


class GridRenderer:
    """Render-Komponente für die tabellarische Planansicht.

    Verantwortet ausschließlich visuelle Aufbereitung und Grid-Interaktion,
    keine Persistenz- oder Fachentscheidungslogik.
    """

    def __init__(self, app):
        """Speichert die App-Referenz als Render- und Event-Kontext."""
        self.app = app
        self._field_help_tooltips: list[HoverTooltip] = []
        self._marker_widgets: list[ui.Canvas] = []
        self._marker_kinds_by_widget: dict[int, tuple[str, ...]] = {}
        self._marker_column_width = 12
        self._row_layout_cache: dict[str, tuple[int, bool, bool, str]] = {}
        self._sequence_field_renderer = SequenceFieldGridRenderer(app, self._create_text_cell)
        self._zoom_rebuild_after_id: str | None = None
        self._next_unit_index: int | None = None

    def set_next_unit_index(self, value: int | None) -> None:
        """Setzt den Spaltenindex der 'nächsten Einheit' für die Header-Markierung.

        Reiner Datenzugriff — der Renderer berechnet diesen Wert nicht selbst
        (keine Zeit-/Policy-Logik, kein Controller-Aufruf). Aufrufer (die
        `_rebuild_grid`/`_refresh_grid_content`-Wrapper in `main_window.py`)
        berechnen ihn einmal pro Render-Durchlauf über
        `overview_controller._next_lesson_column_index()`.
        """
        self._next_unit_index = value

    def _apply_marker_kind_fill(self, canvas: ui.Canvas, item_id: int, kind: str) -> None:
        """Wendet Markerfarbe per canvas-Primitive auf ein Rechteck-Item an."""
        normalized = str(kind).strip().lower()
        if normalized == "ausfall":
            canvas_tinted_fill(canvas, item_id, color_tint="warning_soft", degree=0.72, base_token="panel_strong")
        elif normalized == "lzk":
            canvas_tinted_fill(canvas, item_id, color_tint="success_soft", degree=0.72, base_token="panel_strong")
        elif normalized == "hospitation":
            canvas_tinted_fill(canvas, item_id, color_tint=HOSPITATION_SEED, degree=0.38, base_token="panel_strong")
        else:
            canvas_fill(canvas, item_id, token="panel_strong")

    def _draw_marker_canvas(self, marker: ui.Canvas, kinds: tuple[str, ...]) -> None:
        """Zeichnet farbige Marker-Segmente je ausgeblendeter Spaltenart."""
        marker.delete("all")
        theme_canvas(marker)
        marker.configure(highlightthickness=0)
        marker_width = max(1, int(marker.winfo_width()))
        marker_height = max(1, int(marker.winfo_height()))
        normalized = tuple(str(kind).strip() for kind in kinds if str(kind).strip())
        if not normalized:
            return

        segment_width = max(1, marker_width // len(normalized))
        x0 = 0
        for index, kind in enumerate(normalized):
            x1 = marker_width if index == (len(normalized) - 1) else min(marker_width, x0 + segment_width)
            rect = marker.create_rectangle(x0, 0, x1, marker_height, outline="")
            self._apply_marker_kind_fill(marker, rect, kind)
            x0 = x1

    def _display_layout_items(self) -> list[dict[str, object]]:
        """Liefert die Darstellungsreihenfolge aus sichtbaren Tagen und Marker-Lücken."""
        items: list[dict[str, object]] = []
        for day_index, day in enumerate(self.app.day_columns):
            hidden_before = day.hidden_kinds_before if isinstance(day, DayColumn) else ()
            if isinstance(hidden_before, (tuple, list)) and hidden_before:
                items.append({"type": "marker", "kinds": tuple(str(kind) for kind in hidden_before)})
            items.append({"type": "day", "day_index": day_index})
        return items

    def _field_help_text(self, field_key: str) -> str:
        if field_key == "Stundenziel":
            return LESSON_BUILDER_HELP.get("stundenziel", "")
        if field_key == "Teilziele":
            return LESSON_BUILDER_HELP.get("teilziele", "")
        if field_key == "Sonderziele":
            return LESSON_BUILDER_HELP.get("sonderziele", "")
        return ""

    def _header_visual_state(self, day_index: int) -> tuple[str, str]:
        """Liefert Header-Text und Spalten-Zustandsschlüssel für eine Tages-Spalte.

        Returns:
            (date_text, col_type) — col_type ∈ {'normal', 'cancel', 'hospitation',
            'lzk', 'unresolved', 'next_unit'}. Pass both to ``_apply_header_color``.

        Die "nächste Einheit"-Markierung (persistente, spaltenkopf-only
        Kennzeichnung, unabhängig von der aktuellen Zellauswahl und vom
        UB-/Datumslos-Rahmen aus ``_apply_ub_border``) nutzt zwei getrennte,
        nie kollidierende Kanäle: einen eigenen Hintergrund-`col_type`
        ``"next_unit"`` für den häufigsten Fall (keine speziellere Einfärbung
        aktiv), und ein angehängtes Glyph im Header-Text als Fallback, wenn
        der Hintergrund bereits durch cancel/hospitation/lzk/unresolved belegt
        ist — analog zum bestehenden ``⚠``-Muster für `unresolved`.
        """
        if day_index >= len(self.app.day_columns):
            return "", "normal"
        day = self.app.day_columns[day_index]
        date_text = self._format_header_date(day.datum)
        is_next_unit = day_index == self._next_unit_index
        next_unit_marker = " ▶" if is_next_unit else ""

        if day.is_cancel():
            return f"{date_text}{next_unit_marker}", "cancel"
        if day.is_hospitation():
            return f"{date_text}{next_unit_marker}", "hospitation"
        if day.is_lzk():
            return f"{date_text}{next_unit_marker}", "lzk"
        if day.is_unresolved_link():
            return f"{date_text} ⚠{next_unit_marker}", "unresolved"
        if is_next_unit:
            return date_text, "next_unit"
        return date_text, "normal"

    def _apply_header_color(self, label: ui.Label, col_type: str) -> None:
        """Wendet Spalten-Typ-Farben auf ein Header-Label an (kein Hex-Wert im Consumer)."""
        if col_type == "cancel":
            theme_label_tinted(label, "warning_soft", degree=0.72, base_token="panel_strong", fg_token="fg_muted")
        elif col_type == "hospitation":
            theme_label_tinted(label, HOSPITATION_SEED, degree=0.38, base_token="panel_strong")
        elif col_type == "lzk":
            theme_label_tinted(label, "success_soft", degree=0.72, base_token="panel_strong")
        elif col_type == "unresolved":
            theme_label_token(label, bg_token="warning_soft")
        elif col_type == "next_unit":
            theme_label_tinted(label, "info_soft", degree=0.5, base_token="panel_strong")
        else:
            theme_label_token(label, bg_token="panel_strong")

    def _border_thickness(self, day_index: int) -> int:
        """Liefert die Rahmenstaerke (2px fuer datumslos/UB, sonst 1px) einer Tages-Spalte."""
        return 2 if self._accent_border_active(day_index) else 1

    def _accent_border_active(self, day_index: int) -> bool:
        if not 0 <= day_index < len(self.app.day_columns):
            return False
        day = self.app.day_columns[day_index]
        return day.is_dateless() or day.is_ub()

    def _apply_ub_border(self, widget: ui.Widget, day_index: int) -> None:
        """Setzt Datumslos-/UB-Akzentrahmen oder neutralen Rahmen auf einem Widget."""
        in_range = 0 <= day_index < len(self.app.day_columns)
        if in_range and self.app.day_columns[day_index].is_dateless():
            theme_widget_border(widget, color_token="danger", thickness=2)
        elif in_range and self.app.day_columns[day_index].is_ub():
            theme_widget_border(widget, color_token="accent", thickness=2)
        else:
            theme_widget_border(widget, color_token="border", thickness=1)

    @staticmethod
    def _format_header_date(raw_date: str) -> str:
        """Formatiert Datumswerte als `Mi 18.02.`; bei Parsing-Fehlern bleibt der Originalwert."""
        text = str(raw_date).strip()
        if not text:
            return ""

        parsed = None
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d-%m-%y", "%d.%m.%Y", "%d.%m.%y"):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            return text

        weekday_map = {0: "Mo", 1: "Di", 2: "Mi", 3: "Do", 4: "Fr", 5: "Sa", 6: "So"}
        weekday = weekday_map.get(parsed.weekday(), "")
        return f"{weekday} {parsed.day:02d}.{parsed.month:02d}.".strip()

    def _row_index_for_field(self, field_key: str) -> int | None:
        """Liefert die Grid-Zeile für ein fachliches Feld."""
        label = self.app.row_labels.get(field_key)
        if label is None:
            return None
        info = label.grid_info()
        row_value = info.get("row")
        try:
            return int(row_value)
        except (TypeError, ValueError):
            return None

    def _visible_row_defs(self) -> list[tuple[str, str]]:
        """Liefert nur Zeilen, die mindestens in einer Spalte sichtbar sind."""
        visible: list[tuple[str, str]] = []
        for field_key, label_text in self.app.row_defs:
            if any(self._field_is_visible_for_day(field_key, day) for day in self.app.day_columns):
                visible.append((field_key, label_text))
        return visible

    def _grid_structure_matches_state(self) -> bool:
        """Prüft, ob vorhandene Widgets zur aktuellen fachlichen Sichtbarkeit passen.

        Dreiwertig statt binär (Kursplaner Item 4, Stufe 2): für Zellen
        AUSSERHALB des aktuellen Mount-Fensters ist "domain-sichtbar, aber
        kein Widget" ein legitimer Zustand, kein struktureller Fehler mehr --
        die spätere Virtualisierung mountet dort bewusst nichts. Solange kein
        echtes Mount/Unmount existiert (vor Stufe 3), bleibt `cell_widgets`
        aber für jede domain-sichtbare Zelle vollständig befüllt, das
        Mount-Fenster wirkt sich also noch nicht aus -- diese Änderung ist
        eine strikte Lockerung der alten Gleichheitsprüfung, keine
        Verhaltensänderung: alles, was die alte Prüfung erfüllte, erfüllt
        auch diese.
        """
        if len(self.app.header_labels) != len(self.app.day_columns):
            return False

        expected_row_defs = self._visible_row_defs()
        expected_fields = [field_key for field_key, _ in expected_row_defs]
        actual_fields = list(self.app.row_labels.keys())
        if actual_fields != expected_fields:
            return False

        viewport_sync_h = getattr(self.app, "viewport_sync_h", None)
        mounted_range = viewport_sync_h.mounted_day_index_range() if viewport_sync_h is not None else None

        for field_key in expected_fields:
            for day_index, day in enumerate(self.app.day_columns):
                expected_visible = self._field_is_visible_for_day(field_key, day)
                has_widget = (field_key, day_index) in self.app.cell_widgets
                if not expected_visible:
                    if has_widget:
                        return False  # verwaistes Widget fuer eine jetzt irrelevante Zelle: immer ein Fehler
                    continue
                if mounted_range is not None and not (mounted_range[0] <= day_index <= mounted_range[1]):
                    continue  # domain-sichtbar, aber ausserhalb des Mount-Fensters: erlaubt
                if not has_widget:
                    return False  # sollte gerade gemountet sein, ist es nicht: ein Fehler

        return True

    def _reconcile_column_mounts(self) -> None:
        """Hält `cell_widgets` auf das aktuelle Mount-Fenster begrenzt

        (Kursplaner Item 4, Stufe 4 -- HOT/WARM bleiben ein gemeinsames
        `grid()`'d/lebendiges Fenster wie in Stufe 3; alles ausserhalb wird
        jetzt echt COLD: `destroy()`t und aus `cell_widgets` entfernt, statt
        nur `grid_remove()`t).

        Zwei Durchläufe:
        1. Zellen, deren Tag jetzt ausserhalb des Fensters liegt, werden
           evictet (`_evict_cell_to_cold()`) -- rettet ungespeicherten Text
           nach `pending_cell_text`, zerstört das Widget.
        2. Für jedes domain-sichtbare (Feld, Tag) innerhalb des Fensters:
           existiert das Widget bereits, wird es (wieder) sichtbar gemacht
           (`grid()`, idempotent falls schon sichtbar); existiert es nicht
           (zuvor COLD oder erstmals in Reichweite), wird es über
           `_create_and_mount_cell()` neu erzeugt -- mit `pending_cell_text`
           als Vorbelegung, falls vorhanden, sonst dem Domain-Wert.

        Löst nie einen Save aus: das Erfassen von `pending_cell_text` ist
        reines Lesen-und-Merken (kein `save_cell()`-Aufruf, keine
        Domain-Mutation) -- nur ein echter Fokusverlust committet weiterhin
        über den bestehenden Pfad (`editor_controller.save_cell()`).

        Nur `cell_widgets` ist betroffen -- Header (immer vollständig
        gemountet) und `sequence_field_widgets` (bewusst isoliert per
        `_reconcile_sequence_field_mounts()`, s. dort, Kursplaner Item 4
        Stufe 6) bleiben hier unangetastet.
        """
        if self.app._is_rebuilding_grid:
            return
        mounted_range = self.app.viewport_sync_h.mounted_day_index_range()
        if mounted_range is None:
            return
        self._reconcile_sequence_field_mounts(mounted_range)
        lo, hi = mounted_range

        for (field_key, day_index), cell in list(self.app.cell_widgets.items()):
            if not (lo <= day_index <= hi):
                self._evict_cell_to_cold(field_key, day_index, cell)

        for field_key, _label_text in self._visible_row_defs():
            row_idx = self._row_index_for_field(field_key)
            if row_idx is None:
                continue
            help_text = self._field_help_text(field_key)
            for day_index in range(max(0, lo), min(hi, len(self.app.day_columns) - 1) + 1):
                day = self.app.day_columns[day_index]
                if not self._field_is_visible_for_day(field_key, day):
                    continue
                key = (field_key, day_index)
                existing = self.app.cell_widgets.get(key)
                if existing is not None:
                    existing.grid()
                    continue
                grid_column = self.app.day_grid_columns.get(day_index, day_index)
                pending_text = self.app.pending_cell_text.get(key)
                value = pending_text if pending_text is not None else self.app._field_value(day, field_key)
                cell = self._create_and_mount_cell(
                    field_key=field_key,
                    day=day,
                    day_index=day_index,
                    row_idx=row_idx,
                    grid_column=grid_column,
                    value=value,
                    help_text=help_text,
                )
                self._grow_row_minsize_for_cell(field_key, cell)

    def _evict_cell_to_cold(self, field_key: str, day_index: int, cell) -> None:
        """Entfernt eine einzelne Zelle vollständig (COLD): rettet ungespeicherten

        Text nach `pending_cell_text`, zerstört das Widget, entfernt den
        `cell_widgets`-Eintrag.

        Reines Lesen-und-Merken -- kein I/O, kein `save_cell()`-Aufruf, keine
        Domain-Mutation. Prüft zusätzlich `active_editor`: ein Nutzer kann
        eine Zelle fokussiert halten und trotzdem den Viewport wegscrollen
        (Tk-Fokus hängt nicht von Sichtbarkeit ab); `<FocusOut>` feuert nicht
        zuverlässig vor `destroy()`, daher wird der State hier explizit
        bereinigt, statt sich auf das Event zu verlassen.

        Save-Grenze (bewusst, nicht nur Nebenwirkung): COLD-Eviction einer
        gerade editierten Zelle löst **niemals** selbst einen Commit aus --
        auch nicht über den `active_editor`-Cleanup oben. Nur ein echter
        `<FocusOut>` (`GRID_COMMIT_CELL`-Intent) committet. Scrollen/
        Sichtbarkeitswechsel bleiben damit garantiert save-frei, exakt wie
        von Anfang an gefordert ("Scrollen speichert nie").
        """
        day = self.app.day_columns[day_index] if day_index < len(self.app.day_columns) else None
        if day is not None:
            current_text = cell.get("1.0", "end-1c")
            domain_value = self.app._field_value(day, field_key)
            if current_text != domain_value:
                self.app.pending_cell_text[(field_key, day_index)] = current_text

        active_editor = self.app.ui_state.active_editor
        if active_editor is not None and active_editor.field_key == field_key and active_editor.day_index == day_index:
            self.app.ui_state.clear_active_editor()

        cell.destroy()
        del self.app.cell_widgets[(field_key, day_index)]

    def _reconcile_sequence_field_mounts(self, mounted_range: tuple[int, int]) -> None:
        """Hält Sequenzfeld-Spannzellen (Sequenzziel/Leitkompetenz) auf ihre

        Schnittmenge mit dem aktuellen Mount-Fenster begrenzt (Kursplaner
        Item 4, Stufe 6). Bewusst als eigene Methode neben
        `_reconcile_column_mounts()`, da eine Spannzelle nicht "eine Zelle
        pro Tag" ist, sondern mehrere Tages-Spalten gleichzeitig überspannt
        -- aber über denselben Aufrufer (s. o.) angebunden, damit nie einer
        der beiden Reconciliation-Pfade vergessen wird, wenn sich der andere
        ändert.

        Der volle logische Span eines Sequenzlaufs (`_run_span()`,
        unverändert) ist immer ein zusammenhängender Grid-Spalten-Bereich;
        das Mount-Fenster (`mounted_range`, in Tages-Index-Terminologie)
        wird dafür in denselben Grid-Spalten-Raum übersetzt
        (`day_grid_columns`). Die Schnittmenge zweier Intervalle ist immer
        höchstens EIN zusammenhängendes Intervall -- kein Fall für
        `compute_contiguous_spans()` (das wäre nur nötig, wenn das
        Mount-Fenster selbst kein einzelnes `(lo, hi)`-Intervall mehr wäre;
        aktuell ist es das per Konstruktion immer).

        Löst wie `_reconcile_column_mounts()` NIE einen Save aus:
        Text-Rettung vor der Zerstörung ist reines Lesen-und-Merken in
        `pending_cell_text` (geschlüsselt als `(field_key, first_row_index)`
        -- eigener Namensraum ohne Kollisionsrisiko, da "Sequenzziel"/
        "Leitkompetenz" nie als Feld-Schlüssel normaler Zeilen vorkommen).
        `save_sequence_field()` wird hier nie aufgerufen -- anders als im
        ursprünglichen Plan-Entwurf, der noch von einem Force-Commit-
        Mechanismus ausging, den Stufe 4 zugunsten von `pending_cell_text`
        verworfen hat; dieselbe Entscheidung gilt konsequent auch hier.
        Sequenzfeld-Zellen tragen ohnehin kein `active_editor`-Äquivalent
        (Fokus-/Klick-Intents sind bewusste No-ops, s.
        `ui_intent_controller.py`) -- nichts zu bereinigen dort.
        """
        if not self.app.sequence_fields_visible_var.get() or not self.app.topic_sequence_plans:
            return

        lo, hi = mounted_range
        day_grid_columns = self.app.day_grid_columns
        lo_col = day_grid_columns.get(lo)
        hi_col = day_grid_columns.get(hi)
        if lo_col is None or hi_col is None:
            return
        mounted_col_range = range(lo_col, hi_col + 1)

        row_index_to_grid_col = compute_row_index_to_grid_col(self.app.day_columns, day_grid_columns)

        for field_key in SEQUENCE_FIELD_ROW_ORDER:
            row_idx = SEQUENCE_FIELD_ROW_ORDER.index(field_key)
            for view in self.app.topic_sequence_plans:
                full_span = self._sequence_field_renderer._run_span(
                    row_index_to_grid_col, view.run.first_row_index, view.run.last_row_index
                )
                widget_key = (field_key, view.run.first_row_index)
                existing = self.app.sequence_field_widgets.get(widget_key)
                domain_value = view.sequenzziel if field_key == "Sequenzziel" else view.leitkompetenz

                sub_span = None
                if full_span is not None:
                    start = max(full_span.start, mounted_col_range.start)
                    stop = min(full_span.stop, mounted_col_range.stop)
                    if start < stop:
                        sub_span = range(start, stop)

                if sub_span is None:
                    if existing is not None:
                        self._evict_sequence_field_to_cold(field_key, view.run.first_row_index, existing, domain_value)
                    continue

                if existing is not None:
                    grid_info = existing.grid_info()
                    if int(grid_info.get("column", -1)) != sub_span.start or int(
                        grid_info.get("columnspan", -1)
                    ) != len(sub_span):
                        existing.grid(row=row_idx, column=sub_span.start, columnspan=len(sub_span), sticky="nsew")
                    continue

                pending_text = self.app.pending_cell_text.get(widget_key)
                value = pending_text if pending_text is not None else domain_value
                cell = self._sequence_field_renderer._create_text_cell(
                    self.app.grid_inner,
                    value,
                    editable=True,
                    canceled=False,
                    unresolved_link=False,
                    height_lines=self.app.collapsed_row_lines,
                )
                cell.grid(row=row_idx, column=sub_span.start, columnspan=len(sub_span), sticky="nsew")
                self._sequence_field_renderer._bind_events(
                    cell, field_key=field_key, first_row_index=view.run.first_row_index
                )
                self.app.sequence_field_widgets[widget_key] = cell

    def _evict_sequence_field_to_cold(
        self, field_key: str, first_row_index: int, cell, domain_value: str
    ) -> None:
        """Entfernt eine einzelne Sequenzfeld-Spannzelle vollständig (COLD).

        Spiegelt `_evict_cell_to_cold()` für den Sequenzfeld-Fall -- reines
        Lesen-und-Merken nach `pending_cell_text`, dann `destroy()`. Löst
        ebenso nie einen Save aus (Sequenzfeld-Zellen haben ohnehin kein
        `active_editor`-Äquivalent -- Fokus-Intents sind bewusste No-ops,
        s. `ui_intent_controller.py`).
        """
        current_text = cell.get("1.0", "end-1c")
        if current_text != domain_value:
            self.app.pending_cell_text[(field_key, first_row_index)] = current_text
        cell.destroy()
        del self.app.sequence_field_widgets[(field_key, first_row_index)]

    def _row_layout(self, field_key: str) -> tuple[int, bool, bool, str]:
        """Berechnet Höhe, Kollaps-Status und Labeltext einer Feldzeile und cacht das Ergebnis.

        Das Ergebnis hängt ausschließlich von den Zellwerten aller Spalten ab
        und ändert sich während der Navigation nie — nur nach Datenschreibvorgängen
        oder explizitem Zeilen-Expand/Collapse. Deshalb werden berechnete Werte in
        `_row_layout_cache` gespeichert und nur über `invalidate_row_layout_cache()`
        gelöscht.

        Returns:
            Tupel (row_height, collapsible, expanded, label_text), wobei
            `row_height` die darzustellende Zeilenhöhe in Textzeilen ist,
            `collapsible` angibt, ob ein Expand/Collapse-Pfeil gezeigt werden soll,
            `expanded` den aktuellen Aufklapp-Zustand hält und
            `label_text` ggf. mit dem Richtungspfeil-Icon versehen ist.
        """
        cached = self._row_layout_cache.get(field_key)
        if cached is not None:
            return cached
        label_text = next((text for key, text in self.app.row_defs if key == field_key), field_key)
        row_values = [self.app._field_value(day, field_key) for day in self.app.day_columns]
        max_visual_lines = max([self.app._estimate_visual_lines(value) for value in row_values], default=1)
        expanded_height = max(2, max_visual_lines)
        collapsible = expanded_height > self.app.collapsed_row_lines
        expanded = bool(self.app.row_expanded.get(field_key, self.app.expand_long_rows_var.get()))
        self.app.row_expanded[field_key] = expanded

        row_height = expanded_height if expanded else self.app.collapsed_row_lines
        if collapsible:
            icon = "▾" if expanded else "▸"
            label_text = f"{icon} {label_text}"
        result = (row_height, collapsible, expanded, label_text)
        self._row_layout_cache[field_key] = result
        return result

    def invalidate_row_layout_cache(self, field_key: str | None = None) -> None:
        """Löscht den Row-Layout-Cache vollständig oder für ein einzelnes Feld.

        Muss aufgerufen werden, wenn sich Zellwerte ändern könnten (Schreibvorgang
        via `collect_day_columns()`) oder wenn die Grid-Struktur komplett neu aufgebaut
        wird (`_rebuild_grid()`). Letzteres deckt auch Zoom-Änderungen,
        Modus-Wechsel und Zeilen-Expand/Collapse ab.

        Args:
            field_key: Wenn angegeben, wird nur der Cache-Eintrag für dieses Feld
                gelöscht; ohne Argument wird der gesamte Cache geleert.
        """
        if field_key is None:
            self._row_layout_cache.clear()
        else:
            self._row_layout_cache.pop(field_key, None)

    def _field_is_visible_for_day(self, field_key: str, day: DayColumn) -> bool:
        """Bestimmt, ob ein Feld für eine Spalte als Widget aufgebaut werden soll.

        Der Modus-Check (inkl. Zeilenfilter-Overrides) muss auch für den
        Unlinked-Guard-Fallback laufen, sonst lässt sich z. B. "Inhalt" bei
        Einheiten ohne verlinkte Datei nie modusabhängig ausblenden, weil der
        Fallback sonst den Filter komplett umgeht.
        """
        if not self.app.row_display_mode_usecase.is_linked_day(day):
            if field_key not in {"inhalt", "stunden", "startzeit", "Oberthema", "Ausfallgrund"}:
                return False
        return self.app.row_display_mode_usecase.field_is_relevant_for_day(field_key, day, self.app.row_filter_settings)

    def _clear_selection_if_selected_cell_no_longer_visible(self) -> None:
        """Löscht die Zellauswahl, falls die zuvor ausgewählte Zelle nach einem
        Rebuild (z. B. Modus-/Filterwechsel) nicht mehr existiert.

        Prüft die Domain-Sichtbarkeit (`_field_is_visible_for_day()`), nicht
        Widget-Präsenz in `cell_widgets` -- letzteres ist heute zwar noch
        vollständig (keine Virtualisierung), aber die Domain-Frage ist die
        eigentliche, stabile Quelle der Wahrheit dafür.
        """
        selected = self.app.ui_state.selected_cell
        if selected is None:
            return
        selected_day = (
            self.app.day_columns[selected.day_index]
            if selected.day_index < len(self.app.day_columns)
            else None
        )
        if selected_day is not None and self._field_is_visible_for_day(selected.field_key, selected_day):
            return
        self.app.ui_state.clear_selected_cell()
        if self.app.ui_state.selection_level == self.app.ui_state.SELECTION_LEVEL_CELL:
            self.app.ui_state.set_selection_level(self.app.ui_state.SELECTION_LEVEL_COLUMN)

    def _apply_cell_state(
        self,
        widget: ui.Text,
        *,
        text: str,
        editable: bool,
        canceled: bool,
        unresolved_link: bool,
        row_height: int,
        is_lzk: bool,
        is_hospitation: bool,
        lzk_masked: bool,
        italic: bool,
    ) -> None:
        """Schreibt Inhalt/Stil einer existierenden Zelle ohne Widget-Neubau."""
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(height=max(self.app.collapsed_row_lines, row_height))
        widget.configure(font=("Consolas", self.app.preview_font_size, "italic") if italic else self.app.preview_font)

        if canceled:
            theme_text_tinted(widget, "warning_soft", degree=0.72, base_token="panel_strong", fg_token="fg_muted")
            widget.configure(state="disabled")
            return
        if unresolved_link:
            theme_text(widget, bg_token="warning_soft")
            return
        if lzk_masked:
            theme_text_tinted(widget, "success_soft", degree=0.72, base_token="panel_strong", fg_token="fg_muted")
            widget.configure(state="disabled")
            return
        if is_hospitation:
            theme_text_tinted(widget, HOSPITATION_SEED, degree=0.38, base_token="panel_strong")
            return
        if is_lzk:
            theme_text_tinted(widget, "success_soft", degree=0.72, base_token="panel_strong")
            return
        if editable:
            theme_text(widget)
            return
        theme_text(widget, bg_token="bg_panel", fg_token="fg_muted")
        widget.configure(state="disabled")

    def _apply_cell_selection_style(self, widget: ui.Text, *, field_key: str, day_index: int) -> None:
        """Hebt die aktuell ausgewählte Navigationszelle sichtbar hervor."""
        selected = self.app.ui_state.selected_cell
        is_selected = selected is not None and selected.field_key == field_key and selected.day_index == day_index
        if is_selected:
            theme_widget_border(widget, color_token="selection_bg", thickness=2)
            widget.configure(borderwidth=2, relief="solid")
            return
        self._apply_ub_border(widget, day_index)
        widget.configure(borderwidth=self._border_thickness(day_index), relief="solid")

    def _create_text_cell(
        self,
        parent: ui.Widget,
        text: str,
        editable: bool,
        canceled: bool,
        unresolved_link: bool,
        height_lines: int,
        *,
        is_lzk: bool = False,
        is_hospitation: bool = False,
        lzk_masked: bool = False,
        italic: bool = False,
    ) -> ui.Text:
        """Erzeugt ein Text-Widget für eine Grid-Zelle mit zustandsabhängiger Darstellung."""
        width_chars = max(14, self.app.day_column_width // 9)
        cell_font = ("Consolas", self.app.preview_font_size, "italic") if italic else self.app.preview_font
        widget = ui.Text(
            parent,
            wrap="word",
            width=width_chars,
            height=max(self.app.collapsed_row_lines, height_lines),
            font=cell_font,
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=2,
            undo=True,
        )
        widget.insert("1.0", text)

        if canceled:
            theme_text_tinted(widget, "warning_soft", degree=0.72, base_token="panel_strong", fg_token="fg_muted")
            widget.configure(state="disabled")
        elif unresolved_link:
            theme_text(widget, bg_token="warning_soft")
        elif lzk_masked:
            theme_text_tinted(widget, "success_soft", degree=0.72, base_token="panel_strong", fg_token="fg_muted")
            widget.configure(state="disabled")
        elif is_hospitation:
            theme_text_tinted(widget, HOSPITATION_SEED, degree=0.38, base_token="panel_strong")
        elif is_lzk:
            theme_text_tinted(widget, "success_soft", degree=0.72, base_token="panel_strong")
        elif editable:
            theme_text(widget)
        else:
            theme_text(widget, bg_token="bg_panel", fg_token="fg_muted")
            widget.configure(state="disabled")

        widget.bind("<MouseWheel>", self.app._on_grid_mousewheel)
        self._apply_cell_selection_style(widget, field_key="", day_index=-1)
        return widget

    def _create_and_mount_cell(
        self,
        *,
        field_key: str,
        day: DayColumn,
        day_index: int,
        row_idx: int,
        grid_column: int,
        value: str,
        help_text: str,
    ) -> ui.Text:
        """Erzeugt EIN Zellen-Widget, platziert es im Grid und registriert es in

        ``cell_widgets`` -- gemeinsamer Kern für den vollen `_rebuild_grid()`-
        Durchlauf UND das Remounten einer einzelnen zuvor COLD-entfernten
        Zelle (`_reconcile_column_mounts()`, Kursplaner Item 4, Stufe 4).
        Beide Pfade müssen garantiert dasselbe Zellen-Setup (Theming,
        Editierbarkeit, Event-Bindings) verwenden, statt zweier unabhängiger,
        potenziell divergierender Kopien.

        Höhen-Buchführung ist bewusst NICHT Teil dieser Methode: der volle
        Rebuild sammelt Zeilenhöhen in einem lokalen Dict und wendet sie am
        Ende gebündelt an, während ein Einzelzellen-Remount stattdessen
        `_grow_row_minsize_for_cell()` (grow-only, s. Item 2) braucht -- die
        beiden Aufrufer erledigen das jeweils selbst nach diesem Aufruf.
        """
        is_cancel = day.is_cancel()
        is_unresolved_link = day.is_unresolved_link()
        is_lzk = day.is_lzk()
        is_hospitation = day.is_hospitation()
        editable = self.app.row_display_mode_usecase.is_editable(field_key, day, self.app.row_filter_settings)
        canceled_visual = is_cancel and field_key not in {"Vertretungsmaterial", "Ausfallgrund"}
        row_height, _collapsible, _expanded, _label_text = self._row_layout(field_key)

        cell = self._create_text_cell(
            self.app.grid_inner,
            value,
            editable=editable,
            canceled=canceled_visual,
            unresolved_link=is_unresolved_link,
            height_lines=row_height,
            is_lzk=is_lzk,
            is_hospitation=is_hospitation,
            lzk_masked=False,
            italic=(field_key == "Kompetenzhorizont" and is_lzk),
        )
        cell.grid(row=row_idx, column=grid_column, sticky="nsew")
        self._apply_cell_selection_style(cell, field_key=field_key, day_index=day_index)
        if help_text:
            self._field_help_tooltips.append(HoverTooltip(cell, help_text))

        if editable:
            cell.bind(
                "<Button-1>",
                lambda _event, fk=field_key, di=day_index: self.app._handle_ui_intent(
                    UiIntent.GRID_CELL_CLICK,
                    field_key=fk,
                    day_index=di,
                ),
            )
            cell.bind(
                "<FocusIn>",
                lambda _event, fk=field_key, di=day_index: self.app._handle_ui_intent(
                    UiIntent.GRID_EDITOR_FOCUS_IN,
                    field_key=fk,
                    day_index=di,
                ),
            )
            cell.bind(
                "<FocusOut>",
                lambda _event, fk=field_key, di=day_index: self.app._handle_ui_intent(
                    UiIntent.GRID_COMMIT_CELL,
                    field_key=fk,
                    day_index=di,
                ),
            )
            cell.bind(
                "<FocusOut>",
                lambda _event, fk=field_key, di=day_index: self.app._handle_ui_intent(
                    UiIntent.GRID_EDITOR_FOCUS_OUT,
                    field_key=fk,
                    day_index=di,
                ),
                add="+",
            )
        else:
            cell.bind(
                "<Button-1>",
                lambda _event, di=day_index: self.app._handle_ui_intent(
                    UiIntent.GRID_DATE_CELL_CLICK,
                    day_index=di,
                ),
            )

        self.app.cell_widgets[(field_key, day_index)] = cell
        return cell

    def _rebuild_grid(self):
        """Baut den gesamten Grid-Inhalt aus dem aktuellen UI-Zustand neu auf."""
        # deliberate exception: long by necessity — muss Fix-Spalte, Header-Zeile,
        # Marker-Spalten, Sequenzfeld-Zeilen und alle Tages-Zellen in einem
        # zusammenhängenden Widget-Baum neu aufbauen (Tk-Grid-Layout erfordert
        # konsistente Spalten-/Zeilenindizes über alle Container hinweg); eine
        # Aufteilung würde nur den Layout-Zustand über mehrere Methoden verteilen,
        # ohne echte Kopplung zu reduzieren.
        self.invalidate_row_layout_cache()
        self.app._is_rebuilding_grid = True
        self._field_help_tooltips.clear()
        self.app.ui_state.clear_active_editor()
        self.app.cell_widgets = {}
        self.app.header_labels = {}
        self.app.row_labels = {}
        self.app.sequence_field_widgets = {}
        self.app.corner_label = None
        self._marker_widgets = []
        self._marker_kinds_by_widget = {}
        layout_items = self._display_layout_items()
        self.app.day_column_x_positions = {}
        row_pixel_heights: dict[int, int] = {}

        for child in self.app.fixed_inner.winfo_children():
            child.destroy()
        for child in self.app.fixed_header_frame.winfo_children():
            child.destroy()
        for child in self.app.header_inner.winfo_children():
            child.destroy()
        for child in self.app.grid_inner.winfo_children():
            child.destroy()

        self.app.fixed_inner.grid_columnconfigure(0, weight=0, minsize=220)
        x_cursor = 0
        grid_col = 0
        day_grid_columns: dict[int, int] = {}
        for item in layout_items:
            if item.get("type") == "marker":
                self.app.header_inner.grid_columnconfigure(grid_col, weight=0, minsize=self._marker_column_width)
                self.app.grid_inner.grid_columnconfigure(grid_col, weight=0, minsize=self._marker_column_width)
                x_cursor += self._marker_column_width
                grid_col += 1
                continue
            day_index_obj = item.get("day_index", -1)
            day_index = day_index_obj if isinstance(day_index_obj, int) else -1
            if day_index < 0:
                continue
            self.app.header_inner.grid_columnconfigure(grid_col, weight=0, minsize=self.app.day_column_width)
            self.app.grid_inner.grid_columnconfigure(grid_col, weight=0, minsize=self.app.day_column_width)
            self.app.day_column_x_positions[day_index] = x_cursor
            day_grid_columns[day_index] = grid_col
            x_cursor += self.app.day_column_width
            grid_col += 1
        self.app.day_grid_columns = day_grid_columns

        corner = ui.Label(
            self.app.fixed_header_frame,
            text="Datum",
            anchor="w",
            font=("Segoe UI", 9, "bold"),
            padx=8,
            pady=6,
            relief="solid",
            borderwidth=1,
        )
        theme_label_token(corner, bg_token="panel_strong")
        corner.pack(fill="both", expand=True)
        self.app.corner_label = corner

        for grid_col, item in enumerate(layout_items):
            if item.get("type") == "marker":
                kinds = item.get("kinds", ())
                kinds_tuple = tuple(str(kind) for kind in kinds) if isinstance(kinds, (tuple, list)) else ()
                marker = ui.Canvas(
                    self.app.header_inner,
                    width=self._marker_column_width,
                    height=1,
                    highlightthickness=0,
                    borderwidth=0,
                )
                marker.grid(row=0, column=grid_col, sticky="nsew")
                marker.bind(
                    "<Configure>",
                    lambda _event, widget=marker, mk=kinds_tuple: self._draw_marker_canvas(widget, mk),
                )
                self._marker_kinds_by_widget[int(marker.winfo_id())] = kinds_tuple
                self._draw_marker_canvas(marker, kinds_tuple)
                self._marker_widgets.append(marker)
                continue

            day_index_obj = item.get("day_index", -1)
            day_index = day_index_obj if isinstance(day_index_obj, int) else -1
            if day_index < 0:
                continue
            header_text, col_type = self._header_visual_state(day_index)

            header = ui.Label(
                self.app.header_inner,
                text=header_text,
                anchor="center",
                font=("Segoe UI", 9, "bold"),
                padx=6,
                pady=6,
                relief="solid",
                borderwidth=self._border_thickness(day_index),
            )
            self._apply_header_color(header, col_type)
            self._apply_ub_border(header, day_index)
            header.grid(row=0, column=grid_col, sticky="nsew")
            header.bind(
                "<Button-1>",
                lambda _e, di=day_index: self.app._handle_ui_intent(UiIntent.GRID_COLUMN_CLICK, day_index=di),
            )
            self.app.header_labels[day_index] = header

        row_idx = 0
        if self.app.sequence_fields_visible_var.get():
            row_idx = self._sequence_field_renderer.render(row_idx, day_grid_columns, row_pixel_heights)

        for field_key, label_text in self._visible_row_defs():
            row_values = [self.app._field_value(day, field_key) for day in self.app.day_columns]
            row_height, collapsible, _expanded, field_label_text = self._row_layout(field_key)

            field_label = ui.Label(
                self.app.fixed_inner,
                text=field_label_text,
                anchor="w",
                justify="left",
                font=("Segoe UI", 9, "bold"),
                padx=8,
                pady=3,
                relief="solid",
                borderwidth=1,
                cursor="hand2" if collapsible else "",
            )
            theme_label_token(field_label, bg_token="panel_strong")
            field_label.grid(row=row_idx, column=0, sticky="nsew")
            if collapsible:
                field_label.bind(
                    "<Button-1>",
                    lambda _e, fk=field_key: self.app._handle_ui_intent(UiIntent.GRID_TOGGLE_ROW_EXPAND, field_key=fk),
                )
            self.app.row_labels[field_key] = field_label
            help_text = self._field_help_text(field_key)
            if help_text:
                self._field_help_tooltips.append(HoverTooltip(field_label, help_text))
            row_pixel_heights[row_idx] = max(row_pixel_heights.get(row_idx, 0), int(field_label.winfo_reqheight()))

            for day_index, day in enumerate(self.app.day_columns):
                if not self._field_is_visible_for_day(field_key, day):
                    continue
                value = row_values[day_index] if day_index < len(row_values) else ""
                grid_column = day_grid_columns.get(day_index, day_index)
                cell = self._create_and_mount_cell(
                    field_key=field_key,
                    day=day,
                    day_index=day_index,
                    row_idx=row_idx,
                    grid_column=grid_column,
                    value=value,
                    help_text=help_text,
                )
                row_pixel_heights[row_idx] = max(row_pixel_heights.get(row_idx, 0), int(cell.winfo_reqheight()))

            row_idx += 1

        for row_idx, pixel_height in row_pixel_heights.items():
            if pixel_height <= 0:
                continue
            self.app.fixed_inner.grid_rowconfigure(row_idx, minsize=pixel_height)
            self.app.grid_inner.grid_rowconfigure(row_idx, minsize=pixel_height)

        self.app._is_rebuilding_grid = False
        self._clear_selection_if_selected_cell_no_longer_visible()
        self.app._refresh_header_styles()
        self.app._on_grid_inner_configure()
        self.app.action_controller.update_action_controls()
        # Nach _on_grid_inner_configure(), damit bbox()/scrollregion bereits
        # aktuelle Geometrie hat -- sonst koennte visible_day_index_range()
        # mit veralteten Massen rechnen.
        self._reconcile_column_mounts()

    def update_header(self, day_index: int):
        """Aktualisiert Text/Basisfarbe eines existierenden Tages-Headers."""
        label = self.app.header_labels.get(day_index)
        if label is None:
            return
        text, col_type = self._header_visual_state(day_index)
        label.configure(text=text, borderwidth=self._border_thickness(day_index))
        self._apply_header_color(label, col_type)
        self._apply_ub_border(label, day_index)

    def update_cell(self, field_key: str, day_index: int, *, sync_row_style: bool = True):
        """Aktualisiert eine einzelne Grid-Zelle im bestehenden Widget-Baum."""
        cell = self.app.cell_widgets.get((field_key, day_index))
        if cell is None or day_index >= len(self.app.day_columns):
            return

        row_height, _collapsible, _expanded, _label_text = self._row_layout(field_key)
        day = self.app.day_columns[day_index]
        editable = self.app.row_display_mode_usecase.is_editable(field_key, day, self.app.row_filter_settings)
        canceled_visual = day.is_cancel() and field_key not in {"Vertretungsmaterial", "Ausfallgrund"}
        value = self.app._field_value(day, field_key)
        self._apply_cell_state(
            cell,
            text=value,
            editable=editable,
            canceled=canceled_visual,
            unresolved_link=day.is_unresolved_link(),
            row_height=row_height,
            is_lzk=day.is_lzk(),
            is_hospitation=day.is_hospitation(),
            lzk_masked=False,
            italic=(field_key == "Kompetenzhorizont" and day.is_lzk()),
        )
        self._apply_cell_selection_style(cell, field_key=field_key, day_index=day_index)
        if sync_row_style:
            self.update_row_style(field_key)

    def update_row_style(self, field_key: str):
        """Aktualisiert Label, Hoehe und Zellstile einer Feldzeile.

        Bekannte, bewusst akzeptierte Grenze seit der Viewport-Virtualisierung:
        die Hoehenmessung unten loopt ueber ALLE Tage, misst aber nur aktuell
        materialisierte Zellen (`cell_widgets.get(...)`, `continue` bei COLD)
        -- ist die inhaltlich hoechste Zelle eines Feldes gerade ausserhalb
        des Mount-Fensters, kann die Zeile kurzzeitig zu niedrig gesetzt
        werden. Rein kosmetisch (Zeilenhoehe, kein Daten-/Sichtbarkeitsverlust)
        und selbstheilend: sobald diese Zelle wieder gemountet wird, greift
        der bestehende Grow-only-Mechanismus (`_grow_row_minsize_for_cell()`)
        und korrigiert die Hoehe. Der Save-Pfad selbst ruft diese volle
        Messung nicht auf (`update_column()` nutzt bewusst
        `sync_row_style=False`) -- nur `refresh_grid_content()` (externe
        Aenderungen, Undo/Redo, Modus-Wechsel) erreicht diesen Codepfad.
        """
        row_idx = self._row_index_for_field(field_key)
        if row_idx is None:
            return
        label = self.app.row_labels.get(field_key)
        if label is None:
            return

        row_height, collapsible, _expanded, label_text = self._row_layout(field_key)
        label.configure(text=label_text, cursor="hand2" if collapsible else "")
        theme_label_token(label, bg_token="panel_strong")
        if collapsible:
            label.bind(
                "<Button-1>",
                lambda _e, fk=field_key: self.app._handle_ui_intent(UiIntent.GRID_TOGGLE_ROW_EXPAND, field_key=fk),
            )
        else:
            label.unbind("<Button-1>")

        self.app.fixed_inner.grid_rowconfigure(row_idx, minsize=0)
        self.app.grid_inner.grid_rowconfigure(row_idx, minsize=0)
        max_height = int(label.winfo_reqheight())
        for day_index in range(len(self.app.day_columns)):
            cell = self.app.cell_widgets.get((field_key, day_index))
            if cell is None:
                continue
            self.update_cell(field_key, day_index, sync_row_style=False)
            max_height = max(max_height, int(cell.winfo_reqheight()))

        self.app.fixed_inner.grid_rowconfigure(row_idx, minsize=max_height)
        self.app.grid_inner.grid_rowconfigure(row_idx, minsize=max_height)

    def update_column(self, day_index: int):
        """Aktualisiert Header und alle Feldzellen NUR dieser einen Tages-Spalte.

        Trotz des schon vorher existierenden Namens rief diese Methode bislang
        `update_row_style()` je Feld auf, das seinerseits über ALLE Tage
        loopt — `update_column()` war also in Wahrheit ein voller Grid-Sweep,
        nur mit Umweg über die Zeilen-Update-Methode. Jetzt werden nur die
        Zellen dieser einen Spalte angefasst (über `update_cell(...,
        sync_row_style=False)`, denselben Baustein, den auch `update_row_style()`
        intern nutzt) sowie nur dieser eine Spalten-Header (`_apply_single_header_style()`,
        das bereits fuer den Zell-Selektions-Fast-Path existierte, aber hier
        bisher ungenutzt blieb).
        """
        self.update_header(day_index)
        for field_key, _label in self.app.row_defs:
            cell = self.app.cell_widgets.get((field_key, day_index))
            if cell is None:
                continue
            self.update_cell(field_key, day_index, sync_row_style=False)
            self._grow_row_minsize_for_cell(field_key, cell)
        if day_index in self.app.header_labels:
            self.app.selection_controller._apply_single_header_style(day_index)
        self.app._on_grid_inner_configure()

    def _grow_row_minsize_for_cell(self, field_key: str, cell) -> None:
        """Vergrößert die Zeilenhöhe (`minsize`), falls diese eine Zelle mehr Platz braucht.

        Bewusst nur GRÖSSER, nie kleiner: eine Verkleinerung müsste alle
        Zellen der Zeile neu vermessen — genau die Kosten, die
        `update_column()` für eine einzelne Spalte vermeiden soll (das
        übernimmt weiterhin `update_row_style()`, z. B. beim vollen
        `refresh_grid_content()`). Eine Zeile, die kurzzeitig höher bleibt
        als für diese eine Zelle nötig, ist ein rein kosmetischer,
        selbstheilender Zustand (der nächste volle Refresh vermisst neu) —
        kein Sichtbarkeits- oder Datenverlust wie bei einer zu niedrigen Zeile.
        """
        row_idx = self._row_index_for_field(field_key)
        if row_idx is None:
            return
        needed = int(cell.winfo_reqheight())
        if needed <= 0:
            return
        current = self.app.fixed_inner.grid_rowconfigure(row_idx).get("minsize") or 0
        if needed > current:
            self.app.fixed_inner.grid_rowconfigure(row_idx, minsize=needed)
            self.app.grid_inner.grid_rowconfigure(row_idx, minsize=needed)

    def refresh_grid_content(self):
        """Aktualisiert den kompletten Grid-Inhalt ohne Widget-Neuaufbau."""
        if self.app._is_rebuilding_grid:
            return
        # "Ist das Grid ueberhaupt schon aufgebaut" ist eine Frage an
        # header_labels (ein Header pro Tag, unabhaengig von Feld-Sichtbarkeit)
        # -- nicht an cell_widgets, das bei restriktiven Zeilenfiltern legitim
        # leer sein kann, obwohl das Grid korrekt aufgebaut ist.
        if not self.app.header_labels:
            self._rebuild_grid()
            return
        if not self._grid_structure_matches_state():
            self._rebuild_grid()
            return

        for day_index in range(len(self.app.day_columns)):
            self.update_header(day_index)
        for field_key, _label in self.app.row_defs:
            self.update_row_style(field_key)
        self.app._refresh_header_styles()
        self.app._on_grid_inner_configure()
        self.app.action_controller.update_action_controls()

    def _apply_grid_theme(self):
        """Wendet Theme-Änderungen per Patch-Update auf das bestehende Grid an."""
        if self.app._is_rebuilding_grid:
            return
        if self.app.corner_label is not None:
            theme_label_token(self.app.corner_label, bg_token="panel_strong")
        for widget in self._marker_widgets:
            marker_kinds = self._marker_kinds_by_widget.get(int(widget.winfo_id()), ())
            self._draw_marker_canvas(widget, marker_kinds)
        self.refresh_grid_content()

    def _on_grid_inner_configure(self, _event=None):
        """Synchronisiert die Scrollregion mit der aktuellen Grid-Größe."""
        self.app.header_canvas.configure(scrollregion=self.app.header_canvas.bbox("all"))
        self.app.fixed_canvas.configure(scrollregion=self.app.fixed_canvas.bbox("all"))
        self.app.grid_canvas.configure(scrollregion=self.app.grid_canvas.bbox("all"))

        header_canvas_width = max(1, self.app.header_canvas.winfo_width())
        header_canvas_height = max(1, self.app.header_canvas.winfo_height())
        fixed_canvas_height = max(1, self.app.fixed_canvas.winfo_height())
        grid_canvas_height = max(1, self.app.grid_canvas.winfo_height())

        self.app.header_canvas.itemconfigure(
            self.app.header_window,
            width=max(header_canvas_width, self.app.header_inner.winfo_reqwidth()),
            height=max(header_canvas_height, self.app.header_inner.winfo_reqheight()),
        )
        header_row_height = max(
            self.app.header_inner.winfo_reqheight(),
            int(self.app.corner_label.winfo_reqheight()) if self.app.corner_label else 0,
        )
        if header_row_height > 0:
            self.app.header_canvas.configure(height=header_row_height)
            self.app.fixed_header_frame.configure(height=header_row_height)

        self.app.fixed_canvas.itemconfigure(
            self.app.fixed_window,
            width=220,
            height=max(fixed_canvas_height, self.app.fixed_inner.winfo_reqheight()),
        )
        self.app.grid_canvas.itemconfigure(
            self.app.grid_window,
            height=max(grid_canvas_height, self.app.grid_inner.winfo_reqheight()),
        )
        self.app.viewport_sync.clamp_current_view()

    def _on_canvas_configure(self, _event=None):
        """Hält die Grid-Fensterhöhe bei Canvas-Resize konsistent."""
        self.app.header_canvas.itemconfigure(
            self.app.header_window,
            width=max(self.app.header_canvas.winfo_width(), self.app.header_inner.winfo_reqwidth()),
            height=max(self.app.header_canvas.winfo_height(), self.app.header_inner.winfo_reqheight()),
        )
        self.app.fixed_canvas.itemconfigure(
            self.app.fixed_window,
            width=220,
            height=max(self.app.fixed_canvas.winfo_height(), self.app.fixed_inner.winfo_reqheight()),
        )
        self.app.grid_canvas.itemconfigure(
            self.app.grid_window,
            height=max(self.app.grid_canvas.winfo_height(), self.app.grid_inner.winfo_reqheight()),
        )
        self._on_grid_inner_configure()

    def _on_vertical_scroll(self, *args):
        """Scrollt fixe und inhaltliche Grid-Spalte synchron in Y-Richtung."""
        self.app.viewport_sync.yview(*args)

    def _on_horizontal_scroll(self, *args):
        """Scrollt Kopfzeile und Grid-Inhalt synchron in X-Richtung."""
        self.app.viewport_sync_h.xview(*args)

    def _on_grid_mousewheel(self, event):
        """Behandelt Scroll- und Zoom-Interaktion im Grid (Ctrl+Wheel = Spaltenbreite)."""
        ctrl_pressed = bool(event.state & 0x0004)
        shift_pressed = bool(event.state & 0x0001)

        if ctrl_pressed:
            step = 20 if event.delta > 0 else -20
            self.app.day_column_width = max(
                self.app.min_day_column_width,
                min(self.app.max_day_column_width, self.app.day_column_width + step),
            )
            self._schedule_zoom_rebuild()
            return "break"

        units = -1 if event.delta > 0 else 1
        if shift_pressed:
            self._on_horizontal_scroll("scroll", units, "units")
        else:
            self.app.viewport_sync.yview_scroll(units, "units")
        return "break"

    def _schedule_zoom_rebuild(self, delay_ms: int = 120) -> None:
        """Plant einen verzögerten vollen Grid-Rebuild nach Zoom-Änderung (Debounce).

        `_rebuild_grid()` zerstört und baut den kompletten Widget-Baum neu. Bei
        schnellem Scrollen (Strg+Mausrad) erzeugt das Mausrad mehrere Events in
        kurzer Folge; würde jedes davon synchron einen vollen Rebuild auslösen,
        blockiert jeder Tick das nächste Event ("erst alles neu laden, dann
        weiter zoomen"). Analog zu `ActionController.schedule_action_controls_update`
        wird ein laufender `after`-Call abgebrochen und neu geplant, sodass
        mehrere schnelle Zoom-Ticks zu genau einem Rebuild kollabieren, sobald
        für `delay_ms` kein weiteres Wheel-Event mehr kam. Die Spaltenbreite
        selbst wird weiterhin sofort aktualisiert (billig); nur der teure
        Rebuild wird entkoppelt.

        Args:
            delay_ms: Wartezeit in Millisekunden bis zum tatsächlichen Rebuild.
        """
        if self._zoom_rebuild_after_id is not None:
            try:
                self.app.after_cancel(self._zoom_rebuild_after_id)
            except Exception:
                pass
            self._zoom_rebuild_after_id = None
        self._zoom_rebuild_after_id = self.app.after(delay_ms, self._run_scheduled_zoom_rebuild)

    def _run_scheduled_zoom_rebuild(self) -> None:
        """Führt den geplanten Zoom-Rebuild aus und löscht die Pending-ID."""
        self._zoom_rebuild_after_id = None
        self._rebuild_grid()

