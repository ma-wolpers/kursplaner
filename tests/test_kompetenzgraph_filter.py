from kursplaner.core.domain.kompetenzgraph_filter import (
    KompetenzGraphFilter,
    compute_visible_bereich_ids,
    compute_visible_node_ids,
    node_matches_filter,
)
from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from tests.kompetenzgraph_test_support import make_bereich, make_kc_zuordnung, make_node


def test_no_filter_matches_everything():
    node = make_node("A")

    assert node_matches_filter(node, KompetenzGraphFilter()) is True


def test_kc_zuordnung_criteria_must_match_the_same_entry():
    """Adversarial-Fall: Niedersachsen/11 und Bayern/8 auf demselben Knoten -- 'Niedersachsen + 8' darf nicht treffen."""
    node = make_node(
        "A",
        kc_zuordnung=(
            make_kc_zuordnung(bundesland="Niedersachsen", jahrgang=11),
            make_kc_zuordnung(bundesland="Bayern", jahrgang=8),
        ),
    )

    mixed_filter = KompetenzGraphFilter(bundesland="Niedersachsen", jahrgang=8)
    assert node_matches_filter(node, mixed_filter) is False

    matching_first_entry = KompetenzGraphFilter(bundesland="Niedersachsen", jahrgang=11)
    assert node_matches_filter(node, matching_first_entry) is True

    matching_second_entry = KompetenzGraphFilter(bundesland="Bayern", jahrgang=8)
    assert node_matches_filter(node, matching_second_entry) is True


def test_status_and_bereich_filters_are_node_level_not_per_entry():
    node = make_node(
        "A",
        status="entwurf",
        primarer_bereich_id="I-Test",
        prozessbereich_ids=("P-Prozess",),
        kc_zuordnung=(make_kc_zuordnung(), make_kc_zuordnung(bundesland="Bayern", jahrgang=13)),
    )

    assert node_matches_filter(node, KompetenzGraphFilter(status="geprüft")) is False
    assert node_matches_filter(node, KompetenzGraphFilter(status="entwurf")) is True
    assert node_matches_filter(node, KompetenzGraphFilter(inhaltsbereich_id="I-Anderes")) is False
    assert node_matches_filter(node, KompetenzGraphFilter(prozessbereich_id="P-Prozess")) is True


def test_subjects_none_or_empty_means_all_subjects():
    node = make_node("A", subject="Mathematik")

    assert node_matches_filter(node, KompetenzGraphFilter(subjects=None)) is True
    assert node_matches_filter(node, KompetenzGraphFilter(subjects=frozenset())) is True


def test_subjects_multiselect_is_or_combined_other_criteria_stay_and():
    mathe_node = make_node("M-1", subject="Mathematik", kc_zuordnung=(make_kc_zuordnung(jahrgang=8),))
    informatik_node = make_node("I-1", subject="Informatik", kc_zuordnung=(make_kc_zuordnung(jahrgang=8),))
    informatik_wrong_jahrgang = make_node(
        "I-2", subject="Informatik", kc_zuordnung=(make_kc_zuordnung(jahrgang=5),)
    )
    snapshot = build_kompetenz_graph_snapshot([mathe_node, informatik_node, informatik_wrong_jahrgang], [])

    both_subjects_filter = KompetenzGraphFilter(subjects=frozenset({"Mathematik", "Informatik"}), jahrgang=8)
    visible = compute_visible_node_ids(snapshot, both_subjects_filter)

    assert visible == frozenset({"M-1", "I-1"})

    single_subject_filter = KompetenzGraphFilter(subjects=frozenset({"Mathematik"}))
    assert compute_visible_node_ids(snapshot, single_subject_filter) == frozenset({"M-1"})


def test_compute_visible_bereich_ids_includes_hub_referenced_by_visible_node():
    bereich = make_bereich("I-Test", kind="inhaltsbereich")
    node = make_node("A", primarer_bereich_id="I-Test")
    snapshot = build_kompetenz_graph_snapshot([node], [bereich])

    visible_bereiche = compute_visible_bereich_ids(snapshot, frozenset({"A"}))

    assert visible_bereiche == frozenset({"I-Test"})


def test_compute_visible_bereich_ids_excludes_unresolved_targets():
    node = make_node("A", primarer_bereich_id="I-Nicht-Vorhanden")
    snapshot = build_kompetenz_graph_snapshot([node], [])

    assert compute_visible_bereich_ids(snapshot, frozenset({"A"})) == frozenset()
