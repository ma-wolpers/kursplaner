"""Einheitsvorschau im Kursgitter (Strg+D): Panel rechts, folgt der Auswahl.

Das Panel (bw-gui `ResizableSideOverlay` mit `ZoomableDocText`) wird per
``place()`` in eine eigene rechte Spalte des Editor-Rahmens gelegt; deren
``minsize`` folgt live der Panelbreite (`on_resize` am Panel). Dadurch wird
das Grid schmaler statt verdeckt – die Scroll- und Sichtbarkeitslogik des
Grids bleibt unverändert, jede Spalte bleibt erreichbar.

Auslöser zum Neuladen, alle über ``after_idle`` zusammengefasst:
* jeder Auswahlwechsel (`MainWindowUiState.add_selection_listener`),
* jede Neuberechnung der Plan-Spalten (`on_plan_changed`, aus
  `overview_controller._publish_sequence_plans`): Inhalt kann sich geändert haben.
Bei einem reinen Auswahlwechsel auf dieselbe Datei wird nicht neu gelesen.
Breite und Schriftgröße bleiben über Neustarts erhalten (`ui_preferences_store`).
"""

from __future__ import annotations

from typing import Any

from bw_gui.runtime import ui
from bw_gui.runtime.widget_events import on_resize
from bw_gui.widgets import ResizableSideOverlay, ZoomableDocText

from kursplaner.adapters.gui.unit_preview_events import (
    NO_UNIT_DOCUMENT,
    NO_UNIT_SELECTED,
    PREVIEW_TITLE,
    message_events,
    preview_events,
)
from kursplaner.core.config.ui_preferences_store import (
    UnitPreviewSettings,
    load_unit_preview_settings,
    save_unit_preview_settings,
)

PREVIEW_COLUMN = 3
"""Spalte des Editor-Rahmens, die das Panel reserviert (0–2: Zeilenköpfe, Grid, Scrollbar)."""

_UNLOADED = object()
"""Marker für „noch nichts gezeigt“ – ungleich jedem Anzeige-Schlüssel ``(Pfad, ohne_Auswahl)``."""


class UnitPreviewController:
    """Besitzt das Vorschau-Panel und hält es synchron zur Grid-Auswahl.

    Args:
        app: Hauptfenster (``ui_state``, ``day_columns``, ``selection_controller``,
            ``gui_dependencies.load_unit_preview_usecase``).
        host: Editor-Rahmen des Grids; das Panel liegt in seiner Spalte
            `PREVIEW_COLUMN`.
    """

    def __init__(self, app: Any, host: ui.Misc) -> None:
        self.app = app
        self.host = host
        self._overlay: ResizableSideOverlay | None = None
        self._doc: ZoomableDocText | None = None
        self._shown_key: object = _UNLOADED
        self._after_id: str | None = None
        self._force_next = False
        self._settings = load_unit_preview_settings()
        app.ui_state.add_selection_listener(self.on_selection_changed)

    @property
    def is_open(self) -> bool:
        """Ob das Panel gerade sichtbar ist."""
        return self._overlay is not None and self._overlay.is_visible

    def toggle(self) -> None:
        """Öffnet bzw. schließt die Vorschau (Strg+D, Menü)."""
        if self.is_open:
            self.close()
        else:
            self.open()

    def open(self) -> None:
        """Zeigt das Panel und lädt die Einheit der aktuellen Auswahl."""
        overlay = self._ensure_panel()
        overlay.show()
        self._reserve_column(overlay.effective_width())
        self._schedule(force=True)

    def close(self) -> None:
        """Blendet das Panel aus und gibt dem Grid die volle Breite zurück."""
        if self._overlay is not None and self._overlay.is_visible:
            self._overlay.hide()
        self._reserve_column(0)

    def on_selection_changed(self) -> None:
        """Auswahl-Listener: lädt nach, falls eine andere Einheit gewählt ist."""
        if self.is_open:
            self._schedule(force=False)

    def on_plan_changed(self) -> None:
        """Plan-Spalten neu berechnet: Inhalt kann sich geändert haben, also neu lesen."""
        if self.is_open:
            self._schedule(force=True)

    def _ensure_panel(self) -> ResizableSideOverlay:
        if self._overlay is not None:
            return self._overlay
        overlay = ResizableSideOverlay(
            self.host,
            title=PREVIEW_TITLE,
            width=self._settings.width,
            on_close=self.close,
            on_width_changed=self._remember_width,
        )
        doc = ZoomableDocText(overlay.content, base_size=self._settings.zoom, on_zoom_changed=self._remember_zoom)
        doc.pack(fill="both", expand=True)
        on_resize(overlay, lambda event: self._reserve_column(event.width) if overlay.is_visible else None)
        self._overlay, self._doc = overlay, doc
        return overlay

    def _reserve_column(self, width: int) -> None:
        self.host.columnconfigure(PREVIEW_COLUMN, minsize=max(0, int(width)))

    def _schedule(self, *, force: bool) -> None:
        self._force_next = self._force_next or force
        if self._after_id is None:
            self._after_id = self.app.after_idle(self._run_scheduled)

    def _run_scheduled(self) -> None:
        self._after_id = None
        force, self._force_next = self._force_next, False
        if self.is_open:
            self.refresh(force=force)

    def refresh(self, *, force: bool = False) -> None:
        """Rendert die Einheit der aktuellen Auswahl; ohne ``force`` nur bei anderem Pfad/Platzhalter."""
        index = self._focused_day_index()
        path = None if index is None else self.app.day_columns[index].link
        shown_key = (path, index is None)
        if not force and shown_key == self._shown_key:
            return
        self._shown_key = shown_key
        if self._doc is None or self._overlay is None:
            return
        if path is None:
            self._overlay.set_title(PREVIEW_TITLE)
            self._doc.render(message_events(NO_UNIT_SELECTED if index is None else NO_UNIT_DOCUMENT))
            return
        preview = self.app.gui_dependencies.load_unit_preview_usecase.execute(path)
        self._overlay.set_title(preview.title)
        self._doc.render(preview_events(preview))

    def _focused_day_index(self) -> int | None:
        cell = self.app.ui_state.selected_cell
        if cell is not None and 0 <= cell.day_index < len(self.app.day_columns):
            return cell.day_index
        return self.app.selection_controller.single_selected()

    def _remember_width(self, width: int) -> None:
        self._settings = UnitPreviewSettings(width=width, zoom=self._settings.zoom)
        save_unit_preview_settings(self._settings)

    def _remember_zoom(self, zoom: int) -> None:
        self._settings = UnitPreviewSettings(width=self._settings.width, zoom=zoom)
        save_unit_preview_settings(self._settings)
