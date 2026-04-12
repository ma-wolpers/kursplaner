from kursplaner.adapters.gui.grid_viewport_sync import GridViewportSync


class _CanvasStub:
    def __init__(self, *, full_height: int = 1200, viewport_height: int = 300):
        self.full_height = full_height
        self.viewport_height = viewport_height
        self._y_start = 0.0
        self.calls: list[tuple] = []

    def yview(self, *args):
        if args:
            self.calls.append(("yview", *args))
            if args[0] == "moveto":
                self._y_start = float(args[1])
            return None
        span = self.viewport_height / float(self.full_height)
        return (self._y_start, min(1.0, self._y_start + span))

    def update_idletasks(self):
        return None

    def bbox(self, _window):
        return (0, 0, 800, self.full_height)

    def winfo_height(self):
        return self.viewport_height


class _AppStub:
    def __init__(self):
        self.fixed_canvas = _CanvasStub()
        self.grid_canvas = _CanvasStub()
        self.grid_window = object()


def test_yview_moveto_updates_both_canvases():
    app = _AppStub()
    sync = GridViewportSync(app)

    sync.yview_moveto(0.5)

    assert ("yview", "moveto", 0.5) in app.grid_canvas.calls
    assert ("yview", "moveto", 0.5) in app.fixed_canvas.calls


def test_yview_scroll_updates_both_canvases():
    app = _AppStub()
    sync = GridViewportSync(app)

    sync.yview_scroll(3, "units")

    assert ("yview", "scroll", 3, "units") in app.grid_canvas.calls
    assert ("yview", "scroll", 3, "units") in app.fixed_canvas.calls


def test_yview_moveto_is_clamped_to_valid_range():
    app = _AppStub()
    app.grid_canvas.full_height = 1000
    app.fixed_canvas.full_height = 1000
    app.grid_canvas.viewport_height = 400
    app.fixed_canvas.viewport_height = 400
    sync = GridViewportSync(app)

    sync.yview_moveto(0.9)

    assert ("yview", "moveto", 0.6) in app.grid_canvas.calls
    assert ("yview", "moveto", 0.6) in app.fixed_canvas.calls
