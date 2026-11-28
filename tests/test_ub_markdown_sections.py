from kursplaner.core.usecases.ub_markdown_sections import new_ub_body, parse_reflection


def test_parse_reflection_reads_text_between_h1_and_next_h2():
    body = "# Reflexion\n\nGut gelaufen.\n\n## Eigene Notizen\n- eins"

    assert parse_reflection(body) == "Gut gelaufen."


def test_parse_reflection_missing_heading_returns_empty_string():
    assert parse_reflection("## Eigene Notizen\n- eins") == ""


def test_reflection_with_embedded_sub_heading_stays_part_of_reflection_migration_regression():
    """Semantik-Regressionstest (Konsolidierung auf markdown_sections.py): eine
    Unterueberschrift (Ebene != 2) innerhalb der Reflexion bleibt Teil des Reflexionstexts,
    der Abschnitt endet weiterhin erst an der naechsten Ebene-2-Ueberschrift."""
    body = "# Reflexion\n\nEinleitung.\n\n### Teilaspekt\n\nMehr Text.\n\n## Eigene Notizen\n- eins"

    reflection = parse_reflection(body)

    assert "Einleitung." in reflection
    assert "### Teilaspekt" in reflection
    assert "Mehr Text." in reflection
    assert "Eigene Notizen" not in reflection


def test_new_body_has_only_the_reflection():
    assert new_ub_body() == "# Reflexion\n"
    assert parse_reflection(new_ub_body("Gut gelaufen")) == "Gut gelaufen"
