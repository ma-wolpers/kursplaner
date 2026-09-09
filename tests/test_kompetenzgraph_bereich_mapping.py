from kursplaner.core.domain.kompetenzgraph_bereich_mapping import parse_bereich_node_from_raw
from tests.kompetenzgraph_test_support import make_source_ref


def test_parses_inhaltsbereich_with_kuerzel_and_title():
    body = "# Raum und Form (RF)\n\nKürzel: `RF`\n\nGeometrische Figuren."

    node, issues = parse_bereich_node_from_raw(
        body, node_id="I-Raum und Form", source=make_source_ref("I-Raum und Form")
    )

    assert issues == ()
    assert node is not None
    assert node.kind == "inhaltsbereich"
    assert node.kuerzel == "RF"
    assert node.title == "Raum und Form (RF)"
    assert node.body_markdown == body


def test_parses_prozessbereich_from_p_prefix():
    body = "# Argumentieren\n\nKürzel: `AR`"

    node, _issues = parse_bereich_node_from_raw(
        body, node_id="P-Argumentieren", source=make_source_ref("P-Argumentieren")
    )

    assert node is not None
    assert node.kind == "prozessbereich"
    assert node.kuerzel == "AR"


def test_unknown_prefix_is_hard_error():
    node, issues = parse_bereich_node_from_raw("# Egal", node_id="X-Unbekannt", source=make_source_ref("X-Unbekannt"))

    assert node is None
    assert issues[0].severity == "error"


def test_missing_kuerzel_line_is_soft_warning_with_empty_kuerzel():
    node, issues = parse_bereich_node_from_raw(
        "# Titel ohne Kuerzel", node_id="I-Test", source=make_source_ref("I-Test")
    )

    assert node is not None
    assert node.kuerzel == ""
    assert issues[0].severity == "warning"


def test_title_falls_back_to_node_id_without_heading():
    node, _issues = parse_bereich_node_from_raw("Kürzel: `T`", node_id="I-Test", source=make_source_ref("I-Test"))

    assert node.title == "I-Test"
