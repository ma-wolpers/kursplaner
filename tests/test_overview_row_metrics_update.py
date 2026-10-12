"""Regression: Aktualisieren der Übersichtszeile darf keine Spalten verschieben.

Früher schrieb ``_update_selected_lesson_metrics`` über feste Positionsindizes,
die nach dem Einfügen der Spalte "stufe" um eins verrutscht waren (Thema landete
in "Stufe", Datum in "Nächstes Thema" usw.).
"""

from __future__ import annotations

from tkinter import ttk
from types import SimpleNamespace

import pytest

from kursplaner.adapters.gui.main_window import KursplanerApp
from kursplaner.adapters.gui.overview_columns import OVERVIEW_COLUMNS, overview_row_values


class _QueryStub:
    def summarize_plan(self, _table):
        return ("Neues Thema", 17, "16.11. M", "9.11. M", "26-10-26", 3, True, True)


def test_update_selected_lesson_metrics_writes_by_column_id(tk_root):
    tree = ttk.Treeview(tk_root, columns=OVERVIEW_COLUMNS, show="headings")
    tree.insert(
        "",
        "end",
        iid="kurs",
        values=overview_row_values(
            {
                "name": "Mat 11.1 26-2",
                "stufe": "11",
                "next_topic": "Altes Thema",
                "next_unit": "19-10-26",
                "remaining_hours": "80",
                "next_lzk": "—",
                "next_ub": "",
            }
        ),
    )
    tree.focus("kurs")
    app = SimpleNamespace(lesson_tree=tree, current_table=object(), _plan_overview_query=_QueryStub())

    KursplanerApp._update_selected_lesson_metrics(app)

    row = {column_id: tree.set("kurs", column_id) for column_id in OVERVIEW_COLUMNS}
    assert row == {
        "name": "Mat 11.1 26-2",
        "stufe": "11",
        "next_topic": "Neues Thema",
        "next_unit": "26-10-26",
        "remaining_hours": "17",
        "next_lzk": "16.11. M",
        "next_ub": "9.11. M",
    }
    tree.destroy()


def test_overview_row_values_rejects_mismatched_keys():
    with pytest.raises(ValueError):
        overview_row_values({"name": "x"})
