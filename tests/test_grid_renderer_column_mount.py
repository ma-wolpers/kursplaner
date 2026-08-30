"""Tests für `GridRenderer._reconcile_column_mounts()`/`_evict_cell_to_cold()`
(Kursplaner Item 4, Stufe 4 -- echte COLD-Eviction via `destroy()`).

Design-Klarstellung gegenüber der ursprünglichen Stufen-Beschreibung: HOT und
WARM werden hier NICHT als zwei unterscheidbare Zustände (sichtbar vs.
`grid_remove()`t) geführt, sondern als EIN gemeinsames, immer `grid()`'tes
Mount-Fenster -- der Grund ist die asynchrone, gedebouncte Reconciliation
(`HorizontalViewportSync.on_view_changed()`, Stufe 3): würde der Puffer-
Bereich `grid_remove()`t, könnte eine Spalte, die durch einen kleinen Scroll
neu ins Sichtfeld rückt, für die Dauer des Debounce-Fensters (40ms) als
leere Lücke erscheinen, da die Canvas-Sichtbarkeit unabhängig vom
`grid()`/`grid_remove()`-Zustand der Zelle ist (Spaltenbreiten sind über
`grid_columnconfigure()` fix reserviert). Alles innerhalb des Mount-Fensters
bleibt deshalb durchgängig `grid()`'t; nur ausserhalb wird jetzt echt COLD
(`destroy()`t) statt nur `grid_remove()`t -- `grid_remove()` hat ab dieser
Stufe keine Rolle mehr im Mechanismus.

Zwei Test-Ebenen:
- Reine Eviction-Szenarien (kein Remount nötig, `row_defs=[]`): mit
  Fake-Widgets, kein echter Tk-Root nötig.
- Remount-Szenarien (eine neue Zelle muss tatsächlich erzeugt werden):
  `_create_and_mount_cell()` erzeugt ein echtes `ui.Text`-Widget -- dafür
  braucht es einen echten, off-screen positionierten Tk-Root (Kartograph-
  Konvention: nicht `withdraw()`, das lässt `winfo_width()` bei 1 hängen).
"""

from __future__ import annotations

import tkinter as tk
from types import SimpleNamespace

from bw_libs.shared_gui_core import ensure_bw_gui_on_path
from kursplaner.adapters.gui.grid_renderer import GridRenderer
from kursplaner.adapters.gui.ui_state import MainWindowUiState
from kursplaner.core.usecases.row_display_mode_usecase import RowFilterSettings
from tests.day_column_factory import make_day_column

ensure_bw_gui_on_path()


class _CellSlotStub:
    def __init__(self, text: str = ""):
        self._text = text
        self.destroyed = False
        self.grid_calls = 0

    def get(self, _start, _end):
        return self._text

    def grid(self):
        self.grid_calls += 1

    def destroy(self):
        self.destroyed = True


def _renderer(
    *,
    cell_widgets: dict,
    mounted_range,
    day_columns=None,
    field_value_by_key: dict | None = None,
    pending_cell_text: dict | None = None,
    active_editor: tuple[str, int] | None = None,
    is_rebuilding: bool = False,
    row_defs: list[tuple[str, str]] | None = None,
    row_labels: dict | None = None,
) -> GridRenderer:
    renderer = object.__new__(GridRenderer)
    ui_state = MainWindowUiState()
    if active_editor is not None:
        ui_state.set_active_editor(*active_editor)
    field_value_by_key = field_value_by_key or {}
    renderer.app = SimpleNamespace(
        cell_widgets=cell_widgets,
        _is_rebuilding_grid=is_rebuilding,
        viewport_sync_h=SimpleNamespace(mounted_day_index_range=lambda: mounted_range),
        day_columns=day_columns if day_columns is not None else [],
        # Sequenzfeld-Reconciliation (Stufe 6) ist fuer diese Tests bewusst
        # inaktiv -- kein Sequenzlauf vorhanden, kein zusaetzlicher Stub-Bedarf.
        sequence_fields_visible_var=SimpleNamespace(get=lambda: False),
        topic_sequence_plans=[],
        pending_cell_text=pending_cell_text if pending_cell_text is not None else {},
        ui_state=ui_state,
        _field_value=lambda day, field_key: field_value_by_key.get((field_key, day.row_index), ""),
        row_defs=row_defs if row_defs is not None else [],
        row_labels=row_labels if row_labels is not None else {},
        row_display_mode_usecase=SimpleNamespace(
            is_linked_day=lambda _day: True,
            field_is_relevant_for_day=lambda _field_key, _day, _settings: True,
        ),
        row_filter_settings=SimpleNamespace(),
    )
    return renderer


