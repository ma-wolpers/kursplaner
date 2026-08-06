from datetime import date

from kursplaner.core.domain.course_subject import normalize_course_subject, short_subject_for_course_subject
from kursplaner.core.domain.unterrichtsbesuch_policy import (
    UB_KIND_FACH,
    UB_KIND_PAEDAGOGIK,
    UbStem,
    build_ub_stem,
    normalize_ub_kinds,
    parse_ub_date_from_stem,
    parse_ub_yy_mm_dd,
)


def test_normalize_course_subject_accepts_darstellendes_spiel():
    assert normalize_course_subject("Darstellendes Spiel") == "Darstellendes Spiel"
    assert short_subject_for_course_subject("Darstellendes Spiel") == "DS"


def test_normalize_ub_kinds_rejects_unknown_values():
    try:
        normalize_ub_kinds(["Fach", "Unbekannt"])
        assert False, "Expected ValueError for unknown UB kind"
    except ValueError as exc:
        assert "UB-Art ungueltig" in str(exc)


def test_normalize_ub_kinds_deduplicates_and_preserves_order():
    result = normalize_ub_kinds([UB_KIND_PAEDAGOGIK, UB_KIND_FACH, UB_KIND_PAEDAGOGIK])
    assert result == (UB_KIND_PAEDAGOGIK, UB_KIND_FACH)


def test_normalize_ub_kinds_allows_empty_selection_for_zusatzbesuch():
    assert normalize_ub_kinds([]) == tuple()


def test_parse_ub_yy_mm_dd_supports_plan_row_format():
    assert parse_ub_yy_mm_dd("31-03-26") == "26-03-31"


def test_build_ub_stem_produces_lowercase_prefix_and_date_only():
    assert build_ub_stem("31-03-26") == "ub 26-03-31"


def test_build_ub_stem_uses_fallback_for_empty_date():
    assert build_ub_stem("") == "ub 00-00-00"


def test_ub_stem_from_date_text_round_trips_to_string():
    stem = UbStem.from_date_text("31-03-26")
    assert str(stem) == "ub 26-03-31"


def test_ub_stem_date_returns_correct_date():
    stem = UbStem.from_date_text("31-03-26")
    assert stem.date() == date(2026, 3, 31)


def test_ub_stem_parse_accepts_current_format():
    stem = UbStem.parse("ub 26-03-31")
    assert stem is not None
    assert str(stem) == "ub 26-03-31"


def test_ub_stem_parse_rejects_old_uppercase_format_with_title():
    assert UbStem.parse("UB 26-03-31 Informationen und Daten") is None


def test_ub_stem_parse_rejects_empty_and_garbage():
    assert UbStem.parse("") is None
    assert UbStem.parse("random text") is None


def test_parse_ub_date_from_stem_returns_none_for_old_format():
    assert parse_ub_date_from_stem("UB 26-03-31 Informationen und Daten") is None


def test_parse_ub_date_from_stem_returns_date_for_new_format():
    assert parse_ub_date_from_stem("ub 26-03-31") == date(2026, 3, 31)
