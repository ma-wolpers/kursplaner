from kursplaner.core.domain.kompetenzgraph_filter_options import BereichFilterOption, compute_filter_options
from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from tests.kompetenzgraph_test_support import make_bereich, make_kc_zuordnung, make_node


def test_filter_options_are_derived_from_snapshot_not_hardcoded():
    mathe_node = make_node(
        "M-1",
        subject="Mathematik",
        status="entwurf",
        kc_zuordnung=(make_kc_zuordnung(bundesland="Niedersachsen", schulform="Gymnasium", jahrgang=11),),
    )
    informatik_node = make_node(
        "I-1",
        subject="Informatik",
        status="geprüft",
        kc_zuordnung=(make_kc_zuordnung(bundesland="Bayern", schulform="IGS", niveau="eA", jahrgang=8),),
    )
    inhaltsbereich = make_bereich("I-Test", kind="inhaltsbereich", title="Test-Inhalt")
    prozessbereich = make_bereich("P-Test", kind="prozessbereich", title="Test-Prozess")
    snapshot = build_kompetenz_graph_snapshot([mathe_node, informatik_node], [inhaltsbereich, prozessbereich])

    options = compute_filter_options(snapshot)

    assert options.subjects == ("Informatik", "Mathematik")
    assert options.jahrgaenge == (8, 11)
    assert options.schulformen == ("Gymnasium", "IGS")
    assert options.bundeslaender == ("Bayern", "Niedersachsen")
    assert options.niveaus == ("eA",)
    assert options.status_werte == ("entwurf", "geprüft")
    assert options.anforderungen == ("basis",)
    assert options.inhaltsbereiche == (BereichFilterOption("I-Test", "Mathematik", "Mat · Test-Inhalt"),)
    assert options.prozessbereiche == (BereichFilterOption("P-Test", "Mathematik", "Mat · Test-Prozess"),)


def test_filter_options_empty_snapshot_returns_empty_tuples():
    snapshot = build_kompetenz_graph_snapshot([], [])

    options = compute_filter_options(snapshot)

    assert options.subjects == ()
    assert options.jahrgaenge == ()


def test_bereich_options_are_grouped_by_subject_then_title_with_short_prefix():
    """IDs so gewählt, dass reine ID-Sortierung Mathe und Informatik mischen würde."""
    bereiche = [
        make_bereich("P-A-Mathe", subject="Mathematik", kind="prozessbereich", title="Kommunizieren (KO)"),
        make_bereich("P-B-Info", subject="Informatik", kind="prozessbereich", title="Implementieren (IM)"),
        make_bereich("P-C-Mathe", subject="Mathematik", kind="prozessbereich", title="Argumentieren (AR)"),
        make_bereich("P-D-Info", subject="Informatik", kind="prozessbereich", title="Begründen und Bewerten (BB)"),
    ]
    snapshot = build_kompetenz_graph_snapshot([], bereiche)

    options = compute_filter_options(snapshot)

    assert [option.label for option in options.prozessbereiche] == [
        "Inf · Begründen und Bewerten (BB)",
        "Inf · Implementieren (IM)",
        "Mat · Argumentieren (AR)",
        "Mat · Kommunizieren (KO)",
    ]
    assert [option.id for option in options.prozessbereiche] == ["P-D-Info", "P-B-Info", "P-C-Mathe", "P-A-Mathe"]


def test_bereich_options_keep_duplicate_titles_as_distinct_ids():
    """Daten-Drift: gleicher Titel in zwei Bereichs-Dateien darf keine Option verschlucken."""
    bereiche = [
        make_bereich("P-X2", kind="prozessbereich", title="Argumentieren"),
        make_bereich("P-X1", kind="prozessbereich", title="Argumentieren"),
    ]
    snapshot = build_kompetenz_graph_snapshot([], bereiche)

    options = compute_filter_options(snapshot)

    assert [option.id for option in options.prozessbereiche] == ["P-X1", "P-X2"]


def test_bereich_options_unknown_subject_falls_back_to_full_name():
    bereich = make_bereich("I-Lyrik", subject="Deutsch", kind="inhaltsbereich", title="Lyrik")
    snapshot = build_kompetenz_graph_snapshot([], [bereich])

    options = compute_filter_options(snapshot)

    assert options.inhaltsbereiche[0].label == "Deutsch · Lyrik"


def test_subjects_are_sorted_umlaut_robust():
    nodes = [make_node(f"N-{subject}", subject=subject) for subject in ("Physik", "Ökonomie", "Mathematik")]
    snapshot = build_kompetenz_graph_snapshot(nodes, [make_bereich("I-Test")])

    options = compute_filter_options(snapshot)

    assert options.subjects == ("Mathematik", "Ökonomie", "Physik")
