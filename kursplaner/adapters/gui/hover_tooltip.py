from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path


ensure_bw_gui_on_path()
try:
    from bw_gui.widgets.hover_tooltip import HoverTooltip as HoverTooltip
except ModuleNotFoundError:
    class HoverTooltip:  # type: ignore[no-redef]
        """No-op fallback when shared GUI core is unavailable."""

        def __init__(self, widget, text: str, **_kwargs):
            self.widget = widget
            self.text = str(text or "").strip()

        def bind_widget(self, widget):
            return None
