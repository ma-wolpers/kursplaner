from kursplaner.core.domain.kompetenzgraph_mapping import parse_kompetenz_node_from_raw
from tests.kompetenzgraph_test_support import make_source_ref

_VALID_KC_ZUORDNUNG = [
    {
        "bundesland": "Niedersachsen",
        "schulform": "Gymnasium",
        "niveau": None,
        "jahrgang": 8,
        "anforderung": "basis",
        "kc_verweis": "Ein wörtliches Zitat.",
    }
]


def _source() -> object:
    return make_source_ref("GF-49")


def test_parses_full_valid_frontmatter():
    frontmatter = {
        "oberkompetenzen": ["[[RF-3]]"],
        "primarer_bereich": "[[I-Raum und Form]]",
        "prozessbereiche": ["[[P-Darstellen]]"],
        "voraussetzungen": ["[[GF-48]]"],
        "offene_voraussetzungen": ["Grundverständnis Sek I"],
        "kc_zuordnung": _VALID_KC_ZUORDNUNG,
        "status": "entwurf",
    }
    body = "# Titel der Kompetenz\n\nWeiterer Text."

    node, issues = parse_kompetenz_node_from_raw(frontmatter, body, node_id="GF-49", source=_source())

    assert issues == ()
    assert node is not None
    assert node.id == "GF-49"
    assert node.oberkompetenzen_ids == ("RF-3",)
    assert node.primarer_bereich_id == "I-Raum und Form"
    assert node.prozessbereich_ids == ("P-Darstellen",)
    assert node.voraussetzungen_ids == ("GF-48",)
    assert node.offene_voraussetzungen == ("Grundverständnis Sek I",)
    assert node.status == "entwurf"
    assert node.title == "Titel der Kompetenz"


def test_missing_primarer_bereich_is_hard_error():
    frontmatter = {"kc_zuordnung": _VALID_KC_ZUORDNUNG}

    node, issues = parse_kompetenz_node_from_raw(frontmatter, "", node_id="GF-49", source=_source())

    assert node is None
    assert any(issue.field == "primarer_bereich" and issue.severity == "error" for issue in issues)


def test_empty_kc_zuordnung_is_hard_error():
    frontmatter = {"primarer_bereich": "[[I-Test]]", "kc_zuordnung": []}

    node, issues = parse_kompetenz_node_from_raw(frontmatter, "", node_id="GF-49", source=_source())

    assert node is None
    assert any(issue.field == "kc_zuordnung" for issue in issues)


def test_unresolvable_wikilink_in_optional_list_is_soft_error():
    frontmatter = {
        "primarer_bereich": "[[I-Test]]",
        "oberkompetenzen": ["nicht-ein-wikilink", "[[GF-1]]"],
        "kc_zuordnung": _VALID_KC_ZUORDNUNG,
    }

    node, issues = parse_kompetenz_node_from_raw(frontmatter, "", node_id="GF-49", source=_source())

    assert node is not None
    assert node.oberkompetenzen_ids == ("GF-1",)
    assert any(issue.field == "oberkompetenzen" and issue.severity == "warning" for issue in issues)


def test_offene_voraussetzungen_is_never_resolved_as_wikilinks():
    frontmatter = {
        "primarer_bereich": "[[I-Test]]",
        "offene_voraussetzungen": ["[[sieht-aus-wie-ein-link]]", "Freitext ohne Klammern"],
        "kc_zuordnung": _VALID_KC_ZUORDNUNG,
    }

    node, _issues = parse_kompetenz_node_from_raw(frontmatter, "", node_id="GF-49", source=_source())

    assert node is not None
    assert node.offene_voraussetzungen == ("[[sieht-aus-wie-ein-link]]", "Freitext ohne Klammern")


def test_invalid_status_falls_back_to_entwurf_with_warning():
    frontmatter = {
        "primarer_bereich": "[[I-Test]]",
        "kc_zuordnung": _VALID_KC_ZUORDNUNG,
        "status": "unbekannt",
    }

    node, issues = parse_kompetenz_node_from_raw(frontmatter, "", node_id="GF-49", source=_source())

    assert node is not None
    assert node.status == "entwurf"
    assert any(issue.field == "status" and issue.severity == "warning" for issue in issues)


def test_title_falls_back_to_kc_verweis_when_body_has_no_heading():
    frontmatter = {"primarer_bereich": "[[I-Test]]", "kc_zuordnung": _VALID_KC_ZUORDNUNG}

    node, _issues = parse_kompetenz_node_from_raw(frontmatter, "Kein Heading hier.", node_id="GF-49", source=_source())

    assert node.title == "Ein wörtliches Zitat."


def test_title_falls_back_to_node_id_when_nothing_else_available():
    kc_zuordnung_ohne_zitat = [{**_VALID_KC_ZUORDNUNG[0], "kc_verweis": ""}]
    frontmatter = {"primarer_bereich": "[[I-Test]]", "kc_zuordnung": kc_zuordnung_ohne_zitat}

    node, _issues = parse_kompetenz_node_from_raw(frontmatter, "", node_id="GF-49", source=_source())

    assert node.title == "GF-49"


def test_empty_optional_lists_default_to_empty_tuples():
    frontmatter = {"primarer_bereich": "[[I-Test]]", "kc_zuordnung": _VALID_KC_ZUORDNUNG, "status": "entwurf"}

    node, issues = parse_kompetenz_node_from_raw(frontmatter, "", node_id="GF-49", source=_source())

    assert issues == ()
    assert node.oberkompetenzen_ids == ()
    assert node.voraussetzungen_ids == ()
    assert node.prozessbereich_ids == ()
    assert node.offene_voraussetzungen == ()
