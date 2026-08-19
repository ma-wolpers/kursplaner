from pathlib import Path

import pytest

from kursplaner.core.domain.plan_table import (
    COLUMN_DATUM,
    COLUMN_INHALT,
    COLUMN_THEMA_AUSFALL,
    PlanTableData,
)
from kursplaner.infrastructure.repositories.plan_table_markdown_io import _EXPECTED_HEADERS


def _table(headers: list[str], rows: list[list[str]]) -> PlanTableData:
    return PlanTableData(
        markdown_path=Path("Kurs.md"),
        headers=headers,
        rows=rows,
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={},
    )


def test_column_index_finds_column_case_insensitively():
    table = _table(["Datum", "Inhalt", "Thema/Ausfall"], [])
    assert table.column_index(COLUMN_INHALT) == 1
    assert table.column_index("inhalt") == 1


def test_column_index_raises_when_column_missing():
    table = _table(["Datum", "Inhalt"], [])
    with pytest.raises(RuntimeError, match="Thema/Ausfall"):
        table.column_index(COLUMN_THEMA_AUSFALL)


def test_column_index_optional_returns_none_when_missing():
    table = _table(["Datum", "Inhalt"], [])
    assert table.column_index_optional(COLUMN_THEMA_AUSFALL) is None
    assert table.column_index_optional(COLUMN_DATUM) == 0


def test_inhalt_and_set_inhalt_roundtrip():
    table = _table(["Datum", "Inhalt", "Thema/Ausfall"], [["01-09-25", "alt", ""]])
    assert table.inhalt(0) == "alt"
    table.set_inhalt(0, "neu")
    assert table.inhalt(0) == "neu"
    assert table.rows[0][1] == "neu"


def test_set_inhalt_pads_short_row():
    table = _table(["Datum", "Inhalt", "Thema/Ausfall"], [["01-09-25"]])
    table.set_inhalt(0, "wert")
    assert table.rows[0] == ["01-09-25", "wert"]


def test_inhalt_returns_empty_for_short_row():
    table = _table(["Datum", "Inhalt", "Thema/Ausfall"], [["01-09-25"]])
    assert table.inhalt(0) == ""


def test_thema_ausfall_and_set_thema_ausfall_roundtrip():
    table = _table(["Datum", "Inhalt", "Thema/Ausfall"], [["01-09-25", "", "X Krank"]])
    assert table.thema_ausfall(0) == "X Krank"
    table.set_thema_ausfall(0, "[[li2 Kodierung]]")
    assert table.thema_ausfall(0) == "[[li2 Kodierung]]"


def test_set_thema_ausfall_pads_short_row():
    table = _table(["Datum", "Inhalt", "Thema/Ausfall"], [["01-09-25", "x"]])
    table.set_thema_ausfall(0, "wert")
    assert table.rows[0] == ["01-09-25", "x", "wert"]


def test_column_name_constants_match_markdown_loader_validation():
    """Stellt sicher, dass Domain-Konstanten und Lade-Validierung dieselbe Quelle nutzen."""
    assert _EXPECTED_HEADERS == [COLUMN_DATUM.lower(), COLUMN_INHALT.lower(), COLUMN_THEMA_AUSFALL.lower()]
