"""Tests für `GridRenderer._grid_structure_matches_state()` (Kursplaner Item 4,
Stufe 2 -- dreiwertige Struktur-Prüfung, verhaltensgleich bis echtes
Mount/Unmount existiert).

Vorher: eine binäre Gleichheitsprüfung "domain-sichtbar == hat Widget" für
jede (Feld, Tag)-Kombination -- nach der geplanten Virtualisierung ist
"domain-sichtbar, aber ausserhalb des Mount-Fensters kein Widget" ein
legitimer Zustand, kein struktureller Fehler mehr. Diese Tests beweisen die
strikte Lockerung: alles, was die alte Prüfung erfüllte, erfüllt weiterhin
auch die neue (Tests A/B/E/F), UND die neue Prüfung erlaubt zusätzlich genau
den einen neuen Fall, den die alte fälschlich abgelehnt hätte (Test D).

Isoliert per `object.__new__(GridRenderer)`, kein echter Tk-Root nötig --
dasselbe Muster wie `test_grid_renderer_column_fast_path.py` und
`test_grid_renderer_selection_visibility.py`.
"""

from __future__ import annotations

from types import SimpleNamespace

from kursplaner.adapters.gui.grid_renderer import GridRenderer
from tests.day_column_factory import make_day_column

_FIELD_KEY = "Stundenthema"
_VISIBLE_DAYS = {0, 1, 2, 3}  # Tag 4 ist fuer dieses Feld nicht sichtbar (z.B. Ferientag)
_DAY_COUNT = 5


def _renderer(
    *,
    cell_widgets: dict[tuple[str, int], object],
    mounted_range: tuple[int, int] | str | None = "OMIT",
    header_labels: dict[int, object] | None = None,
    row_labels: dict[str, object] | None = None,
) -> GridRenderer:
    renderer = object.__new__(GridRenderer)
    day_columns = [make_day_column(row_index=i) for i in range(_DAY_COUNT)]
    app = SimpleNamespace(
        day_columns=day_columns,
        row_defs=[(_FIELD_KEY, "Thema")],
        header_labels=header_labels if header_labels is not None else {i: object() for i in range(_DAY_COUNT)},
        row_labels=row_labels if row_labels is not None else {_FIELD_KEY: object()},
        cell_widgets=cell_widgets,
        row_display_mode_usecase=SimpleNamespace(
            is_linked_day=lambda _day: True,
            field_is_relevant_for_day=lambda field_key, day, _settings: (
                field_key == _FIELD_KEY and day.row_index in _VISIBLE_DAYS
            ),
        ),
        row_filter_settings=SimpleNamespace(),
    )
    if mounted_range != "OMIT":
        app.viewport_sync_h = SimpleNamespace(mounted_day_index_range=lambda: mounted_range)
    renderer.app = app
    return renderer


def test_matches_when_every_visible_cell_has_a_widget_and_no_viewport_sync_h():
    """Fallback-Sicherheit: fehlt `viewport_sync_h` ganz (z.B. leichtgewichtiger

    Test-Stub), degradiert die Prüfung auf die alte volle Gleichheitsprüfung,
    statt abzustürzen.
    """
    renderer = _renderer(
        cell_widgets={(_FIELD_KEY, i): object() for i in _VISIBLE_DAYS},
        mounted_range="OMIT",
    )

    assert renderer._grid_structure_matches_state() is True


def test_mismatches_when_widget_exists_for_a_domain_invisible_cell():
    """Verwaistes Widget fuer eine nicht mehr relevante Zelle ist IMMER ein

    Fehler -- unabhaengig vom Mount-Fenster.
    """
    cell_widgets = {(_FIELD_KEY, i): object() for i in _VISIBLE_DAYS}
    cell_widgets[(_FIELD_KEY, 4)] = object()  # Tag 4: nicht sichtbar, aber hat ein Widget
    renderer = _renderer(cell_widgets=cell_widgets, mounted_range="OMIT")

    assert renderer._grid_structure_matches_state() is False


def test_mismatches_when_widget_missing_inside_mount_window():
    """Fehlendes Widget INNERHALB des Mount-Fensters bleibt ein echter Fehler."""
    renderer = _renderer(
        cell_widgets={(_FIELD_KEY, 1): object(), (_FIELD_KEY, 3): object()},  # Tag 2 fehlt
        mounted_range=(1, 3),
    )

    assert renderer._grid_structure_matches_state() is False


def test_matches_when_widget_missing_outside_mount_window():
    """Neues Verhalten (der eigentliche Zweck von Stufe 2): fehlendes Widget

    AUSSERHALB des Mount-Fensters ist kein Fehler mehr, obwohl die Zelle
    domain-sichtbar ist -- die alte binaere Pruefung haette das faelschlich
    als strukturellen Mismatch gewertet.
    """
    renderer = _renderer(
        cell_widgets={(_FIELD_KEY, 1): object(), (_FIELD_KEY, 2): object(), (_FIELD_KEY, 3): object()},
        mounted_range=(1, 3),  # Tag 0 ist domain-sichtbar, aber ausserhalb des Fensters und cold
    )

    assert renderer._grid_structure_matches_state() is True


def test_mismatches_when_header_label_count_differs_from_day_columns():
    renderer = _renderer(
        cell_widgets={(_FIELD_KEY, i): object() for i in _VISIBLE_DAYS},
        header_labels={0: object()},  # nur 1 statt 5
        mounted_range="OMIT",
    )

    assert renderer._grid_structure_matches_state() is False


def test_mismatches_when_row_labels_do_not_match_expected_fields():
    renderer = _renderer(
        cell_widgets={(_FIELD_KEY, i): object() for i in _VISIBLE_DAYS},
        row_labels={},  # erwartetes Feld fehlt
        mounted_range="OMIT",
    )

    assert renderer._grid_structure_matches_state() is False


def test_old_binary_equivalent_check_still_applies_when_mounted_range_is_none():
    """`mounted_day_index_range()` kann auch bei vorhandenem `viewport_sync_h`

    None liefern (z.B. Grid noch nicht layoutet) -- dann gilt weiterhin die
    volle Gleichheitsprüfung fuer jede Zelle, exakt wie vor Stufe 2.
    """
    renderer = _renderer(
        cell_widgets={(_FIELD_KEY, 0): object(), (_FIELD_KEY, 1): object()},  # Tage 2,3 fehlen
        mounted_range=None,
    )

    assert renderer._grid_structure_matches_state() is False
