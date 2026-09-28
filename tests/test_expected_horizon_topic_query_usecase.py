"""Tests für Stichtag, Kandidaten und Vorbelegung eines Kompetenzhorizonts (synthetische Daten)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from kursplaner.core.domain.expected_horizon_cutoff import HorizonCutoff
from kursplaner.core.domain.yaml_registry import RawYamlBlock
from kursplaner.core.usecases.expected_horizon_topic_query_usecase import ExpectedHorizonTopicQueryUseCase
from tests.day_column_factory import make_day_column


class _Course:
    """Baut Tages-Spalten mit echten (leeren) Stunden-Dateien, damit `stundentyp` greift."""

    def __init__(self, tmp_path: Path):
        self.dir = tmp_path / "Kurs" / "Einheiten"
        self.dir.mkdir(parents=True)
        self.days = []

    def add(self, datum: str, kind: str, oberthema: object):
        row_index = len(self.days)
        link = self.dir / f"e{row_index}.md"
        link.write_text("---\n---\n", encoding="utf-8")
        self.days.append(
            make_day_column(
                row_index=row_index,
                datum=datum,
                inhalt=f"[[e{row_index}]]",
                link=link,
                yaml={"Stundentyp": kind, "Oberthema": oberthema},
                group_name="11.1",
            )
        )
        return row_index


def _query(course: _Course, anchor: int):
    return ExpectedHorizonTopicQueryUseCase().query(raw_day_columns=course.days, anchor_row_index=anchor)


def test_cutoff_semantics_before_and_up_to_and_including():
    day = date(2026, 10, 14)

    assert not HorizonCutoff.before(day).admits(day)
    assert HorizonCutoff.before(day).admits(date(2026, 10, 13))
    assert HorizonCutoff.up_to_and_including(day).admits(day)
    assert not HorizonCutoff.up_to_and_including(day).admits(date(2026, 10, 15))
    assert not HorizonCutoff.up_to_and_including(day).admits(None)


def test_lzk_anchor_offers_only_topics_before_lzk_in_chronological_order(tmp_path):
    course = _Course(tmp_path)
    course.add("01-09-26", "Unterricht", ["[[11.1 Potenzen]]"])
    course.add("03-09-26", "Unterricht", ["[[11.1 Exponential]]"])
    course.add("08-09-26", "Unterricht", ["[[11.1 Potenzen]]"])
    lzk = course.add("10-09-26", "LZK", [])
    course.add("10-09-26", "Unterricht", ["[[11.1 Am LZK-Tag]]"])
    course.add("15-09-26", "Unterricht", ["[[11.1 Danach]]"])

    result = _query(course, lzk)

    assert result.is_lzk_anchor
    assert result.cutoff == HorizonCutoff.before(date(2026, 9, 10))
    assert result.option_topics == ("Potenzen", "Exponential")
    potenzen = result.options[0]
    assert (potenzen.first_date, potenzen.last_date, potenzen.unit_count) == (date(2026, 9, 1), date(2026, 9, 8), 2)


def test_unterricht_anchor_includes_its_own_day(tmp_path):
    course = _Course(tmp_path)
    course.add("01-09-26", "Unterricht", ["[[11.1 A]]"])
    anchor = course.add("03-09-26", "Unterricht", ["[[11.1 B]]"])
    course.add("05-09-26", "Unterricht", ["[[11.1 C]]"])

    result = _query(course, anchor)

    assert not result.is_lzk_anchor
    assert result.option_topics == ("A", "B")
    assert result.preselected == ("B",)


def test_dateless_units_are_never_candidates(tmp_path):
    course = _Course(tmp_path)
    course.add("", "Unterricht", ["[[11.1 Ohne Datum]]"])
    course.add("01-09-26", "Unterricht", ["[[11.1 A]]"])
    lzk = course.add("10-09-26", "LZK", [])

    assert _query(course, lzk).option_topics == ("A",)


def test_same_first_date_is_ordered_by_row_index(tmp_path):
    course = _Course(tmp_path)
    course.add("01-09-26", "Unterricht", ["[[11.1 Zweites]]"])
    course.add("01-09-26", "Unterricht", ["[[11.1 Erstes]]"])
    lzk = course.add("10-09-26", "LZK", [])

    assert _query(course, lzk).option_topics == ("Zweites", "Erstes")


def test_lzk_preselects_stored_topics_and_reports_unavailable_ones(tmp_path):
    course = _Course(tmp_path)
    course.add("01-09-26", "Unterricht", ["[[11.1 A]]"])
    course.add("03-09-26", "Unterricht", ["[[11.1 B]]"])
    lzk = course.add("10-09-26", "LZK", ["[[11.1 B]]", "[[11.1 Umbenannt]]"])

    result = _query(course, lzk)

    assert result.stored == ("B", "Umbenannt")
    assert result.preselected == ("B",)
    assert result.unavailable_stored == ("Umbenannt",)


def test_ordered_selection_is_duplicate_free_chronological_and_candidates_only(tmp_path):
    course = _Course(tmp_path)
    course.add("01-09-26", "Unterricht", ["[[11.1 A]]"])
    course.add("03-09-26", "Unterricht", ["[[11.1 B]]"])
    lzk = course.add("10-09-26", "LZK", [])

    result = _query(course, lzk)

    assert result.ordered_selection(["B", "A", "B", "Fremd"]) == ("A", "B")


def test_units_with_invalid_topic_are_counted_not_offered(tmp_path):
    course = _Course(tmp_path)
    course.add("01-09-26", "Unterricht", ["[[11.1 A]]"])
    course.add("02-09-26", "Unterricht", RawYamlBlock(("  foo: bar",)))
    lzk = course.add("10-09-26", "LZK", [])

    result = _query(course, lzk)

    assert result.option_topics == ("A",)
    assert result.invalid_unit_count == 1


def test_lzk_with_invalid_topic_is_rejected(tmp_path):
    course = _Course(tmp_path)
    course.add("01-09-26", "Unterricht", ["[[11.1 A]]"])
    lzk = course.add("10-09-26", "LZK", RawYamlBlock(("  foo: bar",)))

    with pytest.raises(RuntimeError, match="ungültiges Format"):
        _query(course, lzk)


def test_no_candidates_is_an_error(tmp_path):
    course = _Course(tmp_path)
    lzk = course.add("10-09-26", "LZK", [])
    course.add("15-09-26", "Unterricht", ["[[11.1 Danach]]"])

    with pytest.raises(RuntimeError, match="keine datierten Unterrichtsstunden"):
        _query(course, lzk)


def test_anchor_without_date_is_rejected(tmp_path):
    course = _Course(tmp_path)
    anchor = course.add("", "LZK", [])

    with pytest.raises(RuntimeError, match="kein Datum"):
        _query(course, anchor)
