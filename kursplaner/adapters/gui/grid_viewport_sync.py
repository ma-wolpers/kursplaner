from __future__ import annotations


class GridViewportSync:
    """Zentrale Authority fuer vertikale Viewport-Synchronisation im Detail-Grid."""

    def __init__(self, app):
        self.app = app

    def yview(self, *args) -> None:
        """Wendet einen vertikalen Scroll-Befehl synchron auf fixe und Grid-Spalte an."""
        self.app.fixed_canvas.yview(*args)
        self.app.grid_canvas.yview(*args)

    def yview_scroll(self, units: int, what: str = "units") -> None:
        """Scrollt beide vertikalen Canvases um dieselbe Anzahl Einheiten/Seiten."""
        self.yview("scroll", int(units), what)

    def yview_moveto(self, fraction: float) -> None:
        """Setzt die gemeinsame Y-Position beider Canvases robust geclamped."""
        clamped = self._clamp_fraction(float(fraction))
        self.yview("moveto", clamped)

    def yview_range(self) -> tuple[float, float]:
        """Liefert den aktuellen Y-Viewport (start, end) aus dem Grid-Canvas."""
        start, end = self.app.grid_canvas.yview()
        return float(start), float(end)

    def clamp_current_view(self) -> None:
        """Re-clamped den aktuellen gemeinsamen Y-Viewport nach Layout-Aenderungen."""
        start, _end = self.yview_range()
        self.yview_moveto(start)

    def _clamp_fraction(self, fraction: float) -> float:
        """Begrenzt Ziel-Fraction auf den gueltigen Bereich der aktuellen Scrollregion."""
        self.app.grid_canvas.update_idletasks()
        bbox = self.app.grid_canvas.bbox(self.app.grid_window)
        if bbox is None:
            return min(max(fraction, 0.0), 1.0)

        full_height = max(1, int(bbox[3] - bbox[1]))
        viewport_height = max(1, int(self.app.grid_canvas.winfo_height()))
        max_start = max(0.0, 1.0 - (viewport_height / float(full_height)))
        return min(max(fraction, 0.0), max_start)


