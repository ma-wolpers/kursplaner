from __future__ import annotations


from bw_libs.shared_gui_core import ensure_bw_gui_on_path


ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets
try:
    from bw_gui.theming.theme_manager import THEMES as SHARED_THEMES
    from bw_gui.theming.theme_manager import THEME_ORDER as SHARED_THEME_ORDER
    from bw_gui.theming.theme_manager import configure_ttk_theme as configure_shared_ttk_theme
except ModuleNotFoundError:
    SHARED_THEMES = {}
    SHARED_THEME_ORDER = ()
    configure_shared_ttk_theme = None

THEMES = {
    "mono_day": {
        "label": "Mono Day",
        "bg_main": "#F2F3F5",
        "bg_panel": "#E9EBEF",
        "bg_surface": "#FFFFFF",
        "panel_strong": "#DDE1E7",
        "secondary": "#4A5568",
        "secondary_soft": "#E1E5EC",
        "fg_primary": "#111827",
        "fg_muted": "#4B5563",
        "accent": "#2563EB",
        "accent_hover": "#1E56CF",
        "accent_soft": "#D6E3FF",
        "selection_bg": "#1D4ED8",
        "selection_fg": "#FFFFFF",
        "info": "#0EA5E9",
        "info_soft": "#D5EEF9",
        "success": "#16A34A",
        "success_hover": "#15803D",
        "success_soft": "#D8F0DF",
        "warning": "#D97706",
        "warning_hover": "#B95F04",
        "warning_soft": "#F5E6D2",
        "danger": "#DC2626",
        "danger_hover": "#BE2020",
        "danger_soft": "#F7D9D9",
        "fg_on_accent": "#FFFFFF",
        "fg_on_success": "#FFFFFF",
        "fg_on_warning": "#1E1408",
        "fg_on_danger": "#FFFFFF",
        "fg_on_secondary": "#FFFFFF",
        "focus_ring": "#2563EB",
        "border": "#B9C0CB",
    },
    "mono_night": {
        "label": "Mono Night",
        "bg_main": "#0F1115",
        "bg_panel": "#151922",
        "bg_surface": "#1C2230",
        "panel_strong": "#252D3D",
        "secondary": "#64748B",
        "secondary_soft": "#222A39",
        "fg_primary": "#E5E7EB",
        "fg_muted": "#AAB0BD",
        "accent": "#3B82F6",
        "accent_hover": "#2F70DF",
        "accent_soft": "#213450",
        "selection_bg": "#2563EB",
        "selection_fg": "#F8FAFC",
        "info": "#22D3EE",
        "info_soft": "#1E3440",
        "success": "#22C55E",
        "success_hover": "#1FAE54",
        "success_soft": "#223D31",
        "warning": "#F59E0B",
        "warning_hover": "#D6880A",
        "warning_soft": "#463620",
        "hospitation": "#9B6BFF",
        "hospitation_hover": "#8C5AF4",
        "hospitation_soft": "#3D3160",
        "fg_on_hospitation": "#F8FAFC",
        "danger": "#EF4444",
        "danger_hover": "#D73C3C",
        "danger_soft": "#4A272C",
        "fg_on_accent": "#F8FAFC",
        "fg_on_success": "#0B2616",
        "fg_on_warning": "#2A1A05",
        "fg_on_danger": "#2A0D10",
        "fg_on_secondary": "#FFFFFF",
        "focus_ring": "#60A5FA",
        "border": "#3A4354",
    },
    "steel_morning": {
        "label": "Steel Morning",
        "bg_main": "#F4F4F5",
        "bg_panel": "#ECEDEF",
        "bg_surface": "#FFFFFF",
        "panel_strong": "#DEE1E5",
        "secondary": "#52525B",
        "secondary_soft": "#E4E6EA",
        "fg_primary": "#18181B",
        "fg_muted": "#52525B",
        "accent": "#0F766E",
        "accent_hover": "#0B645E",
        "accent_soft": "#CFECE8",
        "selection_bg": "#0F766E",
        "selection_fg": "#F8FFFE",
        "info": "#0369A1",
        "info_soft": "#D5E7F1",
        "success": "#3F8F3F",
        "success_hover": "#377D37",
        "success_soft": "#DAE9DA",
        "warning": "#CA8A04",
        "warning_hover": "#AF7803",
        "warning_soft": "#F2EACF",
        "danger": "#BE123C",
        "danger_hover": "#A90F36",
        "danger_soft": "#F2D7DF",
        "fg_on_accent": "#FFFFFF",
        "fg_on_success": "#FFFFFF",
        "fg_on_warning": "#221A06",
        "fg_on_danger": "#FFFFFF",
        "fg_on_secondary": "#FFFFFF",
        "focus_ring": "#0F766E",
        "border": "#BDC3CC",
    },
    "graphite_core": {
        "label": "Graphite Core",
        "bg_main": "#121315",
        "bg_panel": "#191B1F",
        "bg_surface": "#21252B",
        "panel_strong": "#2A2F37",
        "secondary": "#707784",
        "secondary_soft": "#242932",
        "fg_primary": "#ECEFF4",
        "fg_muted": "#AEB5C0",
        "accent": "#06B6D4",
        "accent_hover": "#089AB3",
        "accent_soft": "#203842",
        "selection_bg": "#0891B2",
        "selection_fg": "#F3FCFF",
        "info": "#38BDF8",
        "info_soft": "#213B49",
        "success": "#22C55E",
        "success_hover": "#1EAF53",
        "success_soft": "#243B30",
        "warning": "#F59E0B",
        "warning_hover": "#D8880A",
        "warning_soft": "#493A20",
        "hospitation": "#B26BFF",
        "hospitation_hover": "#A259F2",
        "hospitation_soft": "#3C2B57",
        "fg_on_hospitation": "#F8FAFC",
        "danger": "#F43F5E",
        "danger_hover": "#DA3653",
        "danger_soft": "#4A2730",
        "fg_on_accent": "#062127",
        "fg_on_success": "#0D2616",
        "fg_on_warning": "#2A1A05",
        "fg_on_danger": "#2D0B13",
        "fg_on_secondary": "#FFFFFF",
        "focus_ring": "#22D3EE",
        "border": "#3A404A",
    },
    "porcelain": {
        "label": "Porcelain",
        "bg_main": "#F8F9FA",
        "bg_panel": "#F0F2F5",
        "bg_surface": "#FFFFFF",
        "panel_strong": "#E3E7ED",
        "secondary": "#5E6470",
        "secondary_soft": "#E7EBF1",
        "fg_primary": "#111827",
        "fg_muted": "#5B6472",
        "accent": "#7C3AED",
        "accent_hover": "#6D32D2",
        "accent_soft": "#E4DAFA",
        "selection_bg": "#6D28D9",
        "selection_fg": "#FFFFFF",
        "info": "#0284C7",
        "info_soft": "#D8EAF4",
        "success": "#16A34A",
        "success_hover": "#15803D",
        "success_soft": "#DCF0E2",
        "warning": "#D97706",
        "warning_hover": "#BF6A05",
        "warning_soft": "#F6E8D5",
        "hospitation": "#6D28D9",
        "hospitation_hover": "#5B21B6",
        "hospitation_soft": "#DDD0F5",
        "fg_on_hospitation": "#FFFFFF",
        "danger": "#DB2777",
        "danger_hover": "#C0226A",
        "danger_soft": "#F7DCE9",
        "fg_on_accent": "#FFFFFF",
        "fg_on_success": "#FFFFFF",
        "fg_on_warning": "#201608",
        "fg_on_danger": "#FFFFFF",
        "fg_on_secondary": "#FFFFFF",
        "focus_ring": "#7C3AED",
        "border": "#C5CCD8",
    },
    "foglight": {
        "label": "Foglight",
        "bg_main": "#F5F6F8",
        "bg_panel": "#ECEFF3",
        "bg_surface": "#FFFFFF",
        "panel_strong": "#E1E5EB",
        "secondary": "#5B6472",
        "secondary_soft": "#E6EAF0",
        "fg_primary": "#111827",
        "fg_muted": "#5E6878",
        "accent": "#0284C7",
        "accent_hover": "#036FA8",
        "accent_soft": "#D7EAF6",
        "selection_bg": "#0369A1",
        "selection_fg": "#FFFFFF",
        "info": "#0891B2",
        "info_soft": "#D2EAF0",
        "success": "#15803D",
        "success_hover": "#136C34",
        "success_soft": "#D9EADB",
        "warning": "#B45309",
        "warning_hover": "#9C4708",
        "warning_soft": "#F0E0D3",
        "danger": "#BE123C",
        "danger_hover": "#A60F35",
        "danger_soft": "#F0D8DF",
        "fg_on_accent": "#FFFFFF",
        "fg_on_success": "#FFFFFF",
        "fg_on_warning": "#211507",
        "fg_on_danger": "#FFFFFF",
        "fg_on_secondary": "#FFFFFF",
        "focus_ring": "#0284C7",
        "border": "#C0C7D2",
    },
    "ledger": {
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
    },
    "charcoal": {
        "label": "Charcoal",
        "bg_main": "#101113",
        "bg_panel": "#171A1F",
        "bg_surface": "#1E232B",
        "panel_strong": "#282E38",
        "secondary": "#778092",
        "secondary_soft": "#242A34",
        "fg_primary": "#E8ECF3",
        "fg_muted": "#B0B8C6",
        "accent": "#3B82F6",
        "accent_hover": "#3170D9",
        "accent_soft": "#22364F",
        "selection_bg": "#2563EB",
        "selection_fg": "#F8FAFC",
        "info": "#06B6D4",
        "info_soft": "#203741",
        "success": "#22C55E",
        "success_hover": "#1FAE54",
        "success_soft": "#243B30",
        "warning": "#F59E0B",
        "warning_hover": "#D8890A",
        "warning_soft": "#473821",
        "hospitation": "#B26BFF",
        "hospitation_hover": "#A259F2",
        "hospitation_soft": "#3C2B57",
        "fg_on_hospitation": "#F8FAFC",
        "danger": "#EF4444",
        "danger_hover": "#D33D3D",
        "danger_soft": "#4A292D",
        "fg_on_accent": "#F8FAFC",
        "fg_on_success": "#0B2616",
        "fg_on_warning": "#2A1A05",
        "fg_on_danger": "#2A0D10",
        "fg_on_secondary": "#FFFFFF",
        "focus_ring": "#60A5FA",
        "border": "#3A4250",
    },
    "blackforge": {
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
        "hospitation": "#B26BFF",
        "hospitation_hover": "#A259F2",
        "hospitation_soft": "#3C2B57",
        "fg_on_hospitation": "#F8FAFC",
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
    },
}

