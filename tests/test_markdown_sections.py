from kursplaner.core.domain.markdown_sections import (
    derive_first_heading_title,
    extract_bullet_items,
    extract_section,
    find_heading_line_index,
)

_NESTED = (
    "## Abschnitt\n"
    "Text\n"
    "### Unterabschnitt\n"
    "mehr Text\n"
    "## Naechster Abschnitt\n"
    "weiter"
)


def test_derive_first_heading_title_returns_first_heading():
    assert derive_first_heading_title("# Titel\n\nText.") == "Titel"


def test_derive_first_heading_title_does_not_pick_a_later_heading():
    """Regressionstest: eine ZWEITE Ueberschrift im Dokument darf nicht versehentlich zum
    Ergebnis werden -- die Funktion liefert immer die ERSTE gefundene Ueberschrift."""
    text = "# Erste Ueberschrift\n\nText.\n\n## Zweite Ueberschrift\n\nMehr Text."
    assert derive_first_heading_title(text) == "Erste Ueberschrift"


def test_derive_first_heading_title_none_without_any_heading():
    assert derive_first_heading_title("Nur Freitext.") is None


def test_extract_section_stop_at_level_none_ends_at_any_level():
    assert extract_section(_NESTED, "Abschnitt", stop_at_level=None) == "Text"


def test_extract_section_stop_at_level_2_treats_sub_heading_as_part_of_section():
    section = extract_section(_NESTED, "Abschnitt", stop_at_level=2)
    assert section == "Text\n### Unterabschnitt\nmehr Text"


def test_extract_section_target_level_constrains_which_heading_counts_as_a_match():
    text = "### Ueberschrift\nfalsche Ebene\n\n## Ueberschrift\nrichtige Ebene\n\n## Weiter"
    assert extract_section(text, "Ueberschrift", target_level=None) == "falsche Ebene"
    assert extract_section(text, "Ueberschrift", target_level=2) == "richtige Ebene"


def test_extract_section_returns_none_when_heading_not_found():
    assert extract_section("# Titel\n\nText.", "Nicht Vorhanden") is None


def test_extract_section_empty_when_heading_immediately_followed_by_next_heading():
    assert extract_section("## Eins\n## Zwei\ntext", "Eins", stop_at_level=None) == ""


def test_extract_section_case_insensitive_by_default():
    assert extract_section("## BEISPIEL\ntext", "beispiel") == "text"


def test_extract_section_case_sensitive_when_requested():
    assert extract_section("## BEISPIEL\ntext", "beispiel", case_sensitive=True) is None
    assert extract_section("## beispiel\ntext", "beispiel", case_sensitive=True) == "text"


def test_find_heading_line_index_locates_named_heading():
    lines = ["# Titel", "", "## Abschnitt", "text"]
    assert find_heading_line_index(lines, "Abschnitt") == 2


def test_find_heading_line_index_not_found_returns_minus_one():
    lines = ["# Titel", "text"]
    assert find_heading_line_index(lines, "Fehlt") == -1


def test_find_heading_line_index_with_none_matches_any_heading_text():
    lines = ["text", "## Irgendeine Ueberschrift", "mehr"]
    assert find_heading_line_index(lines, None) == 1


def test_find_heading_line_index_respects_start_offset():
    lines = ["## Eins", "## Zwei", "## Drei"]
    assert find_heading_line_index(lines, None, start=1) == 1
    assert find_heading_line_index(lines, None, start=2) == 2


def test_extract_bullet_items_filters_and_strips_dash_lines():
    section = "Intro\n- eins\n- zwei\nkein bullet\n-   drei  "
    assert extract_bullet_items(section) == ["eins", "zwei", "drei"]


def test_extract_bullet_items_empty_without_any_bullets():
    assert extract_bullet_items("nur Text") == []