# --- Eviction (kein Remount, row_defs=[] -> zweiter Durchlauf tut nichts) ---


def test_eviction_destroys_widget_and_removes_from_cell_widgets():
    cell = _CellSlotStub(text="unveraendert")
    day = make_day_column(row_index=0)
    renderer = _renderer(
        cell_widgets={("Stundenthema", 0): cell},
        mounted_range=(5, 7),  # Tag 0 liegt ausserhalb
        day_columns=[day],
        field_value_by_key={("Stundenthema", 0): "unveraendert"},
    )

    renderer._reconcile_column_mounts()

    assert cell.destroyed is True
    assert ("Stundenthema", 0) not in renderer.app.cell_widgets


def test_dirty_cell_is_captured_into_pending_cell_text_before_eviction():
    cell = _CellSlotStub(text="getippter, ungespeicherter Text")
    day = make_day_column(row_index=0)
    renderer = _renderer(
        cell_widgets={("Stundenthema", 0): cell},
        mounted_range=(5, 7),
        day_columns=[day],
        field_value_by_key={("Stundenthema", 0): "urspruenglicher Domain-Wert"},
    )

    renderer._reconcile_column_mounts()

    assert renderer.app.pending_cell_text[("Stundenthema", 0)] == "getippter, ungespeicherter Text"


def test_clean_cell_gets_no_pending_cell_text_entry():
    cell = _CellSlotStub(text="unveraendert")
    day = make_day_column(row_index=0)
    renderer = _renderer(
        cell_widgets={("Stundenthema", 0): cell},
        mounted_range=(5, 7),
        day_columns=[day],
        field_value_by_key={("Stundenthema", 0): "unveraendert"},
    )

    renderer._reconcile_column_mounts()

    assert renderer.app.pending_cell_text == {}


def test_eviction_clears_matching_active_editor():
    cell = _CellSlotStub(text="x")
    day = make_day_column(row_index=0)
    renderer = _renderer(
        cell_widgets={("Stundenthema", 0): cell},
        mounted_range=(5, 7),
        day_columns=[day],
        field_value_by_key={("Stundenthema", 0): "x"},
        active_editor=("Stundenthema", 0),
    )

    renderer._reconcile_column_mounts()

    assert renderer.app.ui_state.active_editor is None


def test_eviction_leaves_non_matching_active_editor_untouched():
    cell = _CellSlotStub(text="x")
    day0 = make_day_column(row_index=0)
    renderer = _renderer(
        cell_widgets={("Stundenthema", 0): cell},
        mounted_range=(5, 7),
        day_columns=[day0],
        field_value_by_key={("Stundenthema", 0): "x"},
        active_editor=("Oberthema", 3),
    )

    renderer._reconcile_column_mounts()

    assert renderer.app.ui_state.active_editor is not None
    assert renderer.app.ui_state.active_editor.field_key == "Oberthema"
    assert renderer.app.ui_state.active_editor.day_index == 3


def test_noop_when_mounted_range_is_none():
    cell = _CellSlotStub(text="x")
    renderer = _renderer(cell_widgets={("Stundenthema", 0): cell}, mounted_range=None)

    renderer._reconcile_column_mounts()

    assert cell.destroyed is False
    assert cell.grid_calls == 0


def test_noop_while_rebuild_is_in_progress():
    cell = _CellSlotStub(text="x")
    renderer = _renderer(
        cell_widgets={("Stundenthema", 0): cell},
        mounted_range=(5, 7),  # Tag 0 waere ausserhalb -> wuerde ohne Guard evictet
        is_rebuilding=True,
    )

    renderer._reconcile_column_mounts()

    assert cell.destroyed is False


