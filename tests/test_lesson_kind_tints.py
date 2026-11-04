"""Einheitstyp-Farbtöne: eine Tabelle, identische Parameter wie vor der Zusammenführung."""

from __future__ import annotations

from kursplaner.adapters.gui import lesson_kind_tints as tints
from kursplaner.adapters.gui.ui_theme import HOSPITATION_SEED


def test_table_keeps_the_previous_grid_parameters():
    table = tints.LESSON_KIND_TINTS
    assert (table["ausfall"].color_tint, table["ausfall"].degree, table["ausfall"].fg_token) == (
        "warning_soft",
        0.72,
        "fg_muted",
    )
    assert (table["lzk"].color_tint, table["lzk"].degree, table["lzk"].fg_token) == ("success_soft", 0.72, None)
    assert (table["hospitation"].color_tint, table["hospitation"].degree) == (HOSPITATION_SEED, 0.38)
    assert {tint.base_token for tint in table.values()} == {"panel_strong"}


def test_apply_helpers_forward_exactly_these_parameters(monkeypatch):
    calls = []
    monkeypatch.setattr(tints, "theme_text_tinted", lambda w, c, **kw: calls.append((c, kw)))
    tints.apply_text_tint(object(), tints.LESSON_KIND_TINTS["lzk"].muted())
    tints.apply_text_tint(object(), tints.LESSON_KIND_TINTS["hospitation"])
    assert calls == [
        ("success_soft", {"degree": 0.72, "base_token": "panel_strong", "fg_token": "fg_muted"}),
        (HOSPITATION_SEED, {"degree": 0.38, "base_token": "panel_strong"}),
    ]
