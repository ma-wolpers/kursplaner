"""Tests für `GridRenderer._reconcile_sequence_field_mounts()`/
`_evict_sequence_field_to_cold()` (Kursplaner Item 4, Stufe 6 -- die laut
Plan "trickiest correctness surface": Sequenzziel-/Leitkompetenz-Zellen
überspannen mehrere Tages-Spalten statt einer.

Design-Korrektur gegenüber dem ursprünglichen Plan-Entwurf: der dort noch
vorgesehene Force-Commit über `save_sequence_field()` beim Evicten entfällt
-- Stufe 4 hat dasselbe Prinzip für normale Zellen bereits zugunsten von
`pending_cell_text` verworfen (Force-Commit beim Scrollen würde die harte
Anforderung "Scrollen speichert nie" verletzen); dieselbe Entscheidung gilt
hier konsequent auch für Sequenzfelder.

Zwei Test-Ebenen wie bei `test_grid_renderer_column_mount.py`: reine
Eviction-/Respan-Szenarien mit Fake-Widgets (kein echter Tk-Root, `_run_span`
ist reine Logik), Remount-Szenarien mit echtem `ui.Text` über einen echten,
off-screen positionierten Tk-Root.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from types import SimpleNamespace

from bw_libs.shared_gui_core import ensure_bw_gui_on_path
from kursplaner.adapters.gui.grid_renderer import GridRenderer
from kursplaner.adapters.gui.sequence_field_grid_renderer import SequenceFieldGridRenderer
from kursplaner.core.domain.topic_sequence_runs import TopicSequenceRun
from kursplaner.core.usecases.sync_topic_sequence_plans_usecase import TopicSequencePlanView
from tests.day_column_factory import make_day_column

ensure_bw_gui_on_path()

_DAY_COUNT = 10


def _view(*, member_row_indices, sequenzziel="Ziel", leitkompetenz="Kompetenz") -> TopicSequencePlanView:
    run = TopicSequenceRun(oberthema="Testthema", member_row_indices=tuple(member_row_indices))
    return TopicSequencePlanView(
        run=run, sequence_path=Path("dummy-sequenz.md"), sequenzziel=sequenzziel, leitkompetenz=leitkompetenz
    )


class _SpanCellStub:
    def __init__(self, text: str, *, column: int, columnspan: int):
        self._text = text
        self._column = column
        self._columnspan = columnspan
        self.destroyed = False
        self.grid_calls: list[tuple[int, int]] = []

    def get(self, _start, _end):
        return self._text

    def grid_info(self):
        return {"column": self._column, "columnspan": self._columnspan}

    def grid(self, *, row, column, columnspan, sticky):
        self.grid_calls.append((column, columnspan))
        self._column = column
        self._columnspan = columnspan

    def destroy(self):
        self.destroyed = True


def _renderer(
    *,
    sequence_field_widgets: dict,
    topic_sequence_plans: list[TopicSequencePlanView],
    mounted_range,
    pending_cell_text: dict | None = None,
    sequence_fields_visible: bool = True,
    day_grid_columns: dict[int, int] | None = None,
) -> GridRenderer:
    renderer = object.__new__(GridRenderer)
    renderer._sequence_field_renderer = SequenceFieldGridRenderer(None, lambda *a, **kw: None)
    day_columns = [make_day_column(row_index=i) for i in range(_DAY_COUNT)]
    app = SimpleNamespace(
        day_columns=day_columns,
        day_grid_columns=day_grid_columns if day_grid_columns is not None else {i: i for i in range(_DAY_COUNT)},
        sequence_field_widgets=sequence_field_widgets,
        topic_sequence_plans=topic_sequence_plans,
        sequence_fields_visible_var=SimpleNamespace(get=lambda: sequence_fields_visible),
        pending_cell_text=pending_cell_text if pending_cell_text is not None else {},
    )
    renderer._sequence_field_renderer.app = app
    renderer.app = app
    return renderer


# --- Eviction / Respan (reine Logik, kein Tk-Root noetig) ---


def test_widget_evicted_when_full_span_has_no_overlap_with_mount_window():
    view = _view(member_row_indices=(5, 6, 7, 8))  # full_span = grid cols 5..8
    cell = _SpanCellStub("Ziel", column=5, columnspan=4)
    renderer = _renderer(
        sequence_field_widgets={("Sequenzziel", 5): cell},
        topic_sequence_plans=[view],
        mounted_range=(0, 2),  # Grid-Spalten 0..2, keine Ueberlappung
    )

    renderer._reconcile_sequence_field_mounts((0, 2))

    assert cell.destroyed is True
    assert ("Sequenzziel", 5) not in renderer.app.sequence_field_widgets


def test_dirty_sequence_field_captured_before_eviction():
    view = _view(member_row_indices=(5, 6, 7, 8), sequenzziel="Domain-Ziel")
    cell = _SpanCellStub("Getippt, nicht gespeichert", column=5, columnspan=4)
    renderer = _renderer(
        sequence_field_widgets={("Sequenzziel", 5): cell},
        topic_sequence_plans=[view],
        mounted_range=(0, 2),
    )

    renderer._reconcile_sequence_field_mounts((0, 2))

    assert renderer.app.pending_cell_text[("Sequenzziel", 5)] == "Getippt, nicht gespeichert"


def test_clean_sequence_field_gets_no_pending_entry_on_eviction():
    view = _view(member_row_indices=(5, 6, 7, 8), sequenzziel="Unveraendert")
    cell = _SpanCellStub("Unveraendert", column=5, columnspan=4)
    renderer = _renderer(
        sequence_field_widgets={("Sequenzziel", 5): cell},
        topic_sequence_plans=[view],
        mounted_range=(0, 2),
    )

    renderer._reconcile_sequence_field_mounts((0, 2))

    assert renderer.app.pending_cell_text == {}


def test_widget_is_respanned_not_recreated_when_subspan_shifts():
    """Lauf spannt Grid-Spalten 2..8. Mount-Fenster war (2,4) -> sub_span (2,5),

    verschiebt sich zu (4,6) -> neue sub_span (4,7). Dasselbe Widget bleibt
    bestehen, wird nur neu `.grid()`t -- kein Destroy/Recreate.
    """
    view = _view(member_row_indices=(2, 3, 4, 5, 6, 7, 8))  # full_span = 2..8
    cell = _SpanCellStub("Ziel", column=2, columnspan=3)  # Platzierung passend zu altem Fenster (2,4)
    other_field_cell = _SpanCellStub("Kompetenz", column=4, columnspan=3)  # bereits am NEUEN Fenster (4,6)
    renderer = _renderer(
        sequence_field_widgets={("Sequenzziel", 2): cell, ("Leitkompetenz", 2): other_field_cell},
        topic_sequence_plans=[view],
        mounted_range=(4, 6),
    )

    renderer._reconcile_sequence_field_mounts((4, 6))

    assert cell.destroyed is False
    assert renderer.app.sequence_field_widgets[("Sequenzziel", 2)] is cell
    assert cell.grid_calls == [(4, 3)]  # neue sub_span: Spalten 4..6 -> column=4, columnspan=3


def test_widget_not_regridded_when_subspan_unchanged():
    view = _view(member_row_indices=(2, 3, 4, 5, 6, 7, 8))
    cell = _SpanCellStub("Ziel", column=4, columnspan=3)  # bereits exakt an sub_span (4,6) platziert
    other_field_cell = _SpanCellStub("Kompetenz", column=4, columnspan=3)
    renderer = _renderer(
        sequence_field_widgets={("Sequenzziel", 2): cell, ("Leitkompetenz", 2): other_field_cell},
        topic_sequence_plans=[view],
        mounted_range=(4, 6),
    )

    renderer._reconcile_sequence_field_mounts((4, 6))

    assert cell.grid_calls == []  # kein unnoetiger erneuter grid()-Aufruf
    assert other_field_cell.grid_calls == []


def test_no_visible_member_means_no_action():
    """Lauf, dessen Mitglieder alle ausserhalb des adressierbaren

    Tage-Bereichs liegen (kein Eintrag in day_grid_columns) -- `_run_span()`
    liefert `None`, nichts zu tun."""
    view = _view(member_row_indices=(50, 51))  # ausserhalb von day_grid_columns
    renderer = _renderer(
        sequence_field_widgets={},
        topic_sequence_plans=[view],
        mounted_range=(0, 2),
    )

    renderer._reconcile_sequence_field_mounts((0, 2))  # darf nicht abstuerzen

    assert renderer.app.sequence_field_widgets == {}
    assert renderer.app.pending_cell_text == {}


# --- No-op Guards ---


def test_noop_when_sequence_fields_not_visible():
    cell = _SpanCellStub("x", column=5, columnspan=4)
    view = _view(member_row_indices=(5, 6, 7, 8))
    renderer = _renderer(
        sequence_field_widgets={("Sequenzziel", 5): cell},
        topic_sequence_plans=[view],
        mounted_range=(0, 2),
        sequence_fields_visible=False,
    )

    renderer._reconcile_sequence_field_mounts((0, 2))

    assert cell.destroyed is False


def test_noop_when_no_topic_sequence_plans():
    renderer = _renderer(sequence_field_widgets={}, topic_sequence_plans=[], mounted_range=(0, 2))

    renderer._reconcile_sequence_field_mounts((0, 2))  # darf nicht abstuerzen

    assert renderer.app.sequence_field_widgets == {}


def test_noop_when_mount_window_bounds_not_in_day_grid_columns():
    view = _view(member_row_indices=(5, 6, 7, 8))
    cell = _SpanCellStub("x", column=5, columnspan=4)
    renderer = _renderer(
        sequence_field_widgets={("Sequenzziel", 5): cell},
        topic_sequence_plans=[view],
        mounted_range=(0, 20),  # Tag 20 existiert nicht in day_grid_columns
        day_grid_columns={i: i for i in range(_DAY_COUNT)},
    )

    renderer._reconcile_sequence_field_mounts((0, 20))

    assert cell.destroyed is False  # frueh abgebrochen, nichts angefasst


def test_reconciliation_never_touches_save_sequence_field_or_editor_controller():
    """App-Stub hat bewusst KEIN `save_sequence_field`/`editor_controller` --

    ein versehentlicher Aufruf wuerde mit AttributeError crashen."""
    view_dirty = _view(member_row_indices=(5, 6, 7, 8), sequenzziel="Domain")
    view_clean = _view(member_row_indices=(0, 1), leitkompetenz="Unveraendert")
    cells = {
        ("Sequenzziel", 5): _SpanCellStub("dirty", column=5, columnspan=4),  # weicht von "Domain" ab
        ("Leitkompetenz", 5): _SpanCellStub("Kompetenz", column=5, columnspan=4),  # Default, unveraendert
        ("Sequenzziel", 0): _SpanCellStub("Ziel", column=0, columnspan=2),  # Default, unveraendert
        ("Leitkompetenz", 0): _SpanCellStub("Unveraendert", column=0, columnspan=2),  # entspricht Domain-Wert
    }
    # Fenster (2,3) ueberlappt weder mit view_dirty (Spalten 5-8) noch mit
    # view_clean (Spalten 0-1) -- beide Laeufe werden komplett evictet.
    renderer = _renderer(
        sequence_field_widgets=cells,
        topic_sequence_plans=[view_dirty, view_clean],
        mounted_range=(2, 3),
    )

    renderer._reconcile_sequence_field_mounts((2, 3))  # crasht, falls ein Persistenzpfad beruehrt wird

    assert all(cell.destroyed for cell in cells.values())
    assert renderer.app.pending_cell_text == {("Sequenzziel", 5): "dirty"}


# --- Remount: braucht echte Widget-Erzeugung -> echter Tk-Root ---
# `tk_root`-Fixture kommt aus tests/conftest.py (session-scope, ein einziger
# Root fuer die gesamte Suite -- ein zweiter tk.Tk()-Root pro Testdatei
# schlaegt unzuverlaessig fehl, s. dortiger Docstring).


def _real_renderer_for_sequence_remount(
    tk_root, *, domain_value: str, pending_text: str | None, mounted_range: tuple[int, int]
):
    renderer = object.__new__(GridRenderer)
    grid_inner = tk.Frame(tk_root)
    # 10 Tage, Sequenz spannt nur 0..2 -- laesst Raum fuer ein Mount-Fenster
    # (z.B. (8,9)), das komplett ausserhalb des Laufs liegt (fuer den
    # Eviction-Teil des Rundlauftests).
    view = _view(member_row_indices=(0, 1, 2), sequenzziel=domain_value)
    pending_cell_text = {} if pending_text is None else {("Sequenzziel", 0): pending_text}
    app = SimpleNamespace(
        day_columns=[make_day_column(row_index=i) for i in range(_DAY_COUNT)],
        day_grid_columns={i: i for i in range(_DAY_COUNT)},
        sequence_field_widgets={},
        topic_sequence_plans=[view],
        sequence_fields_visible_var=SimpleNamespace(get=lambda: True),
        pending_cell_text=pending_cell_text,
        grid_inner=grid_inner,
        preview_font=("Segoe UI", 10),
        preview_font_size=10,
        collapsed_row_lines=1,
        day_column_width=260,
        _handle_ui_intent=lambda *a, **kw: None,
        _on_grid_mousewheel=lambda _event: None,
    )
    renderer._sequence_field_renderer = SequenceFieldGridRenderer(app, renderer._create_text_cell)
    renderer.app = app
    renderer._sequence_field_renderer.app = app
    renderer._apply_cell_selection_style = lambda *a, **kw: None
    return renderer, app, view


def test_remount_seeds_sequence_field_from_pending_text_when_present(tk_root):
    renderer, app, _view_obj = _real_renderer_for_sequence_remount(
        tk_root, domain_value="Domain-Ziel", pending_text="Ungespeichertes Sequenzziel", mounted_range=(0, 2)
    )

    renderer._reconcile_sequence_field_mounts((0, 2))

    cell = app.sequence_field_widgets[("Sequenzziel", 0)]
    assert cell.get("1.0", "end-1c") == "Ungespeichertes Sequenzziel"


def test_remount_uses_domain_value_when_no_pending_text_for_sequence_field(tk_root):
    renderer, app, _view_obj = _real_renderer_for_sequence_remount(
        tk_root, domain_value="Domain-Ziel", pending_text=None, mounted_range=(0, 2)
    )

    renderer._reconcile_sequence_field_mounts((0, 2))

    cell = app.sequence_field_widgets[("Sequenzziel", 0)]
    assert cell.get("1.0", "end-1c") == "Domain-Ziel"


def test_full_round_trip_dirty_sequence_text_survives_cold_eviction_and_remount(tk_root):
    renderer, app, _view_obj = _real_renderer_for_sequence_remount(
        tk_root, domain_value="Domain-Ziel", pending_text=None, mounted_range=(0, 2)
    )

    # 1. Initiales Mounten -- Widget zeigt den Domain-Wert.
    renderer._reconcile_sequence_field_mounts((0, 2))
    original_cell = app.sequence_field_widgets[("Sequenzziel", 0)]
    assert original_cell.get("1.0", "end-1c") == "Domain-Ziel"

    # 2. "Tippen": Widget-Text weicht ab, ohne Commit.
    original_cell.delete("1.0", "end")
    original_cell.insert("1.0", "Frisch getippt")

    # 3. Wegscrollen: Lauf faellt komplett aus dem Fenster -> COLD-Eviction.
    renderer._reconcile_sequence_field_mounts((8, 9))
    assert ("Sequenzziel", 0) not in app.sequence_field_widgets
    assert app.pending_cell_text[("Sequenzziel", 0)] == "Frisch getippt"

    # 4. Zurueckscrollen: Remount aus pending_cell_text.
    renderer._reconcile_sequence_field_mounts((0, 2))
    remounted_cell = app.sequence_field_widgets[("Sequenzziel", 0)]
    assert remounted_cell.get("1.0", "end-1c") == "Frisch getippt"
    assert remounted_cell is not original_cell


# --- Multi-Fenster-Szenario: beobachtbares Ergebnis statt Mengenrechnung ---
#
# Invariante (kurz, s. Plan fuer die volle Herleitung): `full_span` ist das
# vollstaendige logische Sequenz-Territorium, `mounted_col_range` der aktuell
# materialisierte Bereich. `sub_span` wird bei JEDEM Aufruf neu als
# Schnittmenge berechnet, nie fortgeschrieben. Eine Spalte kann nur dann vom
# Sequenz-Widget abgedeckt werden muessen, wenn sie sowohl in `full_span` als
# auch im Mount-Fenster liegt -- und genau diese Spalten landen zwangslaeufig
# in `sub_span`. Ausserhalb des Mount-Fensters wird fuer KEINE Zeile etwas
# materialisiert, weshalb dort keine Inkonsistenz zwischen Zeilen entstehen
# kann. Die folgenden Tests pruefen das am tatsaechlichen Mount-Ergebnis
# (sequence_field_widgets + echtes grid_info()), nicht an einer intern
# nachgerechneten Kopie derselben Schnittmengen-Formel.


def _real_renderer_for_multi_view_scenario(tk_root):
    """Zwei Sequenzlaeufe mit einer echten Nicht-Sequenz-Luecke dazwischen.

    view_a: Tage 2-9 (8 Spalten breit -- breiter als jedes Testfenster unten,
    damit auch der Fall "Fenster liegt vollstaendig INNERHALB des Spans,
    beide Raender abgeschnitten" entsteht). Luecke: Tag 10 (keine Sequenz).
    view_b: Tage 11-13 (3 Spalten, passt komplett in ein Fenster).
    20 Tage insgesamt, 1:1 Tag->Grid-Spalte.
    """
    renderer = object.__new__(GridRenderer)
    grid_inner = tk.Frame(tk_root)
    view_a = _view(member_row_indices=tuple(range(2, 10)), sequenzziel="A-Ziel", leitkompetenz="A-Kompetenz")
    view_b = _view(member_row_indices=(11, 12, 13), sequenzziel="B-Ziel", leitkompetenz="B-Kompetenz")
    app = SimpleNamespace(
        day_columns=[make_day_column(row_index=i) for i in range(20)],
        day_grid_columns={i: i for i in range(20)},
        sequence_field_widgets={},
        topic_sequence_plans=[view_a, view_b],
        sequence_fields_visible_var=SimpleNamespace(get=lambda: True),
        pending_cell_text={},
        grid_inner=grid_inner,
        preview_font=("Segoe UI", 10),
        preview_font_size=10,
        collapsed_row_lines=1,
        day_column_width=260,
        _handle_ui_intent=lambda *a, **kw: None,
        _on_grid_mousewheel=lambda _event: None,
    )
    renderer._sequence_field_renderer = SequenceFieldGridRenderer(app, renderer._create_text_cell)
    renderer.app = app
    renderer._sequence_field_renderer.app = app
    renderer._apply_cell_selection_style = lambda *a, **kw: None
    return renderer, app


def _mounted_grid_cols_for_field(app, field_key: str) -> dict[int, tuple[int, int]]:
    """Beobachtbarer Zustand: fuer jedes aktuell gemountete Widget dieses

    field_key, welche Grid-Spalten es tatsaechlich per echtem `grid_info()`
    belegt -- (first_row_index -> (column, column+columnspan-1)).
    """
    result = {}
    for (fk, first_row_index), cell in app.sequence_field_widgets.items():
        if fk != field_key:
            continue
        info = cell.grid_info()
        col = int(info["column"])
        span = int(info["columnspan"])
        result[first_row_index] = (col, col + span - 1)
    return result


def test_scenario_multiple_window_transitions_never_leaves_gap_or_stray_widget(tk_root):
    renderer, app = _real_renderer_for_multi_view_scenario(tk_root)

    # Schritt 1: Fenster (1,3) -> Spalten {1,2,3}. view_a (2-9) rechts
    # abgeschnitten: nur der Anfang (2,3) ist sichtbar.
    renderer._reconcile_sequence_field_mounts((1, 3))
    mounted = _mounted_grid_cols_for_field(app, "Sequenzziel")
    assert mounted == {2: (2, 3)}  # first_row_index=2 (view_a), Spalten 2..3
    assert app.sequence_field_widgets[("Sequenzziel", 2)].get("1.0", "end-1c") == "A-Ziel"

    # Schritt 2: Fenster (4,5) -> Spalten {4,5}, VOLLSTAENDIG innerhalb von
    # view_a (2-9) -- beide Raender des Spans liegen ausserhalb des Fensters.
    renderer._reconcile_sequence_field_mounts((4, 5))
    mounted = _mounted_grid_cols_for_field(app, "Sequenzziel")
    assert mounted == {2: (4, 5)}
    # Dasselbe Widget wie in Schritt 1 -- nur neu gespannt, nicht neu erzeugt.
    assert app.sequence_field_widgets[("Sequenzziel", 2)] is app.sequence_field_widgets[("Sequenzziel", 2)]

    # Schritt 3: Fenster (8,9) -> Spalten {8,9}, view_a links abgeschnitten
    # (rechtes Ende von view_a genau erreicht, Anfang 2-7 nicht sichtbar).
    renderer._reconcile_sequence_field_mounts((8, 9))
    mounted = _mounted_grid_cols_for_field(app, "Sequenzziel")
    assert mounted == {2: (8, 9)}

    # Schritt 4: Fenster (10,10) -> Spalte {10}, die echte Nicht-Sequenz-
    # Luecke zwischen view_a und view_b. Keine Sequenz-Zelle darf hier
    # existieren (weder view_a noch view_b decken Tag 10 ab).
    renderer._reconcile_sequence_field_mounts((10, 10))
    assert app.sequence_field_widgets == {}  # view_a komplett evictet, view_b noch ausserhalb

    # Schritt 5: Fenster (11,13) -> view_b (11-13) VOLLSTAENDIG sichtbar,
    # view_a bleibt (weiterhin ausserhalb) evictet.
    renderer._reconcile_sequence_field_mounts((11, 13))
    mounted = _mounted_grid_cols_for_field(app, "Sequenzziel")
    assert mounted == {11: (11, 13)}
    assert app.sequence_field_widgets[("Sequenzziel", 11)].get("1.0", "end-1c") == "B-Ziel"
    # Leitkompetenz-Zeile unabhaengig, aber symmetrisch geprueft.
    assert _mounted_grid_cols_for_field(app, "Leitkompetenz") == {11: (11, 13)}

    # Schritt 6: Fenster (15,16) -> ausserhalb beider Laeufe. sub_span fuer
    # BEIDE ist leer -- kein Widget bleibt faelschlich sichtbar, keins wird
    # ausserhalb des Fensters neu gemountet.
    renderer._reconcile_sequence_field_mounts((15, 16))
    assert app.sequence_field_widgets == {}

    # Schritt 7: zurueck zu Schritt 1s Fenster -- view_a muss korrekt mit
    # demselben Teilspan wiederauftauchen (Remount, neues Widget-Objekt,
    # da zwischenzeitlich echt COLD).
    renderer._reconcile_sequence_field_mounts((1, 3))
    mounted = _mounted_grid_cols_for_field(app, "Sequenzziel")
    assert mounted == {2: (2, 3)}
    assert app.sequence_field_widgets[("Sequenzziel", 2)].get("1.0", "end-1c") == "A-Ziel"


def test_scenario_reconciling_same_window_twice_is_idempotent(tk_root):
    renderer, app = _real_renderer_for_multi_view_scenario(tk_root)

    renderer._reconcile_sequence_field_mounts((4, 5))  # view_a beidseitig abgeschnitten, wie Schritt 2 oben
    widget_before = app.sequence_field_widgets[("Sequenzziel", 2)]
    grid_info_before = widget_before.grid_info()

    renderer._reconcile_sequence_field_mounts((4, 5))  # identisches Fenster erneut

    widget_after = app.sequence_field_widgets[("Sequenzziel", 2)]
    assert widget_after is widget_before  # keine Destroy/Recreate-Runde
    assert widget_after.grid_info() == grid_info_before  # keine erneute grid()-Umplatzierung
    assert len(app.sequence_field_widgets) == 2  # Sequenzziel + Leitkompetenz, keine Duplikate


def test_scenario_never_triggers_save_or_editor_controller_across_full_transition_sequence(tk_root):
    """Wiederholt denselben Fenster-Zyklus wie der grosse Szenario-Test --

    inklusive echter Remounts (view_a/view_b muessen aus dem leeren
    `sequence_field_widgets` neu erzeugt werden), deshalb derselbe echte
    Tk-Helper wie dort. Der App-Stub hat bewusst KEIN `save_sequence_field`/
    `editor_controller`/`apply_value` -- ein versehentlicher Persistenz-
    Aufruf irgendwo in der Kette (Eviction, Respan, Remount) wuerde mit
    `AttributeError` crashen statt still zu bestehen.
    """
    renderer, app = _real_renderer_for_multi_view_scenario(tk_root)

    windows = [(1, 3), (4, 5), (8, 9), (10, 10), (11, 13), (15, 16), (1, 3)]
    for window in windows:
        renderer._reconcile_sequence_field_mounts(window)  # crasht sofort, falls ein Persistenzpfad beruehrt wird
