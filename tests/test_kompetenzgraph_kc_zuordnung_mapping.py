from kursplaner.core.domain.kompetenzgraph_kc_zuordnung_mapping import parse_kc_zuordnung_list


def _raw_entry(**overrides):
    base = {
        "bundesland": "Niedersachsen",
        "schulform": "Gymnasium",
        "niveau": None,
        "jahrgang": 8,
        "anforderung": "basis",
        "kc_verweis": "Ein Zitat.",
    }
    base.update(overrides)
    return base


def test_parses_single_valid_entry():
    entries, issues = parse_kc_zuordnung_list([_raw_entry()])

    assert issues == []
    assert len(entries) == 1
    assert entries[0].bundesland == "Niedersachsen"
    assert entries[0].jahrgang == 8


def test_non_list_raw_value_is_hard_error():
    entries, issues = parse_kc_zuordnung_list("nicht-eine-liste")

    assert entries == ()
    assert len(issues) == 1
    assert issues[0].severity == "error"


def test_missing_raw_value_is_hard_error():
    entries, issues = parse_kc_zuordnung_list(None)

    assert entries == ()
    assert issues[0].severity == "error"


def test_non_dict_entry_is_soft_error_and_dropped():
    entries, issues = parse_kc_zuordnung_list(["nicht-ein-dict"])

    assert entries == ()
    assert len(issues) == 1
    assert issues[0].severity == "warning"


def test_invalid_anforderung_is_soft_error_and_dropped():
    entries, issues = parse_kc_zuordnung_list([_raw_entry(anforderung="ungueltig")])

    assert entries == ()
    assert len(issues) == 1
    assert issues[0].severity == "warning"


def test_empty_niveau_becomes_none():
    entries, _issues = parse_kc_zuordnung_list([_raw_entry(niveau="")])

    assert entries[0].niveau is None


def test_string_jahrgang_is_parsed_to_int():
    entries, _issues = parse_kc_zuordnung_list([_raw_entry(jahrgang="8")])

    assert entries[0].jahrgang == 8


def test_empty_kc_verweis_is_allowed():
    entries, issues = parse_kc_zuordnung_list([_raw_entry(kc_verweis="")])

    assert issues == []
    assert entries[0].kc_verweis == ""


def test_duplicate_combination_is_dropped_with_warning():
    entries, issues = parse_kc_zuordnung_list([_raw_entry(), _raw_entry()])

    assert len(entries) == 1
    assert len(issues) == 1
    assert issues[0].severity == "warning"


def test_multiple_entries_with_different_combinations_are_all_kept():
    entries, issues = parse_kc_zuordnung_list([_raw_entry(jahrgang=8), _raw_entry(jahrgang=11)])

    assert issues == []
    assert len(entries) == 2
