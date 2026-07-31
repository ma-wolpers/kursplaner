"""Kursplaner-specific theme configuration.

Wraps bw_gui.theming for the canonical theme registry, intensity scaling, and
shared style baseline.  Domain colour computation (Hospitation purple ramp,
view-mode toggle tints, column background tints) is delegated entirely to
bw_gui's ``tinted_color`` / ``tinted_foreground`` API.  This module owns only
the domain seed constant and the two kursplaner-only themes.

``HOSPITATION_SEED`` is the single source of truth for the purple hue used in
all Hospitation lesson-type styling.  Importers that need the colour (e.g.
``grid_renderer``, ``toolbar_icon_styler``) import the constant from here and
pass it as ``mix_color`` — no colour math needed at the call site.
``configure_ttk_theme`` derives every Hospitation shade via ``tinted_color`` /
``tinted_foreground`` at switch time.

External callers import ``configure_ttk_theme``, ``apply_window_theme``,
``HOSPITATION_SEED``, ``DEFAULT_THEME``, and ``normalize_theme_key`` from this
module.  ``set_theme_intensity`` / ``get_theme_intensity`` are re-exported from
bw_gui so any future settings adapter can import them from either location.
"""

from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()

from bw_gui.runtime import ui, widgets
from bw_gui.runtime.platform import apply_window_chrome_theme
from bw_gui.theming import (
    configure_ttk_theme as _configure_base,
    get_theme as _bw_get_theme,
    get_theme_intensity,
    is_dark_color,
    normalize_theme_key as _normalize,
    register_theme,
    set_theme_intensity,
    tinted_color,
    tinted_foreground,
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


# ── Domain seed constants ────────────────────────────────────────────────────

HOSPITATION_SEED: str = "#7C3AED"
"""Purple hue seed for the Hospitation lesson type.

All Hospitation colour values are derived at switch time by bw_gui's
``tinted_color`` / ``tinted_foreground``.  Importers that need the colour
(e.g. ``grid_renderer``, ``toolbar_icon_styler``) import this constant and
pass it as ``mix_color`` — no colour math needed at the call site.
"""


# ── Public API ──────────────────────────────────────────────────────────────

def normalize_theme_key(theme_key: str | None = None) -> str:
    """Return *theme_key* if known, otherwise ``DEFAULT_THEME``.

    Delegates to bw_gui so the full 13-theme registry (plus Ledger and
    Blackforge registered above) is used for validation.

    Args:
        theme_key: Raw key string to validate; ``None`` returns ``DEFAULT_THEME``.

    Returns:
        Validated theme key string.
    """
    return _normalize(theme_key)


def apply_window_theme(window: ui.Misc, theme_key: str | None = None) -> None:
    """Set *window*'s background to ``bg_main`` and apply Windows title-bar chrome.

    Resolves the current theme via bw_gui (using the globally tracked key when
    *theme_key* is ``None``), configures the window background, and calls
    ``apply_window_chrome_theme`` so the OS title bar matches.  The chrome call
    is a no-op on non-Windows platforms.

    Args:
        window:    Tk root or top-level to configure.
        theme_key: Explicit theme override; ``None`` uses the global current theme.
    """
    theme = _bw_get_theme(theme_key)
    window.configure({"bg": theme["bg_main"]})
    apply_window_chrome_theme(window, prefer_dark=is_dark_color(str(theme["bg_main"])))


def configure_ttk_theme(root: ui.Misc, theme_key: str | None = None) -> None:  # deliberate exception: long by necessity
    """Configure the bw_gui baseline and add kursplaner-specific style overrides.

    Calls ``bw_gui.theming.configure_ttk_theme()`` first (which sets the
    globally tracked current theme), then derives Hospitation and view-mode
    colours via ``tinted_color`` / ``tinted_foreground`` and applies the
    kursplaner-specific style overrides:

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
      view-mode toggle buttons derived from ``tinted_color``.
    - ``Action.Utility/Secondary.TButton`` — neutral utility and secondary actions.
    - ``Action.Warn/Danger/Success.TButton`` — semantic colour actions.

    Args:
        root:      Tk root or top-level widget to configure styles on.
        theme_key: Theme to activate; ``None`` uses the globally tracked current theme.
    """
    _configure_base(root, theme_key)  # sets bw_gui global; tinted_color calls below use it

    # ── Hospitation domain colours (purple seed, not a bw_gui token) ──────────
    hospitation       = tinted_color(HOSPITATION_SEED, degree=0.70, base_token="bg_panel")
    hospitation_hover = tinted_color(HOSPITATION_SEED, degree=0.82, base_token="bg_panel")
    fg_on_hospitation = tinted_foreground(HOSPITATION_SEED, degree=0.70, base_token="bg_panel")

    # ── View-mode toggle button backgrounds ───────────────────────────────────
    view_unterricht_bg      = tinted_color("accent_soft",    degree=0.70, base_token="panel_strong")
    view_unterricht_active  = tinted_color("accent",         degree=0.58, base_token="panel_strong")
    view_lzk_bg             = tinted_color("success_soft",   degree=0.70, base_token="panel_strong")
    view_lzk_active         = tinted_color("success",        degree=0.58, base_token="panel_strong")
    view_ausfall_bg         = tinted_color("warning_soft",   degree=0.70, base_token="panel_strong")
    view_ausfall_active     = tinted_color("warning",        degree=0.58, base_token="panel_strong")
    view_hospitation_bg     = tinted_color(HOSPITATION_SEED, degree=0.38, base_token="panel_strong")
    view_hospitation_active = tinted_color(HOSPITATION_SEED, degree=0.58, base_token="panel_strong")

    # Standard bw_gui tokens for borders, disabled states, and solid bg colours.
    theme = _bw_get_theme(theme_key)
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
        "Action.Unterricht.TButton", background=theme["accent"],
        foreground=theme.get("fg_on_accent", theme["fg_primary"]),
        padding=(4, 2), borderwidth=1, relief="flat",
        bordercolor=button_border, lightcolor=theme["accent"], darkcolor=theme["accent"],
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.Unterricht.TButton",
        background=[("disabled", disabled_bg), ("active", theme["accent_hover"]), ("pressed", theme["accent_hover"])],
        foreground=[("disabled", disabled_fg),
                    ("active", theme.get("fg_on_accent", theme["fg_primary"])),
                    ("pressed", theme.get("fg_on_accent", theme["fg_primary"]))],
    )

    lzk_bg = str(theme.get("success", theme.get("accent", theme["bg_surface"])))
    style.configure(
        "Action.Lzk.TButton", background=lzk_bg,
        foreground=theme.get("fg_on_success", theme["fg_primary"]),
        padding=(4, 2), borderwidth=1, relief="flat",
        bordercolor=button_border, lightcolor=lzk_bg, darkcolor=lzk_bg,
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.Lzk.TButton",
        background=[("disabled", disabled_bg), ("active", lzk_bg), ("pressed", lzk_bg)],
        foreground=[("disabled", disabled_fg),
                    ("active", theme.get("fg_on_success", theme["fg_primary"])),
                    ("pressed", theme.get("fg_on_success", theme["fg_primary"]))],
    )

    style.configure(
        "Action.Hospitation.TButton", background=hospitation, foreground=fg_on_hospitation,
        padding=(4, 2), borderwidth=1, relief="flat",
        bordercolor=button_border, lightcolor=hospitation, darkcolor=hospitation,
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.Hospitation.TButton",
        background=[("disabled", disabled_bg), ("active", hospitation_hover), ("pressed", hospitation_hover)],
        foreground=[("disabled", disabled_fg), ("active", fg_on_hospitation), ("pressed", fg_on_hospitation)],
    )

    ausfall_bg = str(theme.get("warning", theme.get("accent", theme["bg_surface"])))
    style.configure(
        "Action.Ausfall.TButton", background=ausfall_bg,
        foreground=theme.get("fg_on_warning", theme["fg_primary"]),
        padding=(4, 2), borderwidth=1, relief="flat",
        bordercolor=button_border, lightcolor=ausfall_bg, darkcolor=ausfall_bg,
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.Ausfall.TButton",
        background=[("disabled", disabled_bg), ("active", ausfall_bg), ("pressed", ausfall_bg)],
        foreground=[("disabled", disabled_fg),
                    ("active", theme.get("fg_on_warning", theme["fg_primary"])),
                    ("pressed", theme.get("fg_on_warning", theme["fg_primary"]))],
    )

    style.configure(
        "Action.View.Unterricht.TButton", background=view_unterricht_bg,
        foreground=theme.get("accent_hover", theme["fg_primary"]),
        padding=(4, 2), borderwidth=1, relief="flat",
        bordercolor=button_border, lightcolor=view_unterricht_bg, darkcolor=view_unterricht_bg,
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.View.Unterricht.TButton",
        background=[("disabled", disabled_bg), ("active", view_unterricht_active),
                    ("pressed", view_unterricht_active)],
        foreground=[("disabled", disabled_fg), ("active", theme.get("fg_on_accent", theme["fg_primary"])),
                    ("pressed", theme.get("fg_on_accent", theme["fg_primary"]))],
    )

    style.configure(
        "Action.View.Lzk.TButton", background=view_lzk_bg,
        foreground=theme.get("success_hover", theme["fg_primary"]),
        padding=(4, 2), borderwidth=1, relief="flat",
        bordercolor=button_border, lightcolor=view_lzk_bg, darkcolor=view_lzk_bg,
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.View.Lzk.TButton",
        background=[("disabled", disabled_bg), ("active", view_lzk_active),
                    ("pressed", view_lzk_active)],
        foreground=[("disabled", disabled_fg), ("active", theme.get("fg_on_success", theme["fg_primary"])),
                    ("pressed", theme.get("fg_on_success", theme["fg_primary"]))],
    )

    style.configure(
        "Action.View.Ausfall.TButton", background=view_ausfall_bg,
        foreground=theme.get("warning_hover", theme["fg_primary"]),
        padding=(4, 2), borderwidth=1, relief="flat",
        bordercolor=button_border, lightcolor=view_ausfall_bg, darkcolor=view_ausfall_bg,
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.View.Ausfall.TButton",
        background=[("disabled", disabled_bg), ("active", view_ausfall_active),
                    ("pressed", view_ausfall_active)],
        foreground=[("disabled", disabled_fg), ("active", theme.get("fg_on_warning", theme["fg_primary"])),
                    ("pressed", theme.get("fg_on_warning", theme["fg_primary"]))],
    )

    style.configure(
        "Action.View.Hospitation.TButton", background=view_hospitation_bg,
        foreground=hospitation_hover,  # saturated purple label text on soft-tinted bg
        padding=(4, 2), borderwidth=1, relief="flat",
        bordercolor=button_border, lightcolor=view_hospitation_bg, darkcolor=view_hospitation_bg,
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.View.Hospitation.TButton",
        background=[("disabled", disabled_bg), ("active", view_hospitation_active),
                    ("pressed", view_hospitation_active)],
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
