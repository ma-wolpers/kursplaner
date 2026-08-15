from __future__ import annotations

from pathlib import Path

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui
from bw_gui.theming import icon_button, recolor_photo, recolor_photo_token, retain_icon_override

from kursplaner.adapters.gui.toolbar_viewmodel import TOOLBAR_ACTIONS
from kursplaner.adapters.gui.ui_theme import HOSPITATION_SEED

# Maps ttk style name → bw_gui color_tint seed for icon recoloring.
# None means no tint: icon pixels are recolored to fg_primary (the neutral
# foreground) rather than to the contrast foreground of a tinted background.
_STYLE_TINT: dict[str, str | None] = {
    "Action.Primary.TButton":     "accent",
    "Action.Unterricht.TButton":  "accent",
    "Action.Ausfall.TButton":     "warning",
    "Action.Hospitation.TButton": HOSPITATION_SEED,
    "Action.Lzk.TButton":         "success",
}

# Style assigned to alternate (state-swap) icons so they receive the same
# tint as the button they replace.
_ALTERNATE_ICON_STYLE: dict[str, str] = {
    "mark_ub_remove": "Action.Unterricht.TButton",
    "resume":         "Action.Ausfall.TButton",
}


class ToolbarIconStyler:
    """Manages toolbar icon loading, tinting, and state-based icon overrides.

    Buttons are created via ``create_button()`` which delegates to bw_gui's
    ``icon_button()`` so every registered button is automatically recolored on
    every theme switch — no per-theme variant cache is required here.

    ``apply_state_overrides()`` handles the small subset of buttons whose icon
    depends on domain state (mark_ub ↔ mark_ub_remove, ausfall ↔ resume) and
    the disabled appearance (icons recolored to ``fg_muted``).  It is called
    from ``_apply_theme()`` after ``configure_ttk_theme()`` has already
    restored every registered button to its enabled icon.
    """

    def __init__(self, app):
        """Store the app reference; icon loading is deferred until first use."""
        self.app = app
        self._base_icons: dict[str, ui.PhotoImage] = {}

    @staticmethod
    def _icon_dir() -> Path:
        """Return the absolute path to the toolbar assets directory."""
        return Path(__file__).resolve().parents[3] / "assets" / "toolbar"

    @staticmethod
    def _icon_file_by_action() -> dict[str, str]:
        """Return a mapping from action key to PNG filename in the assets folder.

        Includes both primary action keys (those with toolbar specs) and the
        two alternate-state icons (mark_ub_remove, resume) that replace their
        counterparts depending on column domain state.
        """
        return {
            "new":                "tb_new.png",
            "refresh":            "tb_refresh.png",
            "export_as":          "tb_export.png",
            "undo":               "tb_undo.png",
            "redo":               "tb_redo.png",
            "plan":               "tb_unterricht.png",
            "extend_to_vacation": "tb_extend.png",
            "ausfall":            "tb_ausfall.png",
            "hospitation":        "tb_hospitation.png",
            "lzk":                "tb_lzk.png",
            "mark_ub":            "tb_bu.png",
            "mark_ub_remove":     "tb_no_ub.png",
            "copy":               "tb_copy.png",
            "paste":              "tb_paste.png",
            "find":               "tb_find.png",
            "clear":              "tb_clear.png",
            "rename":             "tb_rename.png",
            "resume":             "tb_resume.png",
            "move_left":          "tb_move_left.png",
            "move_right":         "tb_move_right.png",
        }

    def _ensure_base_icons(self) -> None:
        """Load all base (uncolored) PNG icons from disk on first call."""
        if self._base_icons:
            return
        icon_dir = self._icon_dir()
        for icon_key, filename in self._icon_file_by_action().items():
            if not filename:
                continue
            icon_path = icon_dir / filename
            if not icon_path.exists() or not icon_path.is_file():
                continue
            try:
                self._base_icons[icon_key] = ui.PhotoImage(file=str(icon_path))
            except ui.TclError:
                continue

    def create_button(self, parent, spec, command):
        """Create and return a theme-aware icon button for *spec*.

        Loads the base PNG for ``spec.key``, selects the correct tint from
        ``_STYLE_TINT``, and delegates to ``icon_button()`` so the button is
        registered for automatic recoloring on every subsequent theme switch.

        Args:
            parent:  Tk parent widget for the new button.
            spec:    Toolbar action spec providing ``key``, ``style``, ``width``.
            command: Callable invoked on button press.

        Returns:
            The created ``ttk.Button``, or ``None`` if no icon asset was found.
        """
        self._ensure_base_icons()
        base = self._base_icons.get(spec.key)
        if base is None:
            return None
        tint = _STYLE_TINT.get(spec.style)  # None → recolor to fg_primary
        kwargs: dict = {"style": spec.style}
        if spec.width is not None:
            kwargs["width"] = spec.width
        return icon_button(parent, base, command, color_tint=tint, **kwargs)

    def apply_state_overrides(self) -> None:
        """Override button icons for state-based swaps and disabled appearance.

        Called from ``_apply_theme()`` after ``configure_ttk_theme()`` has
        restored every registered icon button to its default enabled icon via
        bw_gui's internal ``_reapply_icon_buttons``.  Applies two override
        categories:

        - **State swaps**: replaces the mark_ub icon with mark_ub_remove and
          the ausfall icon with resume when the currently selected day column's
          domain state requires it.
        - **Disabled icons**: recolors to ``fg_muted`` for buttons that are
          currently in the disabled ttk state, so inactive actions appear
          visually dimmed.

        No ``theme_key`` parameter is needed — bw_gui reads the globally active
        theme internally (Principle C: theme is ambient).
        """
        buttons = getattr(self.app, "action_buttons", None)
        if not isinstance(buttons, dict):
            return

        self._ensure_base_icons()

        mark_ub_remove_mode = False
        ausfall_resume_mode = False
        selected = sorted(int(i) for i in getattr(self.app, "selected_day_indices", set()))
        if len(selected) == 1:
            day_columns = list(getattr(self.app, "day_columns", []))
            idx = selected[0]
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
            icon_style = spec.style
            if spec.key == "mark_ub" and mark_ub_remove_mode and "mark_ub_remove" in self._base_icons:
                icon_key = "mark_ub_remove"
                icon_style = _ALTERNATE_ICON_STYLE.get("mark_ub_remove", spec.style)
            elif spec.key == "ausfall" and ausfall_resume_mode and "resume" in self._base_icons:
                icon_key = "resume"
                icon_style = _ALTERNATE_ICON_STYLE.get("resume", spec.style)

            base = self._base_icons.get(icon_key)
            if base is None:
                continue

            is_disabled = bool(button.instate(["disabled"]))
            if is_disabled:
                img = recolor_photo_token(base, "fg_muted")
                retain_icon_override(button, img)
                button.configure(text="", compound="center")
            elif icon_key != spec.key:
                # State-swapped alternate icon: apply the correct tint seed
                tint = _STYLE_TINT.get(icon_style)
                if tint is not None:
                    img = recolor_photo(base, tint)
                else:
                    img = recolor_photo_token(base, "fg_primary")
                retain_icon_override(button, img)
                button.configure(text="", compound="center")
            # Normal case: _reapply_icon_buttons already applied the right color.
