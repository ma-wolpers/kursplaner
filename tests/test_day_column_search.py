import re

from kursplaner.core.domain.day_column_search import day_column_matches_query
from tests.day_column_factory import make_day_column


def test_matches_inhalt():
    day = make_day_column(inhalt="Quadratische Gleichungen")

    assert day_column_matches_query(day, re.compile("Gleichung")) is True


def test_matches_thema_ausfall():
    day = make_day_column(thema_ausfall="X Lehrerkonferenz")

    assert day_column_matches_query(day, re.compile("konferenz")) is True


def test_matches_header_content_via_stundenthema():
    day = make_day_column(yaml={"Stundenthema": "Ableitungsregeln"})

    assert day_column_matches_query(day, re.compile("Ableitung")) is True


def test_matches_oberthema_via_yaml():
    day = make_day_column(yaml={"Oberthema": "Analysis"})

    assert day_column_matches_query(day, re.compile("Analysis")) is True


def test_no_match_returns_false():
    day = make_day_column(inhalt="Vektoren", thema_ausfall="", yaml={})

    assert day_column_matches_query(day, re.compile("Stochastik")) is False


def test_is_case_sensitive_by_default():
    day = make_day_column(inhalt="Vektoren")

    assert day_column_matches_query(day, re.compile("vektoren")) is False
    assert day_column_matches_query(day, re.compile("Vektoren")) is True


def test_group_name_alone_is_not_searched():
    day = make_day_column(group_name="Mathe-LK-12", inhalt="", thema_ausfall="", yaml={})

    assert day_column_matches_query(day, re.compile("Mathe-LK-12")) is False
