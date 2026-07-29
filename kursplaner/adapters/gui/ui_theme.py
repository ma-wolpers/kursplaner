"""Kursplaner-specific theme configuration.

Wraps bw_gui.theming for the canonical theme registry, intensity scaling, and
shared style baseline.  Adds kursplaner-specific domain tokens (hospitation,
view-mode colour tints, column background tints) and registers the two
kursplaner-only themes (Ledger, Blackforge) into bw_gui at import time so
``bw_gui.theming.get_theme()`` can resolve them.

External callers import ``kursplaner_theme``, ``configure_ttk_theme``,
``apply_window_theme``, ``DEFAULT_THEME``, and ``normalize_theme_key`` from
this module unchanged.  ``set_theme_intensity`` / ``get_theme_intensity`` are
re-exported from bw_gui so any future settings adapter can import them from
either location.
"""

from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()

from bw_gui.runtime import ui, widgets
from bw_gui.runtime.platform import apply_window_chrome_theme
from bw_gui.theming import (
    configure_ttk_theme as _configure_base,
    contrast_text_color,
    get_theme as _bw_get_theme,
    get_theme_intensity,
    is_dark_color,
    mix_hex,
    normalize_theme_key as _normalize,
    register_theme,
    set_theme_intensity,
)

DEFAULT_THEME = "mono_day"

# ── Kursplaner-only themes: registered into bw_gui at import time ──────────

_LEDGER: dict[str, str] = {
    "label": "Ledger",
    "bg_main": "#F3F3F2",
    "bg_panel": "#EBECEB",
    "bg_surface": "#FFFFFF",
    "panel_strong": "#DFE1DF",
    "secondary": "#5A625A",
    "secondary_soft": "#E3E6E3",
    "fg_primary": "#171A17",
    "fg_muted": "#5A625C",
    "accent": "#1D4ED8",
    "accent_hover": "#1A43BD",
    "accent_soft": "#D8E2FA",
    "selection_bg": "#1E40AF",
    "selection_fg": "#FFFFFF",
    "info": "#0F766E",
    "info_soft": "#D4E8E5",
    "success": "#3F8F3F",
    "success_hover": "#377D37",
    "success_soft": "#DCE9DC",
    "warning": "#CA8A04",
    "warning_hover": "#B07403",
    "warning_soft": "#F3E9D2",
    "danger": "#B91C1C",
    "danger_hover": "#A51919",
    "danger_soft": "#F1DADA",
    "fg_on_accent": "#FFFFFF",
    "fg_on_success": "#FFFFFF",
    "fg_on_warning": "#1F1807",
    "fg_on_danger": "#FFFFFF",
    "fg_on_secondary": "#FFFFFF",
    "focus_ring": "#1D4ED8",
    "border": "#C0C5BF",
}

_BLACKFORGE: dict[str, str] = {
    "label": "Blackforge",
    "bg_main": "#0B0C0E",
    "bg_panel": "#121418",
    "bg_surface": "#1A1E24",
    "panel_strong": "#242A33",
    "secondary": "#7B828F",
    "secondary_soft": "#1F252E",
    "fg_primary": "#F0F3F8",
    "fg_muted": "#B8BFCC",
    "accent": "#06B6D4",
    "accent_hover": "#099FB8",
    "accent_soft": "#1E3740",
    "selection_bg": "#0891B2",
    "selection_fg": "#F2FCFF",
    "info": "#38BDF8",
    "info_soft": "#233947",
    "success": "#22C55E",
    "success_hover": "#1EAF53",
    "success_soft": "#22392F",
    "warning": "#EAB308",
    "warning_hover": "#CF9D07",
    "warning_soft": "#473B1F",
    "danger": "#F43F5E",
    "danger_hover": "#DA3954",
    "danger_soft": "#4B2830",
    "fg_on_accent": "#062127",
    "fg_on_success": "#0D2616",
    "fg_on_warning": "#2A1E05",
    "fg_on_danger": "#2D0B13",
    "fg_on_secondary": "#FFFFFF",
    "focus_ring": "#22D3EE",
    "border": "#353D49",
}

register_theme("ledger", _LEDGER, append_order=True)
register_theme("blackforge", _BLACKFORGE, append_order=True)


# ── Public API ──────────────────────────────────────────────────────────────

