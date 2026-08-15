from kursplaner.core.domain.topic_sequence_runs import (
    compute_topic_sequence_runs,
    find_run_for_row_index,
    row_lesson_type,
)
from tests.day_column_factory import make_day_column


def _day(*, row_index: int, kind: str, obert: str = "", group_name: str = ""):
    """Baut einen Tages-Eintrag in der jeweils realistischen Form.

    Ausfall-Tage haben in der echten Anwendung nie eine verlinkte Stundendatei
    (kein `[[Link]]` in der Planungstabelle) und tragen ihren Typ deshalb nur
    über den Thema/Ausfall-Textmarker, nicht über `yaml.Stundentyp` — genau
    die Form, die den ursprünglichen Bug (Ausfall bricht die Kette statt sie
    zu überspringen) verursacht hat.
    """
    if kind == "Ausfall":
        return make_day_column(row_index=row_index, thema_ausfall="X Krank")
    return make_day_column(
        row_index=row_index,
        yaml={"Stundentyp": kind, "Oberthema": obert},
        group_name=group_name,
    )


def test_two_adjacent_units_with_same_oberthema_form_one_run():
    day_columns = [
        _day(row_index=0, kind="Unterricht", obert="Algorithmen"),
        _day(row_index=1, kind="Unterricht", obert="Algorithmen"),
    ]

    runs = compute_topic_sequence_runs(day_columns)

    assert len(runs) == 1
    assert runs[0].oberthema == "Algorithmen"
    assert runs[0].member_row_indices == (0, 1)
    assert runs[0].member_count == 2


def test_plain_text_and_wiki_linked_oberthema_form_one_run():
    """Ein bewusst als Wiki-Link gespeichertes Oberthema (Obsidian-Verlinkung) darf die
    Sequenz nicht faelschlich abbrechen, nur weil die Schreibweise vom Klartext abweicht."""
    day_columns = [
        _day(row_index=0, kind="Unterricht", obert="EFl1 Potenzfunktionen", group_name="11.1"),
        _day(row_index=1, kind="Unterricht", obert="[[11.1 EFl1 Potenzfunktionen]]", group_name="11.1"),
    ]

    runs = compute_topic_sequence_runs(day_columns)

    assert len(runs) == 1
    assert runs[0].oberthema == "EFl1 Potenzfunktionen"
    assert runs[0].member_row_indices == (0, 1)


def test_different_oberthema_breaks_the_chain():
    day_columns = [
        _day(row_index=0, kind="Unterricht", obert="Algorithmen"),
        _day(row_index=1, kind="Unterricht", obert="Datenbanken"),
    ]

    runs = compute_topic_sequence_runs(day_columns)

    assert [run.oberthema for run in runs] == ["Algorithmen", "Datenbanken"]
    assert [run.member_row_indices for run in runs] == [(0,), (1,)]


def test_ausfall_is_skipped_and_does_not_break_the_chain():
    day_columns = [
        _day(row_index=0, kind="Unterricht", obert="Chemie"),
        _day(row_index=1, kind="Ausfall"),
        _day(row_index=2, kind="Unterricht", obert="Chemie"),
    ]

    runs = compute_topic_sequence_runs(day_columns)

    assert len(runs) == 1
    assert runs[0].member_row_indices == (0, 2)


def test_two_consecutive_ausfall_days_are_both_skipped():
    day_columns = [
        _day(row_index=0, kind="Unterricht", obert="KI"),
        _day(row_index=1, kind="Ausfall"),
        _day(row_index=2, kind="Ausfall"),
        _day(row_index=3, kind="Unterricht", obert="KI"),
    ]

    runs = compute_topic_sequence_runs(day_columns)

    assert len(runs) == 1
    assert runs[0].member_row_indices == (0, 3)


def test_row_lesson_type_recognizes_linkless_ausfall_via_marker():
    """Regressionstest: Ausfall-Tage ohne verlinkte Stundendatei (yaml={}) müssen
    trotzdem als "Ausfall" erkannt werden, nicht als leerer/unbekannter Typ."""
    assert row_lesson_type(make_day_column(thema_ausfall="X Krank")) == "Ausfall"


def test_hospitation_counts_as_chain_member():
    day_columns = [
        _day(row_index=0, kind="Unterricht", obert="Optik"),
        _day(row_index=1, kind="Hospitation", obert="Optik"),
        _day(row_index=2, kind="Unterricht", obert="Optik"),
    ]

    runs = compute_topic_sequence_runs(day_columns)

    assert len(runs) == 1
    assert runs[0].member_row_indices == (0, 1, 2)


def test_hospitation_without_own_oberthema_breaks_the_chain():
    day_columns = [
        _day(row_index=0, kind="Unterricht", obert="Optik"),
        _day(row_index=1, kind="Hospitation", obert=""),
        _day(row_index=2, kind="Unterricht", obert="Optik"),
    ]

    runs = compute_topic_sequence_runs(day_columns)

    assert [run.member_row_indices for run in runs] == [(0,), (2,)]


def test_non_adjacent_occurrences_of_same_oberthema_form_two_separate_runs():
    day_columns = [
        _day(row_index=0, kind="Unterricht", obert="Funktionen"),
        _day(row_index=1, kind="Unterricht", obert="Geometrie"),
        _day(row_index=2, kind="Unterricht", obert="Funktionen"),
    ]

    runs = compute_topic_sequence_runs(day_columns)

    assert len(runs) == 3
    assert runs[0].member_row_indices == (0,)
    assert runs[2].member_row_indices == (2,)
    assert runs[0] is not runs[2]


def test_empty_oberthema_does_not_form_a_run():
    day_columns = [
        _day(row_index=0, kind="Unterricht", obert=""),
        _day(row_index=1, kind="Unterricht", obert=""),
    ]

    runs = compute_topic_sequence_runs(day_columns)

    assert runs == []


def test_find_run_for_row_index_locates_member_and_returns_none_otherwise():
    day_columns = [
        _day(row_index=0, kind="Unterricht", obert="Mechanik"),
        _day(row_index=1, kind="Unterricht", obert="Mechanik"),
    ]
    runs = compute_topic_sequence_runs(day_columns)

    found = find_run_for_row_index(runs, 1)
    assert found is not None
    assert found.oberthema == "Mechanik"

    assert find_run_for_row_index(runs, 99) is None