def test_reconciliation_never_calls_save_or_touches_editor_controller():
    """Der App-Stub hat bewusst KEIN `save_cell`/`editor_controller`/

    `apply_value` -- ein versehentlicher Save-Aufruf wuerde mit
    `AttributeError` crashen statt still zu bestehen. Mischung aus dirty/
    clean/aktiv-editierten Zellen, um jeden Codepfad einmal zu durchlaufen.
    """
    days = [make_day_column(row_index=i) for i in range(3)]
    cells = {
        ("Stundenthema", 0): _CellSlotStub(text="dirty"),
        ("Stundenthema", 1): _CellSlotStub(text="clean"),
        ("Oberthema", 2): _CellSlotStub(text="auch dirty"),
    }
    renderer = _renderer(
        cell_widgets=cells,
        mounted_range=(10, 12),  # alle drei Tage liegen ausserhalb
        day_columns=days,
        field_value_by_key={
            ("Stundenthema", 0): "urspruenglich",
            ("Stundenthema", 1): "clean",
            ("Oberthema", 2): "urspruenglich2",
        },
        active_editor=("Stundenthema", 0),
    )

    renderer._reconcile_column_mounts()  # crasht, falls ein Persistenzpfad beruehrt wird

    assert all(cell.destroyed for cell in cells.values())
    assert renderer.app.pending_cell_text == {
        ("Stundenthema", 0): "dirty",
        ("Oberthema", 2): "auch dirty",
    }
    assert renderer.app.ui_state.active_editor is None


# --- Bereits gemountete Zelle bleibt bei erneutem Reconcile einfach sichtbar ---


def test_already_mounted_cell_inside_window_is_just_regridded_not_recreated():
    cell = _CellSlotStub(text="x")
    day = make_day_column(row_index=0)
    renderer = _renderer(
        cell_widgets={("Stundenthema", 0): cell},
        mounted_range=(0, 3),  # Tag 0 liegt INNERHALB
        day_columns=[day],
        field_value_by_key={("Stundenthema", 0): "x"},
        row_defs=[("Stundenthema", "Thema")],
        row_labels={"Stundenthema": SimpleNamespace(grid_info=lambda: {"row": 0})},
    )

    renderer._reconcile_column_mounts()

    assert cell.destroyed is False
    assert cell.grid_calls == 1
    assert renderer.app.cell_widgets[("Stundenthema", 0)] is cell  # dieselbe Instanz, kein Recreate


# --- Remount: braucht echte Widget-Erzeugung -> echter Tk-Root ---
# `tk_root`-Fixture kommt aus tests/conftest.py (session-scope, ein einziger
# Root fuer die gesamte Suite -- ein zweiter tk.Tk()-Root pro Testdatei
# schlaegt unzuverlaessig fehl, s. dortiger Docstring).


def _real_renderer_for_remount(tk_root, *, field_value: str, pending_text: str | None) -> tuple[GridRenderer, dict]:
    renderer = object.__new__(GridRenderer)
    renderer._field_help_tooltips = []
    renderer._row_layout_cache = {}
    grid_inner = tk.Frame(tk_root)
    fixed_inner = tk.Frame(tk_root)
    day = make_day_column(row_index=0)
    row_label = tk.Label(tk_root)
    row_label.grid(row=0, column=0)  # damit grid_info()["row"] == 0 real ist
    pending_cell_text = {} if pending_text is None else {("Stundenthema", 0): pending_text}
    app = SimpleNamespace(
        grid_inner=grid_inner,
        fixed_inner=fixed_inner,
        day_columns=[day],
        day_grid_columns={0: 0},
        pending_cell_text=pending_cell_text,
        cell_widgets={},
        sequence_fields_visible_var=SimpleNamespace(get=lambda: False),
        topic_sequence_plans=[],
        row_defs=[("Stundenthema", "Thema")],
        row_labels={"Stundenthema": row_label},
        row_display_mode_usecase=SimpleNamespace(
            is_linked_day=lambda _day: True,
            field_is_relevant_for_day=lambda _fk, _day, _settings: True,
            is_editable=lambda _fk, _day, _settings: True,
        ),
        row_filter_settings=RowFilterSettings(),
        _field_value=lambda _day, _field_key: field_value,
        _estimate_visual_lines=lambda _text: 1,
        row_expanded={},
        expand_long_rows_var=SimpleNamespace(get=lambda: False),
        preview_font=("Segoe UI", 10),
        preview_font_size=10,
        collapsed_row_lines=1,
        day_column_width=260,
        _handle_ui_intent=lambda *a, **kw: None,
        _on_grid_mousewheel=lambda _event: None,
        ui_state=MainWindowUiState(),
        _is_rebuilding_grid=False,
        viewport_sync_h=SimpleNamespace(mounted_day_index_range=lambda: (0, 0)),
    )
    renderer.app = app
    return renderer, app


