from kursplaner.core.usecases.ub_markdown_sections import parse_list_section, parse_reflection


def test_parse_list_section_reads_bullets_under_heading():
    body = "## Professionalisierungsschritte\n- eins\n- zwei\n\n## Nutzbare Ressourcen\n- ressource"

    assert parse_list_section(body, "Professionalisierungsschritte") == ["eins", "zwei"]
    assert parse_list_section(body, "Nutzbare Ressourcen") == ["ressource"]


def test_parse_list_section_missing_heading_returns_empty_list():
    assert parse_list_section("# Reflexion\ntext", "Professionalisierungsschritte") == []


def test_parse_reflection_reads_text_between_h1_and_next_h2():
    body = "# Reflexion\n\nGut gelaufen.\n\n## Professionalisierungsschritte\n- eins"

    assert parse_reflection(body) == "Gut gelaufen."


def test_parse_reflection_missing_heading_returns_empty_string():
    assert parse_reflection("## Professionalisierungsschritte\n- eins") == ""


def test_reflection_with_embedded_sub_heading_stays_part_of_reflection_migration_regression():
    """Semantik-Regressionstest (Konsolidierung auf markdown_sections.py): eine
    Unterueberschrift (Ebene != 2) innerhalb der Reflexion bleibt Teil des Reflexionstexts,
    der Abschnitt endet weiterhin erst an der naechsten Ebene-2-Ueberschrift."""
    body = (
        "# Reflexion\n\n"
        "Einleitung.\n\n"
        "### Teilaspekt\n\n"
        "Mehr Text.\n\n"
        "## Professionalisierungsschritte\n- eins"
    )

    reflection = parse_reflection(body)

    assert "Einleitung." in reflection
    assert "### Teilaspekt" in reflection
    assert "Mehr Text." in reflection
    assert parse_list_section(body, "Professionalisierungsschritte") == ["eins"]
