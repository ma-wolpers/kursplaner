"""Tests für Export-DTO (`TopicUnitExportRow`) und Tabellendarstellung (`sequence_export_table`)."""

from datetime import date
from pathlib import Path

import pytest

from kursplaner.core.domain.course_rhythm import WeekdayRhythm
from kursplaner.core.domain.topic_sequence_runs import (
    TopicSequenceRun,
    TopicUnitExportRow,
    build_export_rows_for_run,
)
from kursplaner.core.domain.wiki_links import wiki_link_display_text
from kursplaner.core.usecases.sequence_export_table import (
    EXPORT_TABLE_HEADERS,
    date_hour_cell,
    export_row_cells,
    material_cell,
    text_cell,
)
from tests.day_column_factory import make_day_column


def _row(**overrides) -> TopicUnitExportRow:
    values = dict(
        datum=date(2023, 9, 7),
        datum_raw="07-09-23",
        startzeit="08:00",
        stunden=2,
        stundenthema="Thema",
        stundenziel="Ziel",
        kompetenzen=("Modellieren", "Argumentieren"),
        material=("[[Material/AB Brüche.pdf|AB 1]]", "Tafelbild"),
    )
    values.update(overrides)
    return TopicUnitExportRow(**values)


def test_headers_follow_template_order():
    assert EXPORT_TABLE_HEADERS == ("Datum und Stunde", "Kompetenzbezug", "Stundenthema", "Stundenziel", "Material")


def test_date_cell_with_weekday_start_time_and_hours():
    assert date_hour_cell(_row()) == ("Do 07.09.2023", "08:00 · 2 Std.")


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({"startzeit": ""}, ("Do 07.09.2023", "2 Std.")),
        ({"stunden": 0}, ("Do 07.09.2023", "08:00")),
        ({"startzeit": "", "stunden": 0}, ("Do 07.09.2023",)),
        ({"datum": None, "datum_raw": "ohne Datum"}, ("ohne Datum", "08:00 · 2 Std.")),
    ],
)
def test_date_cell_omits_missing_parts_without_placeholders(overrides, expected):
    assert date_hour_cell(_row(**overrides)) == expected


def test_one_entry_per_line_for_competencies_and_material():
    cells = export_row_cells(_row())

    assert cells[1] == ("Modellieren", "Argumentieren")
    assert cells[4] == ("AB 1", "Tafelbild")


def test_empty_material_is_an_empty_cell():
    assert export_row_cells(_row(material=()))[4] == ()
    assert material_cell(()) == ()


def test_free_text_cells_split_lines_and_drop_blank_ones():
    assert text_cell("Zeile 1\n\n  Zeile 2  ") == ("Zeile 1", "Zeile 2")
    assert text_cell("") == ()


@pytest.mark.parametrize(
    "entry, expected",
    [
        ("[[Material/AB Brüche.pdf|AB 1]]", "AB 1"),
        ("[[Material/AB Brüche.pdf]]", "AB Brüche.pdf"),
        ("[[Ordner/Notiz.MD]]", "Notiz"),
        ("[[Einheiten/Stunde.ebw]]", "Stunde"),
        ("[[Ziel|]]", "Ziel"),
        ("Tafelbild", "Tafelbild"),
        ("Tafelbild [[Skizze]]", "Tafelbild [[Skizze]]"),
        ("https://example.org/a|b", "https://example.org/a|b"),
    ],
)
def test_wiki_link_display_text_contract(entry, expected):
    assert wiki_link_display_text(entry) == expected


def test_build_export_rows_reads_typed_fields(tmp_path: Path):
    link = tmp_path / "Einheiten" / "u.md"
    link.parent.mkdir()
    link.write_text("---\nStundentyp: Unterricht\n---\n", encoding="utf-8")
    rhythm = (WeekdayRhythm(weekday=3, start_time="08:00", hours=2),)
    day = make_day_column(
        row_index=0,
        datum="07-09-23",
        link=link,
        rhythm=rhythm,
        yaml={
            "Stundentyp": "Unterricht",
            "Oberthema": "Funktionen",
            "Stundenthema": "Thema",
            "Stundenziel": "Ziel",
            "Kompetenzen": ["K1"],
            "Material": ["AB"],
        },
    )

    [row] = build_export_rows_for_run([day], TopicSequenceRun(oberthema="Funktionen", member_row_indices=(0,)))

    assert row == TopicUnitExportRow(
        datum=date(2023, 9, 7),
        datum_raw="07-09-23",
        startzeit="08:00",
        stunden=2,
        stundenthema="Thema",
        stundenziel="Ziel",
        kompetenzen=("K1",),
        material=("AB",),
    )


def test_lzk_without_material_key_yields_empty_material(tmp_path: Path):
    link = tmp_path / "Einheiten" / "l.md"
    link.parent.mkdir()
    link.write_text("---\nStundentyp: LZK\n---\n", encoding="utf-8")
    day = make_day_column(row_index=0, datum="07-09-23", link=link, yaml={"Stundentyp": "LZK", "Oberthema": ["T"]})

    [row] = build_export_rows_for_run([day], TopicSequenceRun(oberthema="T", member_row_indices=(0,)))

    assert row.material == ()


def test_non_list_competencies_violate_the_invariant(tmp_path: Path):
    link = tmp_path / "Einheiten" / "u.md"
    link.parent.mkdir()
    link.write_text("---\nStundentyp: Unterricht\n---\n", encoding="utf-8")
    day = make_day_column(
        row_index=0,
        datum="07-09-23",
        link=link,
        yaml={"Stundentyp": "Unterricht", "Oberthema": "T", "Kompetenzen": "K1"},
    )

    with pytest.raises(TypeError):
        build_export_rows_for_run([day], TopicSequenceRun(oberthema="T", member_row_indices=(0,)))