def test_remount_seeds_widget_from_pending_cell_text_when_present(tk_root):
    renderer, app = _real_renderer_for_remount(tk_root, field_value="Domain-Wert", pending_text="Ungespeichert!")

    renderer._reconcile_column_mounts()

    cell = app.cell_widgets[("Stundenthema", 0)]
    assert cell.get("1.0", "end-1c") == "Ungespeichert!"


def test_remount_uses_domain_value_when_no_pending_text(tk_root):
    renderer, app = _real_renderer_for_remount(tk_root, field_value="Domain-Wert", pending_text=None)

    renderer._reconcile_column_mounts()

    cell = app.cell_widgets[("Stundenthema", 0)]
    assert cell.get("1.0", "end-1c") == "Domain-Wert"


def test_full_round_trip_dirty_text_survives_cold_eviction_and_remount(tk_root):
    """End-zu-Ende: tippen (Widget-Text weicht vom Domain-Wert ab), aus dem

    Sichtbereich scrollen (COLD-Eviction faengt den Text ab), zurueckscrollen
    (Remount stellt ihn wieder her) -- der eigentliche Zweck von Stufe 4, als
    durchgehender Zyklus statt nur in Einzelteilen getestet (Pflichttest laut
    Plan: "ungespeicherte Eingabe uebersteht COLD-Eviction").
    """
    renderer, app = _real_renderer_for_remount(tk_root, field_value="Domain-Wert", pending_text=None)

    # 1. Initiales Mounten (Tag 0 im Fenster) -- Widget zeigt den Domain-Wert.
    app.viewport_sync_h = SimpleNamespace(mounted_day_index_range=lambda: (0, 0))
    renderer._reconcile_column_mounts()
    original_cell = app.cell_widgets[("Stundenthema", 0)]
    assert original_cell.get("1.0", "end-1c") == "Domain-Wert"

    # 2. "Tippen": Widget-Text weicht jetzt ab, ohne dass committet wurde.
    original_cell.delete("1.0", "end")
    original_cell.insert("1.0", "Frisch getippt, nicht gespeichert")

    # 3. Wegscrollen: Tag 0 faellt aus dem Fenster -> COLD-Eviction.
    app.viewport_sync_h = SimpleNamespace(mounted_day_index_range=lambda: (5, 7))
    renderer._reconcile_column_mounts()
    assert ("Stundenthema", 0) not in app.cell_widgets
    assert app.pending_cell_text[("Stundenthema", 0)] == "Frisch getippt, nicht gespeichert"

    # 4. Zurueckscrollen: Tag 0 wieder im Fenster -> Remount aus pending_cell_text.
    app.viewport_sync_h = SimpleNamespace(mounted_day_index_range=lambda: (0, 0))
    renderer._reconcile_column_mounts()
    remounted_cell = app.cell_widgets[("Stundenthema", 0)]
    assert remounted_cell.get("1.0", "end-1c") == "Frisch getippt, nicht gespeichert"
    assert remounted_cell is not original_cell  # neues Widget, aber Inhalt blieb erhalten
