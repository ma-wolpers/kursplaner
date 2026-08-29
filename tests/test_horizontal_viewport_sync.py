"""Tests für `HorizontalViewportSync` (Kursplaner Item 4, Stufe 1 -- reine
Sichtbereichs-Logik, noch kein Mount/Unmount-Verhalten).

Folgt demselben Stub-Stil wie `test_grid_viewport_sync.py` für die bereits
bestehende vertikale `GridViewportSync`.
"""

from kursplaner.adapters.gui.grid_viewport_sync import HorizontalViewportSync


class _CanvasStub:
    def __init__(self, *, full_width: int = 2600, viewport_width: int = 600):
        self.full_width = full_width
        self.viewport_width = viewport_width
        self._x_start = 0.0
        self.calls: list[tuple] = []

    def xview(self, *args):
        if args:
            self.calls.append(("xview", *args))
            if args[0] == "moveto":
                self._x_start = float(args[1])
            return None
        span = self.viewport_width / float(self.full_width)
        return (self._x_start, min(1.0, self._x_start + span))

    def xview_moveto(self, fraction):
        self.calls.append(("xview_moveto", fraction))
        self._x_start = float(fraction)

    def update_idletasks(self):
        return None

    def bbox(self, _window):
        return (0, 0, self.full_width, 600)

    def winfo_width(self):
        return self.viewport_width


class _ScrollbarStub:
    def __init__(self):
        self.set_calls: list[tuple] = []

    def set(self, first, last):
        self.set_calls.append((first, last))


class _AppStub:
    def __init__(self, *, day_count: int = 10, day_column_width: int = 260):
        self.header_canvas = _CanvasStub()
        self.grid_canvas = _CanvasStub()
        self.grid_window = object()
        self.x_scroll = _ScrollbarStub()
        self.day_column_width = day_column_width
        self.day_column_x_positions = {i: i * day_column_width for i in range(day_count)}
        self.day_columns = list(range(day_count))


def test_xview_moveto_updates_both_canvases():
    app = _AppStub()
    sync = HorizontalViewportSync(app)

    sync.xview_moveto(0.5)

    assert ("xview", "moveto", 0.5) in app.header_canvas.calls
    assert ("xview", "moveto", 0.5) in app.grid_canvas.calls


def test_xview_scroll_updates_both_canvases():
    app = _AppStub()
    sync = HorizontalViewportSync(app)

    sync.xview_scroll(2, "units")

    assert ("xview", "scroll", 2, "units") in app.header_canvas.calls
    assert ("xview", "scroll", 2, "units") in app.grid_canvas.calls


def test_xview_moveto_is_clamped_to_valid_range():
    app = _AppStub()
    app.grid_canvas.full_width = 1000
    app.grid_canvas.viewport_width = 400

    sync = HorizontalViewportSync(app)
    sync.xview_moveto(0.9)

    assert ("xview", "moveto", 0.6) in app.grid_canvas.calls


def test_xview_range_reads_from_grid_canvas():
    app = _AppStub()
    app.grid_canvas.full_width = 1000
    app.grid_canvas.viewport_width = 400
    app.grid_canvas._x_start = 0.2
    sync = HorizontalViewportSync(app)

    start, end = sync.xview_range()

    assert start == 0.2
    assert round(end, 6) == 0.6


def test_on_view_changed_syncs_scrollbar_and_header():
    app = _AppStub()
    sync = HorizontalViewportSync(app)

    sync.on_view_changed(0.1, 0.4)

    assert app.x_scroll.set_calls == [(0.1, 0.4)]
    assert ("xview_moveto", 0.1) in app.header_canvas.calls


def test_visible_day_index_range_returns_none_before_layout():
    app = _AppStub()
    app.day_column_x_positions = {}  # Grid noch nicht aufgebaut
    sync = HorizontalViewportSync(app)

    assert sync.visible_day_index_range() is None


def test_visible_day_index_range_matches_viewport_fraction():
    app = _AppStub(day_count=20, day_column_width=260)
    app.grid_canvas.full_width = 20 * 260  # 5200
    app.grid_canvas.viewport_width = 600
    app.grid_canvas._x_start = 0.0  # zeigt Spalten 0..~2 (600/260 ~= 2.3)
    sync = HorizontalViewportSync(app)

    visible = sync.visible_day_index_range()

    assert visible == (0, 2)


def test_visible_day_index_range_shifts_with_scroll_position():
    app = _AppStub(day_count=20, day_column_width=260)
    app.grid_canvas.full_width = 20 * 260
    app.grid_canvas.viewport_width = 600
    app.grid_canvas._x_start = 0.5  # Spalte 10 (2600px) liegt im Zentrum
    sync = HorizontalViewportSync(app)

    visible = sync.visible_day_index_range()

    assert visible is not None
    lo, hi = visible
    assert lo <= 10 <= hi


def test_mount_window_adds_buffer_and_clamps_to_day_range():
    app = _AppStub(day_count=10, day_column_width=260)
    app.grid_canvas.full_width = 10 * 260
    app.grid_canvas.viewport_width = 260  # genau eine Spalte sichtbar
    app.grid_canvas._x_start = 0.0  # Spalte 0 sichtbar
    sync = HorizontalViewportSync(app)

    window = sync.mount_window(buffer_columns=3)

    # visible ~= (0, 0), Puffer 3 -> (-3, 3) geklemmt auf [0, 9]
    assert window == (0, 3)


def test_mount_window_returns_none_without_day_columns():
    app = _AppStub(day_count=0)
    app.day_column_x_positions = {}
    sync = HorizontalViewportSync(app)

    assert sync.mount_window() is None


def test_mounted_day_index_range_matches_mount_window():
    app = _AppStub(day_count=10, day_column_width=260)
    app.grid_canvas.full_width = 10 * 260
    app.grid_canvas.viewport_width = 260
    app.grid_canvas._x_start = 0.0
    sync = HorizontalViewportSync(app)

    assert sync.mounted_day_index_range() == sync.mount_window()