THEME_ORDER = [
    "mono_day",
    "porcelain",
    "steel_morning",
    "foglight",
    "ledger",
    "mono_night",
    "graphite_core",
    "charcoal",
    "blackforge",
]


def _merge_shared_theme_registry() -> None:
    """Enrich local theme registry with shared theme family keys."""
    if not SHARED_THEMES:
        return

    for theme_key, values in SHARED_THEMES.items():
        THEMES.setdefault(theme_key, dict(values))

    merged_order: list[str] = []
    for theme_key in THEME_ORDER:
        if theme_key in THEMES and theme_key not in merged_order:
            merged_order.append(theme_key)

    for theme_key in SHARED_THEME_ORDER:
        if theme_key in THEMES and theme_key not in merged_order:
            merged_order.append(theme_key)

    for theme_key in THEMES:
        if theme_key not in merged_order:
            merged_order.append(theme_key)

    THEME_ORDER[:] = merged_order


_merge_shared_theme_registry()

DEFAULT_THEME = "mono_day"
THEME_INTENSITY_LEVELS: dict[str, float] = {
    "dezent": 0.5,
    "mittel": 0.75,
    "kräftig": 1.0,
}
DEFAULT_THEME_INTENSITY = "mittel"
_ACTIVE_THEME_INTENSITY = DEFAULT_THEME_INTENSITY


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    """Wandelt einen Hex-Farbwert (`#RRGGBB`) in ein RGB-Tupel um."""
    text = color.strip().lstrip("#")
    if len(text) != 6:
        return (0, 0, 0)
    return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    """Wandelt ein RGB-Tupel in einen normierten Hex-Farbwert um."""
    red, green, blue = rgb
    return f"#{max(0, min(255, red)):02X}{max(0, min(255, green)):02X}{max(0, min(255, blue)):02X}"