def normalize_theme_key(theme_key: str | None = None) -> str:
    """Return *theme_key* if known, otherwise ``DEFAULT_THEME``.

    Delegates to bw_gui so the full 13-theme registry (plus Ledger and
    Blackforge registered above) is used for validation.
    """
    return _normalize(theme_key)


def kursplaner_theme(theme_key: str | None = None) -> dict:
    """Return the fully-resolved theme dict with kursplaner domain tokens.

    Calls ``bw_gui.theming.get_theme()`` to get the base palette with intensity
    scaling already applied, then fills in the following domain-specific tokens
    that are not part of the bw_gui contract:

    - ``hospitation`` / ``hospitation_hover`` / ``hospitation_soft`` /
      ``fg_on_hospitation``: purple-tinted colour ramp for Hospitation lesson
      type.  Computed from ``bg_panel`` and a fixed purple seed if not already
      present in the bw_gui theme dict.
    - ``view_unterricht_bg`` / ``view_unterricht_active``: background colours
      for the view-mode toggle button in Unterricht state.
    - ``view_lzk_bg`` / ``view_lzk_active``: same for Lzk (written exam).
    - ``view_ausfall_bg`` / ``view_ausfall_active``: same for Ausfall (absence).
    - ``view_hospitation_bg`` / ``view_hospitation_active``: same for
      Hospitation.
    - ``column_lzk_bg`` / ``column_ausfall_bg`` / ``column_hospitation_bg``:
      slightly stronger tint used as Treeview row backgrounds for those lesson
      types in the plan grid.

    Returns a fresh dict; the bw_gui registry is not mutated.
    """
    theme = dict(_bw_get_theme(theme_key))

    neutral = str(theme.get("bg_panel", theme.get("bg_main", "#FFFFFF")))
    dark_base = is_dark_color(str(theme.get("bg_main", "#FFFFFF")))
    purple_seed = "#7C3AED"

    if "hospitation" not in theme:
        theme["hospitation"] = mix_hex(neutral, purple_seed, 0.80 if dark_base else 0.70)
    if "hospitation_hover" not in theme:
        theme["hospitation_hover"] = mix_hex(neutral, purple_seed, 0.90 if dark_base else 0.82)
    if "hospitation_soft" not in theme:
        theme["hospitation_soft"] = mix_hex(neutral, purple_seed, 0.52 if dark_base else 0.38)
    if "fg_on_hospitation" not in theme:
        theme["fg_on_hospitation"] = contrast_text_color(str(theme["hospitation"]))

    panel = str(theme.get("panel_strong", theme.get("bg_panel", theme.get("bg_main", "#FFFFFF"))))
    theme["view_unterricht_bg"] = mix_hex(panel, str(theme.get("accent_soft", panel)), 0.70)
    theme["view_unterricht_active"] = mix_hex(panel, str(theme.get("accent", panel)), 0.58)
    theme["view_lzk_bg"] = mix_hex(panel, str(theme.get("success_soft", panel)), 0.70)
    theme["view_lzk_active"] = mix_hex(panel, str(theme.get("success", panel)), 0.58)
    theme["view_ausfall_bg"] = mix_hex(panel, str(theme.get("warning_soft", panel)), 0.70)
    theme["view_ausfall_active"] = mix_hex(panel, str(theme.get("warning", panel)), 0.58)
    theme["view_hospitation_bg"] = mix_hex(panel, str(theme.get("hospitation_soft", panel)), 0.70)
    theme["view_hospitation_active"] = mix_hex(panel, str(theme.get("hospitation", panel)), 0.58)
    theme["column_lzk_bg"] = mix_hex(panel, str(theme.get("success_soft", panel)), 0.72)
    theme["column_ausfall_bg"] = mix_hex(panel, str(theme.get("warning_soft", panel)), 0.72)
    theme["column_hospitation_bg"] = mix_hex(panel, str(theme.get("hospitation_soft", panel)), 0.72)

    return theme


def apply_window_theme(window: ui.Misc, theme_key: str | None = None) -> None:
    """Set *window*'s background to ``bg_main`` and apply Windows title-bar chrome.

    The chrome call is a no-op on non-Windows platforms.
    """
    theme = kursplaner_theme(theme_key)
    window.configure({"bg": theme["bg_main"]})
    apply_window_chrome_theme(window, prefer_dark=is_dark_color(str(theme["bg_main"])))


