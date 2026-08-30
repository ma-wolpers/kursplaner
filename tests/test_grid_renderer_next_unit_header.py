"""Tests für die persistente "nächste Einheit"-Header-Markierung in `grid_renderer.py`.

`GridRenderer` berechnet den Next-Unit-Index NICHT selbst (kein Controller-
Aufruf, keine Zeit-/Policy-Logik) — er liest ausschließlich den zuvor per
`set_next_unit_index()` gesetzten Wert. Diese Tests decken `_header_visual_state()`
ab: die Markierung nutzt zwei getrennte Kanäle (eigener Hintergrund-`col_type`
"next_unit" im Normalfall, angehängtes Glyph als Fallback wenn der Hintergrund
bereits durch cancel/hospitation/lzk/unresolved belegt ist) und kollidiert
dadurch nie mit dem bestehenden UB-/Datumslos-Rahmen (`_apply_ub_border`,
unverändert, hier nicht getestet).
"""

from __future__ import annotations

from types import SimpleNamespace

from kursplaner.adapters.gui.grid_renderer import GridRenderer
from tests.day_column_factory import make_day_column


def _visual_state(day_columns, *, next_unit_index, day_index=0):
    renderer = object.__new__(GridRenderer)
    renderer.app = SimpleNamespace(day_columns=day_columns)
    renderer._next_unit_index = None
    renderer.set_next_unit_index(next_unit_index)
    return renderer._header_visual_state(day_index)


def test_set_next_unit_index_stores_plain_value():
    renderer = object.__new__(GridRenderer)
    renderer._next_unit_index = None
    renderer.set_next_unit_index(3)
    assert renderer._next_unit_index == 3


def test_normal_column_not_next_unit_uses_normal_col_type():
    columns = [make_day_column(row_index=0, datum="18-02-26")]
    text, col_type = _visual_state(columns, next_unit_index=None)
    assert col_type == "normal"
    assert "▶" not in text


def test_normal_column_as_next_unit_uses_dedicated_col_type_without_glyph():
    columns = [make_day_column(row_index=0, datum="18-02-26")]
    text, col_type = _visual_state(columns, next_unit_index=0)
    assert col_type == "next_unit"
    assert "▶" not in text  # eigener Hintergrundkanal reicht, kein Text-Glyph noetig


def test_cancelled_column_not_next_unit_keeps_cancel_col_type_no_glyph():
    columns = [make_day_column(row_index=0, datum="18-02-26", thema_ausfall="X Grund")]
    text, col_type = _visual_state(columns, next_unit_index=None)
    assert col_type == "cancel"
    assert "▶" not in text


def test_cancelled_column_as_next_unit_keeps_cancel_background_but_adds_glyph():
    columns = [make_day_column(row_index=0, datum="18-02-26", thema_ausfall="X Grund")]
    text, col_type = _visual_state(columns, next_unit_index=0)
    assert col_type == "cancel"  # Hintergrund bleibt cancel, next_unit ueberschreibt nicht
    assert text.endswith("▶")


def test_hospitation_column_as_next_unit_keeps_hospitation_background_but_adds_glyph():
    # is_hospitation() ohne echten Datei-Link greift ueber den Textmarker
    # "HO ..." in `inhalt` (Stundentyp-YAML braucht dagegen einen real
    # existierenden `link`, siehe DayColumn.stundentyp) -- fuer diesen
    # reinen Domain-Test reicht der Marker-Pfad.
    columns = [make_day_column(row_index=0, datum="18-02-26", inhalt="HO Grund")]
    text, col_type = _visual_state(columns, next_unit_index=0)
    assert col_type == "hospitation"
    assert text.endswith("▶")


def test_unresolved_link_column_not_next_unit_shows_only_warning_glyph():
    columns = [make_day_column(row_index=0, datum="18-02-26", inhalt="[[fehlt]]", link=None)]
    text, col_type = _visual_state(columns, next_unit_index=None)
    assert col_type == "unresolved"
    assert text.endswith("⚠")
    assert "▶" not in text


def test_unresolved_link_column_as_next_unit_combines_both_glyphs():
    columns = [make_day_column(row_index=0, datum="18-02-26", inhalt="[[fehlt]]", link=None)]
    text, col_type = _visual_state(columns, next_unit_index=0)
    assert col_type == "unresolved"
    assert "⚠" in text
    assert text.endswith("▶")


def test_out_of_range_day_index_returns_normal_regardless_of_next_unit_index():
    columns = [make_day_column(row_index=0, datum="18-02-26")]
    text, col_type = _visual_state(columns, next_unit_index=5, day_index=5)
    assert text == ""
    assert col_type == "normal"
