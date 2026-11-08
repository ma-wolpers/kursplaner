"""Gemeinsames Warnbanner an einem echten Tk-Root: ein-/ausblenden und Theme-Wechsel (synthetisch)."""

from __future__ import annotations

from bw_gui.runtime import ui
from bw_gui.theming import configure_ttk_theme, tinted_color

from kursplaner.adapters.gui.warning_banner import WarningBanner


def _warning_bg(theme_key: str) -> str:
    return tinted_color("warning_soft", degree=1.0, base_token="warning_soft", theme_key=theme_key)


def test_banner_shows_each_message_with_prefix_and_hides_without(root):
    frame = ui.Frame(root)
    frame.pack()
    banner = WarningBanner(frame)
    banner.show(["Erste", "", "Zweite"])
    root.update_idletasks()
    assert banner.label.winfo_manager() == "pack"
    assert banner.label.cget("text") == "⚠ Erste\n⚠ Zweite"
    banner.show(None)
    assert banner.label.winfo_manager() == ""
    frame.destroy()


def test_banner_follows_theme_switch(root):
    configure_ttk_theme(root, "mono_day")
    banner = WarningBanner(root)
    banner.show("Hinweis")
    assert banner.label.cget("bg").upper() == _warning_bg("mono_day").upper()
    configure_ttk_theme(root, "mono_night")
    assert banner.label.cget("bg").upper() == _warning_bg("mono_night").upper()
    configure_ttk_theme(root, "mono_day")
    banner.label.destroy()