def configure_ttk_theme(root: ui.Misc, theme_key: str | None = None) -> None:  # deliberate exception: long by necessity
    """Configure the bw_gui baseline and add kursplaner-specific style overrides.

    Calls ``bw_gui.theming.configure_ttk_theme()`` first to establish the
    shared baseline (TFrame, TLabel, TEntry, scrollbars, Treeview, action
    buttons …), then applies kursplaner additions:

    - ``Panel.TFrame`` / ``Toolbar.TFrame`` — panel_strong background used for
      side panels and toolbars.
    - ``Toolbar.TLabel`` — label on a Toolbar.TFrame background.
    - ``TLabelframe`` / ``TLabelframe.Label`` — themed group-box borders.
    - ``Toolbar.TLabelframe`` / ``Toolbar.TLabelframe.Label`` — same on toolbar
      background.
    - ``TButton`` override — compact ``padding=(4, 2)`` for the dense kursplaner
      layout; bw_gui uses ``(12, 5)``.
    - ``Action.Primary.TButton`` — full accent-colour primary action button.
    - ``Action.Unterricht/Lzk/Hospitation/Ausfall.TButton`` — fully saturated
      lesson-type action buttons.
    - ``Action.View.Unterricht/Lzk/Ausfall/Hospitation.TButton`` — softly tinted
      view-mode toggle buttons (using precomputed ``view_*_bg`` tokens).
    - ``Action.Utility/Secondary.TButton`` — neutral utility and secondary actions.
    - ``Action.Warn/Danger/Success.TButton`` — semantic colour actions.
    """
    _configure_base(root, theme_key)

    theme = kursplaner_theme(theme_key)
    style = widgets.Style(root)
    try:
        style.theme_use("clam")
    except ui.TclError:
        pass

    border = theme["border"]
    disabled_bg = str(theme.get("bg_panel", theme["bg_main"]))
    disabled_fg = str(theme.get("fg_muted", theme["fg_primary"]))
    button_border = str(theme.get("border", theme.get("panel_strong", theme["bg_panel"])))
    button_light = str(theme.get("panel_strong", theme.get("bg_panel", theme["bg_main"])))
    hospitation = str(theme["hospitation"])
    hospitation_hover = str(theme["hospitation_hover"])
    hospitation_soft = str(theme["hospitation_soft"])
    fg_on_hospitation = str(theme["fg_on_hospitation"])
    change_fg = "#111111" if is_dark_color(str(theme.get("bg_main", "#FFFFFF"))) else "#FFFFFF"

    panel_bg = str(theme.get("panel_strong", theme.get("secondary_soft", theme.get("bg_panel", theme["bg_main"]))))
    style.configure("Panel.TFrame", background=panel_bg)
    style.configure("Toolbar.TFrame", background=panel_bg)
    style.configure("Toolbar.TLabel", background=panel_bg, foreground=theme["fg_primary"])
    style.configure("TLabelframe", background=theme["bg_main"], bordercolor=border)
    style.configure("TLabelframe.Label", background=theme["bg_main"], foreground=theme["fg_primary"])
    style.configure("Toolbar.TLabelframe", background=panel_bg, bordercolor=border)
    style.configure("Toolbar.TLabelframe.Label", background=panel_bg, foreground=theme["fg_primary"])

    style.configure(
        "TButton", background=theme["accent_soft"], foreground=theme["fg_primary"],
        padding=(4, 2), borderwidth=1, relief="flat",
        bordercolor=button_border, lightcolor=button_light, darkcolor=button_light,
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "TButton",
        background=[("disabled", disabled_bg), ("active", theme["border"]), ("pressed", theme["border"])],
        foreground=[("disabled", disabled_fg)],
    )

    style.configure(
        "Action.Primary.TButton", background=theme["accent"],
        foreground=theme.get("fg_on_accent", theme["fg_primary"]),
        padding=(4, 2), borderwidth=1, relief="flat",
        bordercolor=button_border, lightcolor=theme["accent"], darkcolor=theme["accent"],
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.Primary.TButton",
        background=[("disabled", disabled_bg), ("active", theme["accent_hover"]), ("pressed", theme["accent_hover"])],
        foreground=[("disabled", disabled_fg),
                    ("active", theme.get("fg_on_accent", theme["fg_primary"])),
                    ("pressed", theme.get("fg_on_accent", theme["fg_primary"]))],
    )

    style.configure(
        "Action.Unterricht.TButton", background=theme["accent"], foreground=change_fg,
        padding=(4, 2), borderwidth=1, relief="flat",
        bordercolor=button_border, lightcolor=theme["accent"], darkcolor=theme["accent"],
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.Unterricht.TButton",
        background=[("disabled", disabled_bg), ("active", theme["accent_hover"]), ("pressed", theme["accent_hover"])],
        foreground=[("disabled", disabled_fg), ("active", change_fg), ("pressed", change_fg)],
    )

    lzk_bg = str(theme.get("success", theme.get("accent", theme["bg_surface"])))
    style.configure(
        "Action.Lzk.TButton", background=lzk_bg, foreground=change_fg,
        padding=(4, 2), borderwidth=1, relief="flat",
        bordercolor=button_border, lightcolor=lzk_bg, darkcolor=lzk_bg,
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.Lzk.TButton",
        background=[("disabled", disabled_bg), ("active", lzk_bg), ("pressed", lzk_bg)],
        foreground=[("disabled", disabled_fg), ("active", change_fg), ("pressed", change_fg)],
    )

    style.configure(
        "Action.Hospitation.TButton", background=hospitation, foreground=change_fg,
        padding=(4, 2), borderwidth=1, relief="flat",
        bordercolor=button_border, lightcolor=hospitation, darkcolor=hospitation,
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.Hospitation.TButton",
        background=[("disabled", disabled_bg), ("active", hospitation_hover), ("pressed", hospitation_hover)],
        foreground=[("disabled", disabled_fg), ("active", change_fg), ("pressed", change_fg)],
    )

    ausfall_bg = str(theme.get("warning", theme.get("accent", theme["bg_surface"])))
    style.configure(
        "Action.Ausfall.TButton", background=ausfall_bg, foreground=change_fg,
        padding=(4, 2), borderwidth=1, relief="flat",
        bordercolor=button_border, lightcolor=ausfall_bg, darkcolor=ausfall_bg,
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.Ausfall.TButton",
        background=[("disabled", disabled_bg), ("active", ausfall_bg), ("pressed", ausfall_bg)],
        foreground=[("disabled", disabled_fg), ("active", change_fg), ("pressed", change_fg)],
    )

    style.configure(
        "Action.View.Unterricht.TButton", background=theme["view_unterricht_bg"],
        foreground=theme.get("accent_hover", theme["fg_primary"]),
        padding=(4, 2), borderwidth=1, relief="flat",
        bordercolor=button_border,
        lightcolor=theme["view_unterricht_bg"], darkcolor=theme["view_unterricht_bg"],
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.View.Unterricht.TButton",
        background=[("disabled", disabled_bg), ("active", theme["view_unterricht_active"]),
                    ("pressed", theme["view_unterricht_active"])],
        foreground=[("disabled", disabled_fg), ("active", theme.get("fg_on_accent", theme["fg_primary"])),
                    ("pressed", theme.get("fg_on_accent", theme["fg_primary"]))],
    )

    style.configure(
        "Action.View.Lzk.TButton", background=theme["view_lzk_bg"],
        foreground=theme.get("success_hover", theme["fg_primary"]),
        padding=(4, 2), borderwidth=1, relief="flat",
        bordercolor=button_border,
        lightcolor=theme["view_lzk_bg"], darkcolor=theme["view_lzk_bg"],
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.View.Lzk.TButton",
        background=[("disabled", disabled_bg), ("active", theme["view_lzk_active"]),
                    ("pressed", theme["view_lzk_active"])],
        foreground=[("disabled", disabled_fg), ("active", theme.get("fg_on_success", theme["fg_primary"])),
                    ("pressed", theme.get("fg_on_success", theme["fg_primary"]))],
    )

    style.configure(
        "Action.View.Ausfall.TButton", background=theme["view_ausfall_bg"],
        foreground=theme.get("warning_hover", theme["fg_primary"]),
        padding=(4, 2), borderwidth=1, relief="flat",
        bordercolor=button_border,
        lightcolor=theme["view_ausfall_bg"], darkcolor=theme["view_ausfall_bg"],
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.View.Ausfall.TButton",
        background=[("disabled", disabled_bg), ("active", theme["view_ausfall_active"]),
                    ("pressed", theme["view_ausfall_active"])],
        foreground=[("disabled", disabled_fg), ("active", theme.get("fg_on_warning", theme["fg_primary"])),
                    ("pressed", theme.get("fg_on_warning", theme["fg_primary"]))],
    )

    style.configure(
        "Action.View.Hospitation.TButton", background=theme["view_hospitation_bg"],
        foreground=hospitation_hover,
        padding=(4, 2), borderwidth=1, relief="flat",
        bordercolor=button_border,
        lightcolor=theme["view_hospitation_bg"], darkcolor=theme["view_hospitation_bg"],
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.View.Hospitation.TButton",
        background=[("disabled", disabled_bg), ("active", theme["view_hospitation_active"]),
                    ("pressed", theme["view_hospitation_active"])],
        foreground=[("disabled", disabled_fg), ("active", fg_on_hospitation), ("pressed", fg_on_hospitation)],
    )

    style.configure(
        "Action.Utility.TButton", background=theme.get("bg_surface", theme["accent_soft"]),
        foreground=theme["fg_primary"],
        padding=(4, 2), borderwidth=1, relief="flat",
        bordercolor=button_border, lightcolor=button_light, darkcolor=button_light,
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.Utility.TButton",
        background=[("disabled", disabled_bg), ("active", button_light), ("pressed", button_light)],
        foreground=[("disabled", disabled_fg)],
    )

    style.configure(
        "Action.Secondary.TButton", background=theme.get("bg_surface", theme["accent_soft"]),
        foreground=theme["fg_primary"],
        padding=(4, 2), borderwidth=1, relief="flat",
        bordercolor=button_border, lightcolor=button_light, darkcolor=button_light,
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.Secondary.TButton",
        background=[("disabled", disabled_bg), ("active", theme["accent_soft"]), ("pressed", theme["accent_soft"])],
        foreground=[("disabled", disabled_fg)],
    )

    style.configure(
        "Action.Warn.TButton", background=theme["warning"],
        foreground=theme.get("fg_on_warning", theme["fg_primary"]),
        padding=(4, 2), borderwidth=1, relief="flat",
        bordercolor=button_border, lightcolor=theme["warning"], darkcolor=theme["warning"],
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.Warn.TButton",
        background=[("disabled", disabled_bg), ("active", theme["warning"]),
                    ("pressed", theme.get("warning_hover", theme["warning"]))],
        foreground=[("disabled", disabled_fg), ("active", theme.get("fg_on_warning", theme["fg_primary"])),
                    ("pressed", theme.get("fg_on_warning", theme["fg_primary"]))],
    )

    style.configure(
        "Action.Danger.TButton", background=theme["danger"],
        foreground=theme.get("fg_on_danger", theme["fg_primary"]),
        padding=(4, 2), borderwidth=1, relief="flat",
        bordercolor=button_border, lightcolor=theme["danger"], darkcolor=theme["danger"],
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.Danger.TButton",
        background=[("disabled", disabled_bg), ("active", theme["danger"]),
                    ("pressed", theme.get("danger_hover", theme["danger"]))],
        foreground=[("disabled", disabled_fg), ("active", theme.get("fg_on_danger", theme["fg_primary"])),
                    ("pressed", theme.get("fg_on_danger", theme["fg_primary"]))],
    )

    style.configure(
        "Action.Success.TButton", background=theme["success"],
        foreground=theme.get("fg_on_success", theme["fg_primary"]),
        padding=(4, 2), borderwidth=1, relief="flat",
        bordercolor=button_border, lightcolor=theme["success"], darkcolor=theme["success"],
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.Success.TButton",
        background=[("disabled", disabled_bg), ("active", theme["success"]),
                    ("pressed", theme.get("success_hover", theme["success"]))],
        foreground=[("disabled", disabled_fg), ("active", theme.get("fg_on_success", theme["fg_primary"])),
                    ("pressed", theme.get("fg_on_success", theme["fg_primary"]))],
    )
