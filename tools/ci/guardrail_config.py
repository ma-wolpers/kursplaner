# line-limit: data-only
"""Kursplaner-Guardrails: Konfiguration (Pfade, Pflicht-Snippets, Prozessregeln).

Reine Daten; die Logik liegt in den Geschwistermodulen von ``check_ai_guardrails.py``."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


GUARDRAIL_RELEVANT_PATHS = {
    "AGENTS.md",
    ".github/copilot-instructions.md",
    ".github/workflows/repo-path-guardrails.yml",
    "docs/DEVELOPMENT_LOG.md",
    "docs/GUI_MIGRATION_BACKLOG.md",
    "docs/ARCHITEKTUR_KERN.md",
    "docs/ARCHITEKTUR_UMSETZUNGSPLAN.md",
    "kursplaner/adapters/gui/main_window.py",
    "kursplaner/adapters/gui/screen_builder.py",
    "kursplaner/adapters/gui/_screen_key_handlers.py",
    "kursplaner/adapters/gui/_screen_menus.py",
    "kursplaner/adapters/gui/_screen_shortcuts.py",
    "kursplaner/adapters/gui/_screen_shortcut_debug.py",
    "kursplaner/adapters/gui/_screen_toolbar.py",
    "kursplaner/adapters/gui/hover_tooltip.py",
    "kursplaner/core/config/path_store.py",
    "kursplaner/core/usecases/daily_course_log_usecase.py",
    "kursplaner/infrastructure/repositories/lesson_index_repository.py",
    "bw_libs/ui_contract/keybinding.py",
    "bw_libs/ui_contract/popup.py",
    "bw_libs/ui_contract/hsm.py",
    "bw_libs/ui_contract/laufkern.py",
    "bw_libs/app_paths.py",
    "tools/ci/check_ai_guardrails.py",
    "tools/ci/guardrail_config.py",
    "tools/ci/guardrail_support.py",
    "tools/ci/guardrail_process.py",
    "tools/ci/guardrail_checks.py",
    "tools/ci/guardrail_gui_checks.py",
    "tools/repo_ci/check_no_absolute_paths.py",
}


PROCESS_GUIDANCE_RULES = {
    "feature_commit": "Feature-Aenderungen werden in eigenstaendigen Commits",
    "manual_push": "Push erfolgt manuell",
}


SHORTCUT_COVERAGE_SOFT_CHECKS = (
    {
        "label": "open-settings",
        "intent_paths": (
            "kursplaner/adapters/gui/ui_intents.py",
            "kursplaner/adapters/gui/screen_builder.py",
        ),
        "intent_markers": (
            "OPEN_SETTINGS",
            "app.open_settings",
            "command=lambda: self._emit_intent(UiIntent.OPEN_SETTINGS)",
        ),
        "shortcut_paths": (
            "kursplaner/adapters/gui/screen_builder.py",
            "kursplaner/resources/shortcuts/shortcut_guide.json",
        ),
        "shortcut_markers": (
            "<Control-comma>",
            "<Control-,>",
            "Strg+,",
        ),
    },
    {
        "label": "toolbar-new",
        "intent_paths": ("kursplaner/adapters/gui/ui_intents.py",),
        "intent_markers": ("TOOLBAR_NEW", "toolbar.new"),
        "shortcut_paths": ("kursplaner/resources/shortcuts/shortcut_guide.json",),
        "shortcut_markers": ("\"intent\": \"toolbar.new\"",),
    },
    {
        "label": "toolbar-export-as",
        "intent_paths": ("kursplaner/adapters/gui/ui_intents.py",),
        "intent_markers": ("TOOLBAR_EXPORT_AS", "toolbar.export_as"),
        "shortcut_paths": ("kursplaner/resources/shortcuts/shortcut_guide.json",),
        "shortcut_markers": ("\"intent\": \"toolbar.export_as\"",),
    },
    {
        "label": "toolbar-undo",
        "intent_paths": ("kursplaner/adapters/gui/ui_intents.py",),
        "intent_markers": ("TOOLBAR_UNDO", "toolbar.undo"),
        "shortcut_paths": ("kursplaner/resources/shortcuts/shortcut_guide.json",),
        "shortcut_markers": ("\"intent\": \"toolbar.undo\"",),
    },
    {
        "label": "toolbar-redo",
        "intent_paths": ("kursplaner/adapters/gui/ui_intents.py",),
        "intent_markers": ("TOOLBAR_REDO", "toolbar.redo"),
        "shortcut_paths": ("kursplaner/resources/shortcuts/shortcut_guide.json",),
        "shortcut_markers": ("\"intent\": \"toolbar.redo\"",),
    },
    {
        "label": "shortcut-copy",
        "intent_paths": ("kursplaner/adapters/gui/ui_intents.py",),
        "intent_markers": ("SHORTCUT_COPY", "shortcut.copy"),
        "shortcut_paths": ("kursplaner/resources/shortcuts/shortcut_guide.json",),
        "shortcut_markers": ("\"intent\": \"shortcut.copy\"",),
    },
    {
        "label": "shortcut-cut",
        "intent_paths": ("kursplaner/adapters/gui/ui_intents.py",),
        "intent_markers": ("SHORTCUT_CUT", "shortcut.cut"),
        "shortcut_paths": ("kursplaner/resources/shortcuts/shortcut_guide.json",),
        "shortcut_markers": ("\"intent\": \"shortcut.cut\"",),
    },
    {
        "label": "shortcut-paste",
        "intent_paths": ("kursplaner/adapters/gui/ui_intents.py",),
        "intent_markers": ("SHORTCUT_PASTE", "shortcut.paste"),
        "shortcut_paths": ("kursplaner/resources/shortcuts/shortcut_guide.json",),
        "shortcut_markers": ("\"intent\": \"shortcut.paste\"",),
    },
    {
        "label": "shortcut-escape",
        "intent_paths": ("kursplaner/adapters/gui/ui_intents.py",),
        "intent_markers": ("SHORTCUT_ESCAPE", "shortcut.escape"),
        "shortcut_paths": ("kursplaner/adapters/gui/screen_builder.py", "kursplaner/adapters/gui/_screen_shortcuts.py"),
        "shortcut_markers": ("intent=UiIntent.SHORTCUT_ESCAPE", "<Escape>"),
    },
)


CHANGELOG_RELEVANT_PREFIXES = (
    "kursplaner/adapters/gui/",
    "kursplaner/core/usecases/",
    "bw_libs/",
)


CHANGELOG_CODEV_RELEVANT_PATHS = {
    "AGENTS.md",
    ".github/copilot-instructions.md",
    ".github/pull_request_template.md",
    "tools/ci/check_ai_guardrails.py",
    "tools/ci/guardrail_config.py",
    "tools/ci/guardrail_support.py",
    "tools/ci/guardrail_process.py",
    "tools/ci/guardrail_checks.py",
    "tools/ci/guardrail_gui_checks.py",
    "docs/GUI_MIGRATION_BACKLOG.md",
    "bw_libs/ui_contract/keybinding.py",
    "bw_libs/ui_contract/popup.py",
    "bw_libs/ui_contract/hsm.py",
    "bw_libs/ui_contract/laufkern.py",
    "bw_libs/app_paths.py",
}


LAUFKERN_BRIDGE_PATH = "bw_libs/ui_contract/laufkern.py"


LAUFKERN_FALLBACK_SCAN_ROOTS = ("kursplaner", "bw_libs")


DOCSTRING_REQUIRED_PATHS = {
    "tools/ci/check_ai_guardrails.py",
    "tools/ci/guardrail_config.py",
    "tools/ci/guardrail_support.py",
    "tools/ci/guardrail_process.py",
    "tools/ci/guardrail_checks.py",
    "tools/ci/guardrail_gui_checks.py",
    "kursplaner/adapters/gui/main_window.py",
    "kursplaner/infrastructure/repositories/lesson_index_repository.py",
}


FUTURE_GUI_SEARCH_ROOTS = (
    "kursplaner/adapters/gui",
)


FUTURE_GUI_ENTRY_FILE_NAMES = {
    "main_window.py",
    "ui.py",
    "blatt_ui.py",
    "screen_builder.py",
}


FUTURE_GUI_ENTRY_BASELINES: set[str] = set()


FUTURE_GUI_REQUIRED_SHARED_SNIPPETS = (
    "ensure_bw_gui_on_path()",
    "from bw_gui.runtime import",
    "from bw_gui.menu import",
    "open_tabbed_settings_dialog",
    "compose_hover_text",
    "HoverTooltip",
)


GUI_CONTRACT_SCAN_ROOTS = (*FUTURE_GUI_SEARCH_ROOTS, "bw_libs")


UI_BASECLASS_MODULE_ALIASES = {"ui", "widgets", "tui"}


LEGACY_UI_BASECLASS_ALLOWLIST: set[str] = set()


SHARED_PRIMITIVE_CLASS_NAMES = {"TkRootHost", "ScrollablePopupWindow", "WrappedTextField"}


SHARED_PRIMITIVE_CLASS_ALLOWLIST = {
    "kursplaner/adapters/gui/popup_window.py:ScrollablePopupWindow",
}


GUI_MIGRATION_BACKLOG_PATH = "docs/GUI_MIGRATION_BACKLOG.md"


SCREEN_BUILDER_PATH = "kursplaner/adapters/gui/screen_builder.py"


SCREEN_BUILDER_MIXIN_GLOB = "kursplaner/adapters/gui/_screen_*.py"
