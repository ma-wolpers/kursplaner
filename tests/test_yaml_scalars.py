"""Tests für die symmetrische Maskierung/Rückwandlung von YAML-Skalaren."""

import pytest

from kursplaner.core.domain.yaml_registry import LESSON_SCHEMA, parse_yaml_frontmatter, render_yaml_frontmatter
from kursplaner.core.domain.yaml_scalars import decode_yaml_scalar, yaml_double_quote

_TRICKY_TEXTS = [
    "einfach",
    'AB "Brüche"',
    "Pfad C:\\Users\\x",
    "Ende mit Backslash \\",
    'Backslash vor Quote \\"',
    "\\\\ doppelt",
    "[[Material/AB.pdf|AB 1]]",
    "",
]


@pytest.mark.parametrize("text", _TRICKY_TEXTS)
def test_quote_then_decode_roundtrips(text):
    assert decode_yaml_scalar(yaml_double_quote(text)) == text


def test_quote_escapes_backslash_before_quote():
    assert yaml_double_quote('a"b\\c') == '"a\\"b\\\\c"'


def test_decode_keeps_unknown_escape_sequences_from_legacy_values():
    """Altbestand ohne Maskierung (z. B. Windows-Pfad) behält seine Bedeutung."""
    assert decode_yaml_scalar('"C:\\Users\\x"') == "C:\\Users\\x"


def test_decode_unquoted_value_keeps_legacy_strip_behavior():
    assert decode_yaml_scalar("Unterricht") == "Unterricht"
    assert decode_yaml_scalar('halb"') == "halb"


@pytest.mark.parametrize("text", [t for t in _TRICKY_TEXTS if t])
def test_rendered_list_entries_roundtrip_through_project_parser(text):
    """Regression: Listeneinträge mit ``"``/``\\`` erzeugten ungültiges bzw. wachsendes YAML."""
    rendered = render_yaml_frontmatter(
        ["Stundentyp", "Dauer", "Stundenthema", "Material"],
        {"Stundentyp": "Unterricht", "Dauer": "2", "Stundenthema": "X", "Material": [text, "zweiter"]},
    )

    data, _ = parse_yaml_frontmatter(rendered, LESSON_SCHEMA)

    assert data["Material"] == [text, "zweiter"]


def test_rendered_link_scalar_with_quote_roundtrips_through_project_parser():
    value = '[[Thema "A"]]'
    rendered = render_yaml_frontmatter(
        ["Stundentyp", "Dauer", "Stundenthema", "Oberthema"],
        {"Stundentyp": "Unterricht", "Dauer": "2", "Stundenthema": "X", "Oberthema": value},
    )

    data, _ = parse_yaml_frontmatter(rendered, LESSON_SCHEMA)

    assert data["Oberthema"] == value
