"""Tests für die Mehrthemen-Zugriffe und die Grid-Anzeige von `DayColumn`."""

from __future__ import annotations

from kursplaner.core.domain.oberthema_values import OBERTHEMA_INVALID_MARKER
from kursplaner.core.domain.yaml_registry import RawYamlBlock
from tests.day_column_factory import make_day_column


def test_lzk_with_multiple_topics_exposes_list_primary_and_joined_display():
    day = make_day_column(
        yaml={"Stundentyp": "LZK", "Oberthema": ["[[11.1 Potenzen]]", "[[11.1 Exponential]]"]},
        group_name="[[11.1]]",
    )

    assert day.oberthemen() == ("Potenzen", "Exponential")
    assert day.oberthema() == "Potenzen"
    assert day.oberthema_display() == "Potenzen\n--\nExponential"


def test_unit_without_yaml_topic_falls_back_to_plan_cell():
    day = make_day_column(thema_ausfall="[[11.1 Potenzen]]", group_name="11.1")

    assert day.oberthemen() == ("Potenzen",)
    assert day.oberthema_display() == "Potenzen"


def test_invalid_topic_is_shown_as_warning_not_as_empty():
    day = make_day_column(
        thema_ausfall="[[11.1 Potenzen]]",
        yaml={"Stundentyp": "Unterricht", "Oberthema": RawYamlBlock(("  foo: bar",))},
        group_name="11.1",
    )

    assert day.oberthema_state().is_invalid
    assert day.oberthemen() == ()
    assert day.oberthema_display() == OBERTHEMA_INVALID_MARKER
