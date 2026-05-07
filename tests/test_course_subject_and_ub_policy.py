from kursplaner.core.domain.course_subject import normalize_course_subject, short_subject_for_course_subject
from kursplaner.core.domain.unterrichtsbesuch_policy import (
    UB_KIND_FACH,
    UB_KIND_PAEDAGOGIK,
    build_ub_stem,
    normalize_ub_kinds,
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


def test_build_ub_stem_uses_required_prefix_and_sanitized_title():
    stem = build_ub_stem("31-03-26", "Einheit: Funktionen/Graphen")
    assert stem == "UB 26-03-31 Einheit FunktionenGraphen"