class HorizontalViewportSync:
    """Zentrale Authority fuer horizontale Viewport-Synchronisation im Detail-Grid.

    Stufe 1 der geplanten Viewport-Virtualisierung (Kursplaner Item 4): reine
    Sichtbereichs-Logik ohne Mount/Unmount-Verhalten -- ``mount_window()``/
    ``mounted_day_index_range()`` werden hier bewusst noch nicht verwendet,
    das folgt erst mit der eigentlichen Virtualisierung. Diese Klasse
    zentralisiert nur, was bisher auf drei Stellen verstreut war
    (``grid_renderer.py::_on_horizontal_scroll``, ein inline-Closure in
    ``screen_builder.py``, ``selection_controller.py::ensure_column_visible()``'s
    direkter ``xview_moveto()``-Aufruf) -- analog zu ``GridViewportSync`` für
    die vertikale Achse, deren Zentralisierung bereits durch
    ``tests/test_vertical_scroll_architecture_guard.py`` erzwungen wird.
    """

    def __init__(self, app):
        self.app = app
        self._reconcile_after_id: str | None = None

    def xview(self, *args) -> None:
        """Wendet einen horizontalen Scroll-Befehl synchron auf Header und Grid-Spalte an."""
        self.app.header_canvas.xview(*args)
        self.app.grid_canvas.xview(*args)

    def xview_scroll(self, units: int, what: str = "units") -> None:
        """Scrollt beide horizontalen Canvases um dieselbe Anzahl Einheiten/Seiten."""
        self.xview("scroll", int(units), what)

    def xview_moveto(self, fraction: float) -> None:
        """Setzt die gemeinsame X-Position beider Canvases robust geclamped."""
        clamped = self._clamp_fraction(float(fraction))
        self.xview("moveto", clamped)

    def xview_range(self) -> tuple[float, float]:
        """Liefert den aktuellen X-Viewport (start, end) aus dem Grid-Canvas."""
        start, end = self.app.grid_canvas.xview()
        return float(start), float(end)

    def on_view_changed(self, first: float, last: float) -> None:
        """xscrollcommand-Callback des Grid-Canvas: haelt Scrollbar und Header synchron.

        Tk ruft das bei jeder horizontalen Positionsaenderung auf, unabhaengig
        von der Quelle (Drag, Scrollbar-Klick, Mausrad, ein programmatischer
        ``xview_moveto()``) -- der zentrale Punkt, an dem eine spaetere
        Virtualisierungsstufe das Mount-Fenster neu berechnen wuerde.
        """
        self.app.x_scroll.set(first, last)
        self.app.header_canvas.xview_moveto(first)
        self._schedule_mount_reconciliation()

    def _schedule_mount_reconciliation(self, delay_ms: int = 40) -> None:
        """Debounced Aufruf von ``grid_renderer._reconcile_column_mounts()``.

        Reine Zellen-Sichtbarkeitsänderung (``grid()``/``grid_remove()``,
        s. ``_reconcile_column_mounts()``-Docstring) -- löst nie einen Save
        aus. Ein schneller Drag-Scroll feuert ``on_view_changed()`` viele
        Male pro Sekunde; ohne Debounce würde jeder Tick synchron über die
        gesamte ``cell_widgets``-Map laufen. Analog zu
        ``GridRenderer._schedule_zoom_rebuild()``.
        """
        if self._reconcile_after_id is not None:
            try:
                self.app.after_cancel(self._reconcile_after_id)
            except Exception:
                pass
            self._reconcile_after_id = None
        self._reconcile_after_id = self.app.after(delay_ms, self._run_scheduled_mount_reconciliation)

    def _run_scheduled_mount_reconciliation(self) -> None:
        """Führt die geplante Mount-Fenster-Reconciliation aus und löscht die Pending-ID."""
        self._reconcile_after_id = None
        self.app.grid_renderer._reconcile_column_mounts()

    def visible_day_index_range(self) -> tuple[int, int] | None:
        """Berechnet die aktuell sichtbaren Tages-Indizes aus der X-Viewport-Fraction.

        Reine Funktion von ``xview_range()`` + ``app.day_column_x_positions``
        + ``app.day_column_width`` -- dieselbe Pixel-Quelle, die
        ``ensure_column_visible()`` (``selection_controller.py``) bereits
        nutzt, kein neuer Zustand. Liefert ``None``, solange das Grid noch
        nicht aufgebaut ist (leere Positions-Map) oder noch keine reale
        Geometrie hat (``bbox()`` ist ``None`` vor dem ersten Layout-Pass).
        """
        x_positions = getattr(self.app, "day_column_x_positions", {})
        if not x_positions:
            return None
        self.app.grid_canvas.update_idletasks()
        bbox = self.app.grid_canvas.bbox(self.app.grid_window)
        if bbox is None:
            return None

        full_width = max(1, int(bbox[2] - bbox[0]))
        x_start, x_end = self.xview_range()
        visible_start_px = x_start * full_width
        visible_end_px = x_end * full_width

        visible_indices = [
            day_index
            for day_index, x_pos in x_positions.items()
            if x_pos + self.app.day_column_width > visible_start_px and x_pos < visible_end_px
        ]
        if not visible_indices:
            return None
        return min(visible_indices), max(visible_indices)

    def mount_window(self, buffer_columns: int = 3) -> tuple[int, int] | None:
        """Erweitert ``visible_day_index_range()`` um einen Puffer (HOT+WARM),
        geklemmt auf den gueltigen ``day_columns``-Bereich.

        Noch ungenutzt (s. Klassendocstring) -- ``buffer_columns=3`` ist der
        im Plan festgelegte Standardwert fuer die spaetere Virtualisierung,
        hier bereits als Parameter statt Konstante, damit er dort nicht
        nochmal neu verdrahtet werden muss.
        """
        visible = self.visible_day_index_range()
        if visible is None:
            return None
        day_count = len(getattr(self.app, "day_columns", []))
        if day_count == 0:
            return None
        lo, hi = visible
        return max(0, lo - buffer_columns), min(day_count - 1, hi + buffer_columns)

    def mounted_day_index_range(self) -> tuple[int, int] | None:
        """Aktuell identisch zu ``mount_window()`` -- kein Caching noetig,
        solange nichts dieses Fenster fuer echtes Mount/Unmount konsumiert."""
        return self.mount_window()

    def _clamp_fraction(self, fraction: float) -> float:
        """Begrenzt Ziel-Fraction auf den gueltigen Bereich der aktuellen Scrollregion."""
        self.app.grid_canvas.update_idletasks()
        bbox = self.app.grid_canvas.bbox(self.app.grid_window)
        if bbox is None:
            return min(max(fraction, 0.0), 1.0)

        full_width = max(1, int(bbox[2] - bbox[0]))
        viewport_width = max(1, int(self.app.grid_canvas.winfo_width()))
        max_start = max(0.0, 1.0 - (viewport_width / float(full_width)))
        return min(max(fraction, 0.0), max_start)
