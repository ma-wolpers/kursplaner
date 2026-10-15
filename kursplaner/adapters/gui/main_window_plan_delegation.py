"""Hauptfenster-Delegationen fuer Plantabelle, Detailansicht und Raster: duenne Weiterleitungen an die Controller (Grid, Editor, Overview, Aktionen).

Aus ``main_window.py`` ausgelagert (300-Zeilen-Regel), Methoden unverändert."""

from __future__ import annotations

import pathlib

from bw_libs.shared_gui_core import ensure_bw_gui_on_path
from kursplaner.adapters.gui.lesson_context_controller import MainWindowLessonContextController
from kursplaner.core.domain.day_column import DayColumn

ensure_bw_gui_on_path()
from bw_gui.runtime import ui  # noqa: E402


class KursplanerPlanDelegationMixin:
    """Hauptfenster-Delegationen fuer Plantabelle, Detailansicht und Raster: duenne Weiterleitungen an die Controller (Grid, Editor, Overview, Aktionen)."""

    def _clear_plan_table(self, title: str):
        """Setzt die rechte Planansicht auf einen leeren Ausgangszustand."""
        self.action_controller.clear_plan_table(title)

    def _undo_history(self):
        """Delegiert Undo an den Action-Controller."""
        self.action_controller.undo_history()

    def _redo_history(self):
        """Delegiert Redo an den Action-Controller."""
        self.action_controller.redo_history()

    def _on_grid_inner_configure(self, _event=None):
        """Synchronisiert Scrollregion/Layout nach Änderungen im Grid-Container."""
        return self.grid_renderer._on_grid_inner_configure(_event)

    def _on_canvas_configure(self, event):
        """Reagiert auf Größenänderungen des Canvas für responsive Grid-Breite."""
        return self.grid_renderer._on_canvas_configure(event)

    def _on_vertical_scroll(self, *args):
        """Delegiert vertikales Scrollen an beide Grid-Bereiche synchron."""
        return self.viewport_sync.yview(*args)

    def _on_horizontal_scroll(self, *args):
        """Delegiert horizontales Scrollen an Header- und Body-Canvas synchron."""
        return self.grid_renderer._on_horizontal_scroll(*args)

    def _load_selected_table(self, _event=None):
        """High-level Entry: lädt die aktuell selektierte Planung in die Detailansicht."""
        self.overview_controller.load_selected_table(_event)

    def _close_detail_view(self):
        """Schließt die Einheitenansicht und zeigt wieder nur die Kursliste."""
        self.overview_controller.close_detail_view()

    def _show_course_overview(self):
        """Zeigt die Kursliste als alleinige Hauptansicht."""
        self.screen_builder.show_course_overview()

    def _show_course_detail(self):
        """Zeigt die Einheitenansicht als alleinige Hauptansicht."""
        self.screen_builder.show_course_detail()

    def _collect_day_columns(self, changed_row_indices: set[int] | None = None) -> None:
        """Aktualisiert die Grid-Projektion (`day_columns`) aus der geladenen Tabelle.

        Args:
            changed_row_indices: Siehe `OverviewController.collect_day_columns()`.
        """
        self.overview_controller.collect_day_columns(changed_row_indices)

    def _field_value(self, day: DayColumn, field_key: str) -> str:
        """Liefert den darzustellenden Zellwert für ein Feld aus `day_columns`."""
        return self.lesson_context_controller.field_value(day, field_key)

    def _estimate_visual_lines(self, text: str) -> int:
        """Schätzt benötigte Anzeigezeilen für Text anhand UI-Regeln."""
        return self.lesson_context_controller.estimate_visual_lines(text)

    @staticmethod
    def _keyword_match(text: str, keywords: list[str]) -> bool:
        """Prüft case-insensitiv, ob eines der Keywords im Text enthalten ist."""
        return MainWindowLessonContextController.keyword_match(text, keywords)

    @staticmethod
    def _contains_markdown_link(text: str) -> bool:
        """Erkennt Obsidian-Linksyntax `[[...]]` in einem Text."""
        return MainWindowLessonContextController.contains_markdown_link(text)

    def _parse_halfyear_token(self) -> str:
        """Liest Halbjahres-Token aus aktueller Planmetadatenlage."""
        return self.lesson_context_controller.parse_halfyear_token()

    def _is_lzk_row(self, row_index: int) -> bool:
        """Prüft, ob die gegebene Tabellenzeile als LZK klassifiziert ist."""
        return self.lesson_context_controller.is_lzk_row(row_index)

    def _next_lzk_number(self) -> int:
        """Bestimmt die nächste freie LZK-Nummer im aktuellen Plan."""
        return self.lesson_context_controller.next_lzk_number()

    def _replace_plan_link(self, row_index: int, new_stem: str):
        """Ersetzt den Linktext in einer Planzeile durch einen neuen Dateistamm."""
        self.lesson_context_controller.replace_plan_link(row_index, new_stem)

    def _rename_linked_file_for_row(self, row_index: int, desired_stem: str) -> pathlib.Path | None:
        """Benennt die verlinkte Stunden-Datei einer Zeile auf den Zielstamm um."""
        return self.lesson_context_controller.rename_linked_file_for_row(row_index, desired_stem)

    def _toggle_column_selection(self, day_index: int):
        """Schaltet die Selektion einer Spalte und stößt Header-Update an."""
        self.selection_controller.toggle_column_selection(day_index)

    def _update_selected_column_label(self):
        """Aktualisiert das UI-Label für aktuell selektierte Grid-Spalten."""
        self.selection_controller.update_selected_column_label()

    def _refresh_header_styles(self):
        """Aktualisiert Header-Styling anhand Selektion und Theme-Zustand."""
        self.selection_controller.refresh_header_styles()

    def _selected_indices_sorted(self) -> list[int]:
        """Liefert selektierte Spaltenindizes in stabil sortierter Reihenfolge."""
        return self.selection_controller.selected_indices_sorted()

    def _collect_selected_or_warn(self) -> list[int]:
        """Liefert selektierte Spalten oder zeigt Hinweis bei leerer Auswahl."""
        return self.selection_controller.collect_selected_or_warn()

    def _get_single_selected_or_warn(self) -> int | None:
        """Liefert genau eine ausgewählte Spalte oder zeigt Warnhinweis."""
        return self.selection_controller.get_single_selected_or_warn()

    def _set_single_column_selection(self, day_index: int, *, ensure_visible: bool = False):
        """Setzt genau eine selektierte Spalte und optional den horizontalen Fokus darauf."""
        self.selection_controller.set_single_column_selection(day_index, ensure_visible=ensure_visible)

    def _move_selected_column_focus(self, direction: int) -> bool:
        """Verschiebt die Spaltenselektion per Tastatur zur nächsten stattfindenden Einheit."""
        return self.selection_controller.move_selection_to_adjacent_occurring(direction)

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
        lzk_masked: bool = False,
    ) -> ui.Text:
        """Erzeugt ein Text-Widget für eine Grid-Zelle mit passendem Rendering."""
        return self.grid_renderer._create_text_cell(
            parent,
            text,
            editable,
            canceled,
            unresolved_link,
            height_lines,
            is_lzk=is_lzk,
            lzk_masked=lzk_masked,
        )

    def _rebuild_grid(self):
        """High-frequency Entry: rendert das komplette Plan-Grid neu."""
        self.grid_renderer.set_next_unit_index(self.overview_controller._next_lesson_column_index())
        return self.grid_renderer._rebuild_grid()

    def _refresh_grid_content(self):
        """Aktualisiert Header/Zellen ohne kompletten Widget-Neuaufbau."""
        self.grid_renderer.set_next_unit_index(self.overview_controller._next_lesson_column_index())
        return self.grid_renderer.refresh_grid_content()

    def _update_grid_column(self, day_index: int):
        """Aktualisiert Header und alle Zellen einer bestehenden Spalte."""
        self.grid_renderer.set_next_unit_index(self.overview_controller._next_lesson_column_index())
        return self.grid_renderer.update_column(day_index)

    def _update_grid_cell(self, field_key: str, day_index: int):
        """Aktualisiert den Inhalt/Stil einer einzelnen existierenden Zelle."""
        return self.grid_renderer.update_cell(field_key, day_index)

    def _update_grid_header(self, day_index: int):
        """Aktualisiert nur den Header einer bestehenden Spalte."""
        self.grid_renderer.set_next_unit_index(self.overview_controller._next_lesson_column_index())
        return self.grid_renderer.update_header(day_index)

    def _update_grid_row_style(self, field_key: str):
        """Aktualisiert Label und Stil einer bestehenden Feldzeile."""
        return self.grid_renderer.update_row_style(field_key)

    def _apply_grid_theme(self):
        """Wendet Themefarben/-stile auf alle Grid-Komponenten an."""
        return self.grid_renderer._apply_grid_theme()

    def _ensure_link_for_day(self, day_index: int, preferred_topic: str = "") -> pathlib.Path | None:
        """Stellt sicher, dass für eine Spalte eine Stunden-Datei verlinkt ist."""
        return self.editor_controller.ensure_link_for_day(day_index, preferred_topic=preferred_topic)

    def _save_cell(self, field_key: str, day_index: int):
        """High-frequency Entry: persistiert Änderungen einer einzelnen Grid-Zelle."""
        self.editor_controller.save_cell(field_key, day_index)

    def _apply_value(self, field_key: str, day_index: int, value: str):
        """Übernimmt einen Zellenwert fachkonform in Tabelle/YAML und Persistenz."""
        self.editor_controller.apply_value(field_key, day_index, value)

    def _update_selected_lesson_metrics(self):
        """Aktualisiert die Übersichtsmetriken der aktuell selektierten Unterrichtszeile."""
        selected = self.lesson_tree.focus()
        if not selected or self.current_table is None:
            return

        (
            next_theme,
            remaining_hours,
            next_lzk,
            next_ub,
            next_unit,
            _days_until_next_unit,
            _has_upcoming_unit,
            _has_any_dated_unit,
        ) = self._plan_overview_query.summarize_plan(self.current_table)
        # Schreibzugriff über Spalten-IDs statt Positionsindizes, damit neue oder
        # umsortierte Übersichtsspalten (z. B. "stufe") keine Werte verschieben.
        updates = {
            "next_topic": next_theme,
            "next_unit": next_unit,
            "remaining_hours": str(remaining_hours),
            "next_lzk": next_lzk,
            "next_ub": next_ub,
        }
        available_columns = set(self.lesson_tree["columns"])
        for column_id, value in updates.items():
            if column_id in available_columns:
                self.lesson_tree.set(selected, column_id, value)

    def _on_grid_mousewheel(self, event):
        """Delegiert Scroll-/Zoom-Interaktion des Grids an den Renderer."""
        return self.grid_renderer._on_grid_mousewheel(event)