def _mix(color_a: str, color_b: str, ratio: float) -> str:
    """Mischt zwei Hex-Farben linear entsprechend des Anteils `ratio`."""
    ax, ay, az = _hex_to_rgb(color_a)
    bx, by, bz = _hex_to_rgb(color_b)
    weight = max(0.0, min(1.0, ratio))
    return _rgb_to_hex(
        (
            round(ax + (bx - ax) * weight),
            round(ay + (by - ay) * weight),
            round(az + (bz - az) * weight),
        )
    )


def _is_dark_color(color: str) -> bool:
    """Heuristik zur Unterscheidung dunkler/heller Hintergrundfarben."""
    red, green, blue = _hex_to_rgb(color)
    luminance = (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255.0
    return luminance < 0.45


def _auto_contrast_fg(background: str) -> str:
    """Wählt eine lesbare Vordergrundfarbe passend zum Hintergrund."""
    return "#F8FAFC" if _is_dark_color(background) else "#1F2937"


def set_theme_intensity(level: str):
    """Aktualisiert den fachlichen Zustand in dem Modul.

    Args:
        level: Eingabewert für diesen Verarbeitungsschritt.
    """
    global _ACTIVE_THEME_INTENSITY
    _ACTIVE_THEME_INTENSITY = level if level in THEME_INTENSITY_LEVELS else DEFAULT_THEME_INTENSITY


def get_theme_intensity() -> str:
    """Liefert die aktuell aktive Theme-Intensitätsstufe."""
    return _ACTIVE_THEME_INTENSITY


def _apply_intensity(theme: dict) -> dict:
    """Skaliert Akzentfarben eines Themes gemäß aktueller Intensität."""
    level = get_theme_intensity()
    strength = THEME_INTENSITY_LEVELS.get(level, THEME_INTENSITY_LEVELS[DEFAULT_THEME_INTENSITY])
    neutral = str(theme.get("bg_panel", theme.get("bg_main", "#FFFFFF")))

    adjusted = dict(theme)
    accent_keys = ["accent", "accent_hover", "accent_soft", "selection_bg", "focus_ring"]
    for key in accent_keys:
        if key in adjusted:
            adjusted[key] = _mix(neutral, str(adjusted[key]), strength)

    # Semantische Farben bleiben absichtlich farbstark, damit Themes nicht einfarbig wirken.
    semantic_strength = min(1.0, 0.7 + 0.3 * strength)
    semantic_keys = [
        "info",
        "success",
        "success_hover",
        "warning",
        "warning_hover",
        "danger",
        "danger_hover",
    ]
    for key in semantic_keys:
        if key in adjusted:
            adjusted[key] = _mix(neutral, str(adjusted[key]), semantic_strength)

    soft_semantic_keys = ["info_soft", "success_soft", "warning_soft", "danger_soft"]
    for key in soft_semantic_keys:
        if key in adjusted:
            adjusted[key] = _mix(neutral, str(adjusted[key]), min(1.0, 0.5 + 0.4 * strength))

    if "secondary" in adjusted:
        adjusted["secondary"] = _mix(neutral, str(adjusted["secondary"]), min(1.0, 0.85 * strength + 0.15))
    if "secondary_soft" in adjusted:
        adjusted["secondary_soft"] = _mix(neutral, str(adjusted["secondary_soft"]), min(1.0, 0.65 * strength + 0.2))

    return adjusted


def normalize_theme_key(theme_key: str | None = None) -> str:
    """Normalisiert einen Theme-Key auf einen gültigen Eintrag oder den Default."""
    return theme_key if theme_key in THEMES else DEFAULT_THEME


def get_theme(theme_key: str | None = None) -> dict:
    """Liefert ein Theme inklusive angewandter Intensitätsanpassung."""
    base = THEMES[normalize_theme_key(theme_key)]
    theme = _apply_intensity(base)

    neutral = str(theme.get("bg_panel", theme.get("bg_main", "#FFFFFF")))
    dark_base = _is_dark_color(str(theme.get("bg_main", "#FFFFFF")))
    success_seed = "#2FAE58"
    warning_seed = "#CC7A1A"
    purple_seed = "#7C3AED"

    if "success" not in theme:
        theme["success"] = _mix(neutral, success_seed, 0.72 if dark_base else 0.62)
    if "success_hover" not in theme:
        theme["success_hover"] = _mix(neutral, success_seed, 0.84 if dark_base else 0.74)
    if "success_soft" not in theme:
        theme["success_soft"] = _mix(neutral, success_seed, 0.44 if dark_base else 0.30)
    if "fg_on_success" not in theme:
        theme["fg_on_success"] = _auto_contrast_fg(str(theme["success"]))

    if "warning" not in theme:
        theme["warning"] = _mix(neutral, warning_seed, 0.72 if dark_base else 0.62)
    if "warning_hover" not in theme:
        theme["warning_hover"] = _mix(neutral, warning_seed, 0.84 if dark_base else 0.74)
    if "warning_soft" not in theme:
        theme["warning_soft"] = _mix(neutral, warning_seed, 0.44 if dark_base else 0.30)
    if "fg_on_warning" not in theme:
        theme["fg_on_warning"] = _auto_contrast_fg(str(theme["warning"]))

    if "hospitation" not in theme:
        theme["hospitation"] = _mix(neutral, purple_seed, 0.80 if dark_base else 0.70)
    if "hospitation_hover" not in theme:
        theme["hospitation_hover"] = _mix(neutral, purple_seed, 0.90 if dark_base else 0.82)
    if "hospitation_soft" not in theme:
        theme["hospitation_soft"] = _mix(neutral, purple_seed, 0.52 if dark_base else 0.38)
    if "fg_on_hospitation" not in theme:
        theme["fg_on_hospitation"] = _auto_contrast_fg(str(theme["hospitation"]))

    panel = str(theme.get("panel_strong", theme.get("bg_panel", theme.get("bg_main", "#FFFFFF"))))
    theme["view_unterricht_bg"] = _mix(panel, str(theme.get("accent_soft", panel)), 0.70)
    theme["view_unterricht_active"] = _mix(panel, str(theme.get("accent", panel)), 0.58)
    theme["view_lzk_bg"] = _mix(panel, str(theme.get("success_soft", panel)), 0.70)
    theme["view_lzk_active"] = _mix(panel, str(theme.get("success", panel)), 0.58)
    theme["view_ausfall_bg"] = _mix(panel, str(theme.get("warning_soft", panel)), 0.70)
    theme["view_ausfall_active"] = _mix(panel, str(theme.get("warning", panel)), 0.58)
    theme["view_hospitation_bg"] = _mix(panel, str(theme.get("hospitation_soft", panel)), 0.70)
    theme["view_hospitation_active"] = _mix(panel, str(theme.get("hospitation", panel)), 0.58)

    theme["column_lzk_bg"] = _mix(panel, str(theme.get("success_soft", panel)), 0.72)
    theme["column_ausfall_bg"] = _mix(panel, str(theme.get("warning_soft", panel)), 0.72)
    theme["column_hospitation_bg"] = _mix(panel, str(theme.get("hospitation_soft", panel)), 0.72)

    return theme


def apply_window_theme(window: ui.Misc, theme_key: str | None = None):
    """Setzt die Hintergrundfarbe des Fensters gemäß aktivem Theme."""
    theme = get_theme(theme_key)
    window.configure({"bg": theme["bg_main"]})


def configure_ttk_theme(root: ui.Misc, theme_key: str | None = None):
    """Konfiguriert ttk-Styles für Buttons, Labels, Eingaben und Treeview."""
    theme = get_theme(theme_key)

    # Shared baseline first, local styles override where Kursplaner needs custom behavior.
    if configure_shared_ttk_theme is not None:
        configure_shared_ttk_theme(root, normalize_theme_key(theme_key))

    style = widgets.Style(root)
    try:
        style.theme_use("clam")
    except ui.TclError:
        pass

    style.configure("TFrame", background=theme["bg_main"])
    style.configure(
        "Panel.TFrame",
        background=theme.get("panel_strong", theme.get("secondary_soft", theme.get("bg_panel", theme["bg_main"]))),
    )
    style.configure(
        "Toolbar.TFrame",
        background=theme.get("panel_strong", theme.get("secondary_soft", theme.get("bg_panel", theme["bg_main"]))),
    )
    style.configure("TLabel", background=theme["bg_main"], foreground=theme["fg_primary"])
    style.configure(
        "Toolbar.TLabel",
        background=theme.get("panel_strong", theme.get("secondary_soft", theme.get("bg_panel", theme["bg_main"]))),
        foreground=theme["fg_primary"],
    )
    style.configure("TLabelframe", background=theme["bg_main"], bordercolor=theme["border"])
    style.configure("TLabelframe.Label", background=theme["bg_main"], foreground=theme["fg_primary"])
    style.configure(
        "Toolbar.TLabelframe",
        background=theme.get("panel_strong", theme.get("secondary_soft", theme.get("bg_panel", theme["bg_main"]))),
        bordercolor=theme["border"],
    )
    style.configure(
        "Toolbar.TLabelframe.Label",
        background=theme.get("panel_strong", theme.get("secondary_soft", theme.get("bg_panel", theme["bg_main"]))),
        foreground=theme["fg_primary"],
    )

    disabled_bg = theme.get("bg_panel", theme["bg_main"])
    disabled_fg = theme.get("fg_muted", theme["fg_primary"])
    button_border = theme.get("border", theme.get("panel_strong", theme.get("bg_panel", theme["bg_main"])))
    button_light = theme.get("panel_strong", theme.get("bg_panel", theme["bg_main"]))
    hospitation = theme["hospitation"]
    hospitation_hover = theme["hospitation_hover"]
    hospitation_soft = theme["hospitation_soft"]
    fg_on_hospitation = theme["fg_on_hospitation"]
    change_fg = "#111111" if _is_dark_color(str(theme.get("bg_main", "#FFFFFF"))) else "#FFFFFF"

    style.configure(
        "TButton",
        background=theme["accent_soft"],
        foreground=theme["fg_primary"],
        padding=(4, 2),
        borderwidth=1,
        relief="flat",
        bordercolor=button_border,
        lightcolor=button_light,
        darkcolor=button_light,
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "TButton",
        background=[("disabled", disabled_bg), ("active", theme["border"]), ("pressed", theme["border"])],
        foreground=[("disabled", disabled_fg)],
    )

    style.configure(
        "Action.Primary.TButton",
        background=theme["accent"],
        foreground=theme.get("fg_on_accent", theme["fg_primary"]),
        padding=(4, 2),
        borderwidth=1,
        relief="flat",
        bordercolor=button_border,
        lightcolor=theme["accent"],
        darkcolor=theme["accent"],
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.Primary.TButton",
        background=[("disabled", disabled_bg), ("active", theme["accent_hover"]), ("pressed", theme["accent_hover"])],
        foreground=[
            ("disabled", disabled_fg),
            ("active", theme.get("fg_on_accent", theme["fg_primary"])),
            ("pressed", theme.get("fg_on_accent", theme["fg_primary"])),
        ],
    )

    style.configure(
        "Action.Unterricht.TButton",
        background=theme["accent"],
        foreground=change_fg,
        padding=(4, 2),
        borderwidth=1,
        relief="flat",
        bordercolor=button_border,
        lightcolor=theme["accent"],
        darkcolor=theme["accent"],
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.Unterricht.TButton",
        background=[("disabled", disabled_bg), ("active", theme["accent_hover"]), ("pressed", theme["accent_hover"])],
        foreground=[("disabled", disabled_fg), ("active", change_fg), ("pressed", change_fg)],
    )

    style.configure(
        "Action.Lzk.TButton",
        background=theme.get("success", theme.get("accent", theme["bg_surface"])),
        foreground=change_fg,
        padding=(4, 2),
        borderwidth=1,
        relief="flat",
        bordercolor=button_border,
        lightcolor=theme.get("success", theme.get("accent", theme["bg_surface"])),
        darkcolor=theme.get("success", theme.get("accent", theme["bg_surface"])),
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.Lzk.TButton",
        background=[
            ("disabled", disabled_bg),
            ("active", theme.get("success", theme.get("accent_hover", theme["accent"]))),
            ("pressed", theme.get("success", theme.get("accent_hover", theme["accent"]))),
        ],
        foreground=[("disabled", disabled_fg), ("active", change_fg), ("pressed", change_fg)],
    )

    style.configure(
        "Action.Hospitation.TButton",
        background=hospitation,
        foreground=change_fg,
        padding=(4, 2),
        borderwidth=1,
        relief="flat",
        bordercolor=button_border,
        lightcolor=hospitation,
        darkcolor=hospitation,
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.Hospitation.TButton",
        background=[("disabled", disabled_bg), ("active", hospitation_hover), ("pressed", hospitation_hover)],
        foreground=[("disabled", disabled_fg), ("active", change_fg), ("pressed", change_fg)],
    )

    style.configure(
        "Action.Ausfall.TButton",
        background=theme.get("warning", theme.get("accent", theme["bg_surface"])),
        foreground=change_fg,
        padding=(4, 2),
        borderwidth=1,
        relief="flat",
        bordercolor=button_border,
        lightcolor=theme.get("warning", theme.get("accent", theme["bg_surface"])),
        darkcolor=theme.get("warning", theme.get("accent", theme["bg_surface"])),
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.Ausfall.TButton",
        background=[
            ("disabled", disabled_bg),
            ("active", theme.get("warning", theme.get("accent_hover", theme["accent"]))),
            ("pressed", theme.get("warning", theme.get("accent_hover", theme["accent"]))),
        ],
        foreground=[("disabled", disabled_fg), ("active", change_fg), ("pressed", change_fg)],
    )

    style.configure(
        "Action.View.Unterricht.TButton",
        background=theme.get(
            "view_unterricht_bg",
            theme.get("accent_soft", theme.get("panel_strong", theme.get("bg_panel", theme["bg_main"]))),
        ),
        foreground=theme.get("accent_hover", theme.get("fg_primary", "#000000")),
        padding=(4, 2),
        borderwidth=1,
        relief="flat",
        bordercolor=button_border,
        lightcolor=theme.get(
            "view_unterricht_bg",
            theme.get("accent_soft", theme.get("panel_strong", theme.get("bg_panel", theme["bg_main"]))),
        ),
        darkcolor=theme.get(
            "view_unterricht_bg",
            theme.get("accent_soft", theme.get("panel_strong", theme.get("bg_panel", theme["bg_main"]))),
        ),
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.View.Unterricht.TButton",
        background=[
            ("disabled", disabled_bg),
            (
                "active",
                theme.get("view_unterricht_active", theme.get("accent", theme.get("accent_hover", theme["bg_panel"]))),
            ),
            (
                "pressed",
                theme.get("view_unterricht_active", theme.get("accent", theme.get("accent_hover", theme["bg_panel"]))),
            ),
        ],
        foreground=[
            ("disabled", disabled_fg),
            ("active", theme.get("fg_on_accent", theme["fg_primary"])),
            ("pressed", theme.get("fg_on_accent", theme["fg_primary"])),
        ],
    )

    style.configure(
        "Action.View.Lzk.TButton",
        background=theme.get(
            "view_lzk_bg",
            theme.get(
                "success_soft",
                theme.get("accent_soft", theme.get("panel_strong", theme.get("bg_panel", theme["bg_main"]))),
            ),
        ),
        foreground=theme.get("success_hover", theme.get("fg_primary", "#000000")),
        padding=(4, 2),
        borderwidth=1,
        relief="flat",
        bordercolor=button_border,
        lightcolor=theme.get(
            "view_lzk_bg",
            theme.get(
                "success_soft",
                theme.get("accent_soft", theme.get("panel_strong", theme.get("bg_panel", theme["bg_main"]))),
            ),
        ),
        darkcolor=theme.get(
            "view_lzk_bg",
            theme.get(
                "success_soft",
                theme.get("accent_soft", theme.get("panel_strong", theme.get("bg_panel", theme["bg_main"]))),
            ),
        ),
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.View.Lzk.TButton",
        background=[
            ("disabled", disabled_bg),
            (
                "active",
                theme.get("view_lzk_active", theme.get("success", theme.get("accent", theme["bg_panel"]))),
            ),
            (
                "pressed",
                theme.get("view_lzk_active", theme.get("success", theme.get("accent", theme["bg_panel"]))),
            ),
        ],
        foreground=[
            ("disabled", disabled_fg),
            ("active", theme.get("fg_on_success", theme.get("fg_on_accent", theme["fg_primary"]))),
            ("pressed", theme.get("fg_on_success", theme.get("fg_on_accent", theme["fg_primary"]))),
        ],
    )

    style.configure(
        "Action.View.Ausfall.TButton",
        background=theme.get(
            "view_ausfall_bg",
            theme.get(
                "warning_soft",
                theme.get("accent_soft", theme.get("panel_strong", theme.get("bg_panel", theme["bg_main"]))),
            ),
        ),
        foreground=theme.get("warning_hover", theme.get("fg_primary", "#000000")),
        padding=(4, 2),
        borderwidth=1,
        relief="flat",
        bordercolor=button_border,
        lightcolor=theme.get(
            "view_ausfall_bg",
            theme.get(
                "warning_soft",
                theme.get("accent_soft", theme.get("panel_strong", theme.get("bg_panel", theme["bg_main"]))),
            ),
        ),
        darkcolor=theme.get(
            "view_ausfall_bg",
            theme.get(
                "warning_soft",
                theme.get("accent_soft", theme.get("panel_strong", theme.get("bg_panel", theme["bg_main"]))),
            ),
        ),
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.View.Ausfall.TButton",
        background=[
            ("disabled", disabled_bg),
            (
                "active",
                theme.get("view_ausfall_active", theme.get("warning", theme.get("accent", theme["bg_panel"]))),
            ),
            (
                "pressed",
                theme.get("view_ausfall_active", theme.get("warning", theme.get("accent", theme["bg_panel"]))),
            ),
        ],
        foreground=[
            ("disabled", disabled_fg),
            ("active", theme.get("fg_on_warning", theme.get("fg_on_accent", theme["fg_primary"]))),
            ("pressed", theme.get("fg_on_warning", theme.get("fg_on_accent", theme["fg_primary"]))),
        ],
    )

    style.configure(
        "Action.View.Hospitation.TButton",
        background=theme.get("view_hospitation_bg", hospitation_soft),
        foreground=hospitation_hover,
        padding=(4, 2),
        borderwidth=1,
        relief="flat",
        bordercolor=button_border,
        lightcolor=theme.get("view_hospitation_bg", hospitation_soft),
        darkcolor=theme.get("view_hospitation_bg", hospitation_soft),
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.View.Hospitation.TButton",
        background=[
            ("disabled", disabled_bg),
            ("active", theme.get("view_hospitation_active", hospitation)),
            ("pressed", theme.get("view_hospitation_active", hospitation)),
        ],
        foreground=[("disabled", disabled_fg), ("active", fg_on_hospitation), ("pressed", fg_on_hospitation)],
    )

    style.configure(
        "Action.Utility.TButton",
        background=theme.get("bg_surface", theme["accent_soft"]),
        foreground=theme["fg_primary"],
        padding=(4, 2),
        borderwidth=1,
        relief="flat",
        bordercolor=button_border,
        lightcolor=button_light,
        darkcolor=button_light,
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.Utility.TButton",
        background=[
            ("disabled", disabled_bg),
            ("active", theme.get("panel_strong", theme.get("bg_panel", theme["bg_main"]))),
            ("pressed", theme.get("panel_strong", theme.get("bg_panel", theme["bg_main"]))),
        ],
        foreground=[("disabled", disabled_fg)],
    )

    style.configure(
        "Action.Secondary.TButton",
        background=theme.get("bg_surface", theme["accent_soft"]),
        foreground=theme["fg_primary"],
        padding=(4, 2),
        borderwidth=1,
        relief="flat",
        bordercolor=button_border,
        lightcolor=button_light,
        darkcolor=button_light,
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.Secondary.TButton",
        background=[("disabled", disabled_bg), ("active", theme["accent_soft"]), ("pressed", theme["accent_soft"])],
        foreground=[("disabled", disabled_fg)],
    )

    style.configure(
        "Action.Warn.TButton",
        background=theme["warning"],
        foreground=theme.get("fg_on_warning", theme["fg_primary"]),
        padding=(4, 2),
        borderwidth=1,
        relief="flat",
        bordercolor=button_border,
        lightcolor=theme["warning"],
        darkcolor=theme["warning"],
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.Warn.TButton",
        background=[
            ("disabled", disabled_bg),
            ("active", theme["warning"]),
            ("pressed", theme.get("warning_hover", theme["warning"])),
        ],
        foreground=[
            ("disabled", disabled_fg),
            ("active", theme.get("fg_on_warning", theme["fg_primary"])),
            ("pressed", theme.get("fg_on_warning", theme["fg_primary"])),
        ],
    )

    style.configure(
        "Action.Danger.TButton",
        background=theme["danger"],
        foreground=theme.get("fg_on_danger", theme["fg_primary"]),
        padding=(4, 2),
        borderwidth=1,
        relief="flat",
        bordercolor=button_border,
        lightcolor=theme["danger"],
        darkcolor=theme["danger"],
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.Danger.TButton",
        background=[
            ("disabled", disabled_bg),
            ("active", theme["danger"]),
            ("pressed", theme.get("danger_hover", theme["danger"])),
        ],
        foreground=[
            ("disabled", disabled_fg),
            ("active", theme.get("fg_on_danger", theme["fg_primary"])),
            ("pressed", theme.get("fg_on_danger", theme["fg_primary"])),
        ],
    )

    style.configure(
        "Action.Success.TButton",
        background=theme["success"],
        foreground=theme.get("fg_on_success", theme["fg_primary"]),
        padding=(4, 2),
        borderwidth=1,
        relief="flat",
        bordercolor=button_border,
        lightcolor=theme["success"],
        darkcolor=theme["success"],
        focuscolor=theme.get("focus_ring", theme["accent"]),
    )
    style.map(
        "Action.Success.TButton",
        background=[
            ("disabled", disabled_bg),
            ("active", theme["success"]),
            ("pressed", theme.get("success_hover", theme["success"])),
        ],
        foreground=[
            ("disabled", disabled_fg),
            ("active", theme.get("fg_on_success", theme["fg_primary"])),
            ("pressed", theme.get("fg_on_success", theme["fg_primary"])),
        ],
    )

    style.configure(
        "TEntry",
        fieldbackground=theme["bg_surface"],
        foreground=theme["fg_primary"],
        background=theme["bg_surface"],
        bordercolor=button_border,
        lightcolor=theme["bg_surface"],
        darkcolor=theme["bg_surface"],
        insertcolor=theme["fg_primary"],
    )
    style.configure(
        "TCombobox",
        fieldbackground=theme["bg_surface"],
        foreground=theme["fg_primary"],
        background=theme["bg_surface"],
        bordercolor=button_border,
        lightcolor=theme["bg_surface"],
        darkcolor=theme["bg_surface"],
        arrowcolor=theme["fg_primary"],
    )
    scroll_bg = theme.get("panel_strong", theme.get("bg_panel", theme["bg_surface"]))
    scroll_active_bg = theme.get("accent_soft", theme.get("bg_panel", theme["bg_surface"]))
    scroll_trough = theme.get("bg_surface", theme.get("bg_panel", theme["bg_main"]))

    style.configure(
        "TScrollbar",
        troughcolor=scroll_trough,
        background=scroll_bg,
        arrowcolor=theme["fg_primary"],
        bordercolor=button_border,
        lightcolor=button_border,
        darkcolor=button_border,
        gripcount=0,
    )
    style.map(
        "TScrollbar",
        background=[("active", scroll_active_bg), ("pressed", scroll_active_bg)],
        arrowcolor=[("disabled", disabled_fg)],
    )
    style.configure(
        "Horizontal.TScrollbar",
        troughcolor=scroll_trough,
        background=scroll_bg,
        arrowcolor=theme["fg_primary"],
        bordercolor=button_border,
        lightcolor=button_border,
        darkcolor=button_border,
        gripcount=0,
    )
    style.map(
        "Horizontal.TScrollbar",
        background=[("active", scroll_active_bg), ("pressed", scroll_active_bg)],
        arrowcolor=[("disabled", disabled_fg)],
    )
    style.configure(
        "Vertical.TScrollbar",
        troughcolor=scroll_trough,
        background=scroll_bg,
        arrowcolor=theme["fg_primary"],
        bordercolor=button_border,
        lightcolor=button_border,
        darkcolor=button_border,
        gripcount=0,
    )
    style.map(
        "Vertical.TScrollbar",
        background=[("active", scroll_active_bg), ("pressed", scroll_active_bg)],
        arrowcolor=[("disabled", disabled_fg)],
    )

    style.configure(
        "Treeview",
        background=theme["bg_surface"],
        foreground=theme["fg_primary"],
        fieldbackground=theme["bg_surface"],
        bordercolor=button_border,
        lightcolor=theme["bg_surface"],
        darkcolor=theme["bg_surface"],
    )
    style.map(
        "Treeview",
        background=[("selected", theme.get("selection_bg", theme["accent"]))],
        foreground=[("selected", theme.get("selection_fg", theme.get("fg_on_accent", theme["fg_primary"])))],
    )
    style.configure(
        "Treeview.Heading",
        background=theme.get("panel_strong", theme.get("secondary_soft", theme.get("bg_panel", theme["accent_soft"]))),
        foreground=theme["fg_primary"],
        bordercolor=button_border,
        lightcolor=theme.get("panel_strong", theme.get("bg_panel", theme["bg_main"])),
        darkcolor=theme.get("panel_strong", theme.get("bg_panel", theme["bg_main"])),
    )


def style_text_widget(widget: ui.Text, theme_key: str | None = None):
    """Stylt ein Tk-Textwidget mit Farben und Fokusrahmen des Themes."""
    theme = get_theme(theme_key)
    widget.configure(
        bg=theme["bg_surface"],
        fg=theme["fg_primary"],
        insertbackground=theme["fg_primary"],
        selectbackground=theme.get("selection_bg", theme["accent_soft"]),
        selectforeground=theme.get("selection_fg", theme.get("fg_on_accent", theme["fg_primary"])),
        highlightthickness=1,
        highlightbackground=theme["border"],
        highlightcolor=theme.get("focus_ring", theme["accent"]),
    )


def populate_theme_menu(view_menu: ui.Menu, theme_var: ui.StringVar, on_theme_changed):
    """Fügt alle verfügbaren Themes als Radiobuttons in ein Menü ein."""
    for theme_key in THEME_ORDER:
        view_menu.add_radiobutton(
            label=THEMES[theme_key]["label"],
            variable=theme_var,
            value=theme_key,
            command=on_theme_changed,
        )

