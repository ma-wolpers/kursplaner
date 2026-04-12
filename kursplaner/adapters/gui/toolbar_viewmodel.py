from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kursplaner.adapters.gui.ui_intents import UiIntent
from kursplaner.core.usecases.action_button_state_usecase import ActionButtonState


@dataclass(frozen=True)
class ToolbarActionDefinition:
    """Deklarative Beschreibung einer Toolbar-Aktion inklusive Slot-Zuweisung."""

    key: str
    slot_key: str
    text: str
    intent: str
    style: str = "Action.Utility.TButton"
    padx: tuple[int, int] = (0, 0)
    width: int | None = None
    help_key: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolbarActionView:
    """Deklarativer Sichtbarkeits- und Aktivierungszustand einer Aktion."""

    visible: bool
    enabled: bool


@dataclass(frozen=True)
class ToolbarViewModel:
    """Gesamtes Toolbar-ViewModel als reine UI-Daten."""

    actions: dict[str, ToolbarActionView]


TOOLBAR_SLOT_ORDER: tuple[str, ...] = (
    "new",
    "refresh",
    "extend_to_vacation",
    "sep_primary",
    "undo",
    "redo",
    "sep_extend",
    "plan",
    "mark_ub",
    "ausfall",
    "hospitation",
    "lzk",
    "lzk_expected_horizon",
    "sep_secondary",
    "copy",
    "paste",
    "find",
    "clear",
    "rename",
    "split",
    "merge",
    "move_left",
    "move_right",
    "export_as",
)

TOOLBAR_SLOT_MIN_WIDTH: dict[str, int] = {
    "new": 42,
    "refresh": 42,
    "export_as": 52,
    "extend_to_vacation": 42,
    "sep_primary": 14,
    "undo": 42,
    "redo": 42,
    "plan": 42,
    "mark_ub": 42,
    "sep_extend": 14,
    "ausfall": 42,
    "hospitation": 42,
    "lzk": 42,
    "lzk_expected_horizon": 42,
    "sep_secondary": 14,
    "copy": 42,
    "paste": 42,
    "find": 42,
    "clear": 42,
    "rename": 42,
    "split": 42,
    "merge": 42,
    "move_left": 40,
    "move_right": 40,
}

TOOLBAR_SEPARATOR_SLOTS: set[str] = {"sep_primary", "sep_extend", "sep_secondary"}

