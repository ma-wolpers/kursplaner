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
