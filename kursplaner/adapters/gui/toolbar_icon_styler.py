from __future__ import annotations

from pathlib import Path
from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui

from kursplaner.adapters.gui.toolbar_viewmodel import TOOLBAR_ACTIONS
from kursplaner.adapters.gui.ui_theme import get_theme


class ToolbarIconStyler:
    """Verwaltet Toolbar-Icons inkl. Theme-Tinting und Disabled-Varianten."""

    def __init__(self, app):
        self.app = app
        self._base_icons: dict[str, ui.PhotoImage] = {}
        self._variants_by_theme: dict[str, dict[str, dict[str, ui.PhotoImage]]] = {}

    @staticmethod
    def _icon_dir() -> Path:
        return Path(__file__).resolve().parents[3] / "assets" / "toolbar"

    @staticmethod
    def _icon_file_by_action() -> dict[str, str]:
        return {
            "new": "tb_new.png",
            "refresh": "tb_refresh.png",
            "export_as": "tb_export.png",
            "undo": "tb_undo.png",
            "redo": "tb_redo.png",
            "plan": "tb_unterricht.png",
            "extend_to_vacation": "tb_extend.png",
            "ausfall": "tb_ausfall.png",
            "hospitation": "tb_hospitation.png",
            "lzk": "tb_lzk.png",
            "mark_ub": "tb_bu.png",
            "mark_ub_remove": "tb_no_ub.png",
            "copy": "tb_copy.png",
            "paste": "tb_paste.png",
            "find": "tb_find.png",
            "clear": "tb_clear.png",
            "rename": "tb_rename.png",
            "split": "tb_split.png",
            "merge": "tb_merge.png",
            "resume": "tb_resume.png",
            "move_left": "tb_move_left.png",
            "move_right": "tb_move_right.png",
        }

    @staticmethod
    def _icon_color_role_for_style(style_name: str) -> str:
        if style_name == "Action.Primary.TButton":
            return "primary"
        if style_name == "Action.Unterricht.TButton":
            return "unterricht"
        if style_name == "Action.Ausfall.TButton":
            return "ausfall"
        if style_name == "Action.Hospitation.TButton":
            return "hospitation"
        if style_name == "Action.Lzk.TButton":
            return "lzk"
        return "utility"

    @staticmethod
    def _theme_icon_colors(theme_key: str) -> dict[str, str]:
        theme = get_theme(theme_key)
        return {
            "utility": str(theme.get("fg_primary", "#222222")),
            "primary": str(theme.get("fg_on_accent", theme.get("fg_primary", "#FFFFFF"))),
            "unterricht": str(theme.get("fg_on_accent", theme.get("fg_primary", "#FFFFFF"))),
            "ausfall": str(theme.get("fg_on_warning", theme.get("fg_on_accent", "#FFFFFF"))),
            "hospitation": str(theme.get("fg_on_hospitation", theme.get("fg_on_accent", "#FFFFFF"))),
            "lzk": str(theme.get("fg_on_success", theme.get("fg_on_accent", "#FFFFFF"))),
            "disabled": str(theme.get("fg_muted", "#777777")),
        }

    @staticmethod
    def _recolor_photo(base: ui.PhotoImage, color_hex: str) -> ui.PhotoImage:
        width = int(base.width())
        height = int(base.height())
        recolored = ui.PhotoImage(width=width, height=height)
        recolored.put(color_hex, to=(0, 0, width, height))

        has_transparency = hasattr(base, "transparency_get") and hasattr(recolored, "transparency_set")
        if not has_transparency:
            return recolored

        for y in range(height):
            for x in range(width):
                try:
                    if bool(base.transparency_get(x, y)):
                        recolored.transparency_set(x, y, True)
                except ui.TclError:
                    continue
        return recolored

    def _ensure_base_icons(self) -> None:
        if self._base_icons:
            return

        icon_dir = self._icon_dir()
        icon_files = self._icon_file_by_action()
        for icon_key, filename in icon_files.items():
            if not filename:
                continue
            icon_path = icon_dir / filename
            if not icon_path.exists() or not icon_path.is_file():
                continue
            try:
                self._base_icons[icon_key] = ui.PhotoImage(file=str(icon_path))
            except ui.TclError:
                continue

    def _ensure_theme_variants(self, theme_key: str) -> dict[str, dict[str, ui.PhotoImage]]:
        if theme_key in self._variants_by_theme:
            return self._variants_by_theme[theme_key]

        self._ensure_base_icons()
        colors = self._theme_icon_colors(theme_key)

        variants: dict[str, dict[str, ui.PhotoImage]] = {}
        style_by_key = {spec.key: spec.style for spec in TOOLBAR_ACTIONS}
        style_by_key["mark_ub_remove"] = style_by_key.get("mark_ub", "Action.Utility.TButton")
        style_by_key["resume"] = style_by_key.get("ausfall", "Action.Ausfall.TButton")
        for icon_key, style_name in style_by_key.items():
            base = self._base_icons.get(icon_key)
            if base is None:
                continue
            role = self._icon_color_role_for_style(style_name)
            enabled_color = colors.get(role, colors["utility"])
            variants[icon_key] = {
                "enabled": self._recolor_photo(base, enabled_color),
                "disabled": self._recolor_photo(base, colors["disabled"]),
            }

        self._variants_by_theme[theme_key] = variants
        return variants

    def apply(self, theme_key: str | None = None) -> None:
        buttons = getattr(self.app, "action_buttons", None)
        if not isinstance(buttons, dict):
            return

        resolved_theme = str(theme_key or self.app.theme_var.get())
        variants = self._ensure_theme_variants(resolved_theme)
        self.app.toolbar_button_images = variants

        mark_ub_remove_mode = False
        ausfall_resume_mode = False
        selected_indices = sorted(int(idx) for idx in getattr(self.app, "selected_day_indices", set()))
        if len(selected_indices) == 1:
            day_columns = list(getattr(self.app, "day_columns", []))
            idx = selected_indices[0]
            if 0 <= idx < len(day_columns):
                day = day_columns[idx]
                yaml_data = day.get("yaml") if isinstance(day, dict) else {}
                if isinstance(yaml_data, dict):
                    mark_ub_remove_mode = bool(str(yaml_data.get("Unterrichtsbesuch", "")).strip())
                ausfall_resume_mode = bool(day.get("is_cancel", False)) if isinstance(day, dict) else False

        for spec in TOOLBAR_ACTIONS:
            button = buttons.get(spec.key)
            if button is None:
                continue
            icon_key = spec.key
            if spec.key == "mark_ub" and mark_ub_remove_mode and "mark_ub_remove" in variants:
                icon_key = "mark_ub_remove"
            if spec.key == "ausfall" and ausfall_resume_mode and "resume" in variants:
                icon_key = "resume"

            icon_set = variants.get(icon_key)
            if not isinstance(icon_set, dict):
                button.configure(text=spec.text, image="")
                continue
            is_disabled = bool(button.instate(["disabled"]))
            button.configure(
                image=icon_set["disabled"] if is_disabled else icon_set["enabled"],
                text="",
                compound="center",
            )