TOOLBAR_ACTIONS: tuple[ToolbarActionDefinition, ...] = (
    ToolbarActionDefinition(
        key="new",
        slot_key="new",
        text="✚",
        intent=UiIntent.TOOLBAR_NEW,
        style="Action.Primary.TButton",
        width=3,
        help_key="new",
    ),
    ToolbarActionDefinition(
        key="refresh",
        slot_key="refresh",
        text="⟳",
        intent=UiIntent.TOOLBAR_REFRESH,
        width=3,
        help_key="refresh",
    ),
    ToolbarActionDefinition(
        key="export_as",
        slot_key="export_as",
        text="Exportieren als...",
        intent=UiIntent.TOOLBAR_EXPORT_AS,
        width=16,
        help_key="export_as",
    ),
    ToolbarActionDefinition(
        key="extend_to_vacation",
        slot_key="extend_to_vacation",
        text="⇢",
        intent=UiIntent.TOOLBAR_EXTEND_TO_VACATION,
        style="Action.Utility.TButton",
        width=3,
        padx=(6, 0),
        help_key="extend_to_vacation",
    ),
    ToolbarActionDefinition(
        key="undo",
        slot_key="undo",
        text="↶",
        intent=UiIntent.TOOLBAR_UNDO,
        width=3,
        padx=(0, 0),
        help_key="undo",
    ),
    ToolbarActionDefinition(
        key="redo",
        slot_key="redo",
        text="↷",
        intent=UiIntent.TOOLBAR_REDO,
        width=3,
        padx=(4, 0),
        help_key="redo",
    ),
    ToolbarActionDefinition(
        key="plan",
        slot_key="plan",
        text="⌂",
        intent=UiIntent.TOOLBAR_PLAN,
        style="Action.Unterricht.TButton",
        width=3,
        help_key="as_unterricht",
    ),
    ToolbarActionDefinition(
        key="ausfall",
        slot_key="ausfall",
        text="⊘",
        intent=UiIntent.TOOLBAR_AUSFALL,
        style="Action.Ausfall.TButton",
        width=3,
        padx=(6, 0),
        help_key="as_ausfall",
    ),
    ToolbarActionDefinition(
        key="hospitation",
        slot_key="hospitation",
        text="◎",
        intent=UiIntent.TOOLBAR_HOSPITATION,
        style="Action.Hospitation.TButton",
        width=3,
        padx=(6, 0),
        help_key="as_hospitation",
    ),
    ToolbarActionDefinition(
        key="lzk",
        slot_key="lzk",
        text="✐",
        intent=UiIntent.TOOLBAR_LZK,
        style="Action.Lzk.TButton",
        width=3,
        padx=(6, 0),
        help_key="as_lzk",
    ),
    ToolbarActionDefinition(
        key="lzk_expected_horizon",
        slot_key="lzk_expected_horizon",
        text="KH",
        intent=UiIntent.TOOLBAR_LZK_EXPECTED_HORIZON,
        style="Action.Lzk.TButton",
        width=4,
        padx=(6, 0),
        help_key="lzk_expected_horizon",
    ),
    ToolbarActionDefinition(
        key="mark_ub",
        slot_key="mark_ub",
        text="◍",
        intent=UiIntent.MARK_SELECTED_AS_UB,
        style="Action.Utility.TButton",
        width=3,
        padx=(6, 0),
        help_key="mark_ub",
    ),
    ToolbarActionDefinition(
        key="copy", slot_key="copy", text="⎘", intent=UiIntent.TOOLBAR_COPY, width=3, help_key="copy"
    ),
    ToolbarActionDefinition(
        key="paste",
        slot_key="paste",
        text="⇪",
        intent=UiIntent.TOOLBAR_PASTE,
        width=3,
        padx=(6, 0),
        help_key="paste",
    ),
    ToolbarActionDefinition(
        key="find",
        slot_key="find",
        text="⌕",
        intent=UiIntent.TOOLBAR_FIND,
        width=3,
        padx=(6, 0),
        help_key="find_markdown",
    ),
    ToolbarActionDefinition(
        key="clear",
        slot_key="clear",
        text="⌫",
        intent=UiIntent.TOOLBAR_CLEAR,
        width=3,
        padx=(6, 0),
        help_key="clear",
    ),
    ToolbarActionDefinition(
        key="rename",
        slot_key="rename",
        text="✎",
        intent=UiIntent.TOOLBAR_RENAME,
        width=3,
        padx=(6, 0),
        help_key="rename",
    ),
    ToolbarActionDefinition(
        key="split",
        slot_key="split",
        text="⇲",
        intent=UiIntent.TOOLBAR_SPLIT,
        width=3,
        padx=(6, 0),
        help_key="split",
    ),
    ToolbarActionDefinition(
        key="merge",
        slot_key="merge",
        text="⇄",
        intent=UiIntent.TOOLBAR_MERGE,
        width=3,
        padx=(6, 0),
        help_key="merge",
    ),
    ToolbarActionDefinition(
        key="move_left",
        slot_key="move_left",
        text="←",
        intent=UiIntent.TOOLBAR_MOVE_COLUMNS,
        width=3,
        padx=(12, 0),
        help_key="move_left",
        payload={"direction": -1},
    ),
    ToolbarActionDefinition(
        key="move_right",
        slot_key="move_right",
        text="→",
        intent=UiIntent.TOOLBAR_MOVE_COLUMNS,
        width=3,
        padx=(4, 0),
        help_key="move_right",
        payload={"direction": 1},
    ),
)

TOOLBAR_ACTION_BY_KEY: dict[str, ToolbarActionDefinition] = {item.key: item for item in TOOLBAR_ACTIONS}


def build_toolbar_view_model(*, action_state: ActionButtonState, can_undo: bool, can_redo: bool) -> ToolbarViewModel:
    """Erzeugt den deklarativen Toolbar-Zustand aus fachlichem Action-State."""

    visibility: dict[str, bool] = {
        "new": True,
        "refresh": True,
        "export_as": action_state.can_export_topic_pdf,
        "plan": action_state.can_plan,
        "extend_to_vacation": action_state.can_extend_to_vacation,
        "lzk": action_state.can_lzk,
        "lzk_expected_horizon": action_state.can_export_lzk_expected_horizon,
        "ausfall": action_state.can_ausfall,
        "hospitation": action_state.can_hospitation,
        "mark_ub": action_state.can_mark_ub,
        "split": action_state.can_split,
        "merge": action_state.can_merge,
        "move_left": action_state.can_move_left,
        "move_right": action_state.can_move_right,
        "clear": action_state.can_clear,
        "find": action_state.can_find,
        "copy": action_state.can_copy,
        "rename": action_state.can_copy,
        "paste": action_state.can_paste,
        "undo": can_undo,
        "redo": can_redo,
    }

    actions = {
        definition.key: ToolbarActionView(visible=True, enabled=bool(visibility.get(definition.key, True)))
        for definition in TOOLBAR_ACTIONS
    }
    return ToolbarViewModel(actions=actions)
