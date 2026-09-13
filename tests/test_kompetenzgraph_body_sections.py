from kursplaner.core.domain.kompetenzgraph_mapping import split_kompetenz_body_sections


def test_no_heading_at_all():
    sections = split_kompetenz_body_sections("Nur Freitext ohne jede Ueberschrift.")

    assert sections.beispiel_text == ""
    assert sections.rest_text == "Nur Freitext ohne jede Ueberschrift."


def test_title_only_no_beispiel_section():
    sections = split_kompetenz_body_sections("# Titel der Kompetenz\n\nEin Absatz ohne Beispiel-Ueberschrift.")

    assert sections.beispiel_text == ""
    assert sections.rest_text == "Ein Absatz ohne Beispiel-Ueberschrift."


def test_title_and_beispiel_only():
    sections = split_kompetenz_body_sections("# Titel\n\n## Beispiel\n\nErlaeutere den Zusammenhang.")

    assert sections.beispiel_text == "Erlaeutere den Zusammenhang."
    assert sections.rest_text == ""


def test_pretext_beispiel_and_posttext_with_further_heading():
    body = (
        "# Titel\n\nEinleitender Text vor dem Beispiel.\n\n"
        "## Beispiel\n\nDas eigentliche Beispiel.\n\n"
        "## Weiterfuehrend\n\nZusaetzlicher Text danach."
    )

    sections = split_kompetenz_body_sections(body)

    assert sections.beispiel_text == "Das eigentliche Beispiel."
    assert "Einleitender Text vor dem Beispiel." in sections.rest_text
    assert "## Weiterfuehrend" in sections.rest_text
    assert "Zusaetzlicher Text danach." in sections.rest_text
    assert "Das eigentliche Beispiel." not in sections.rest_text


def test_beispiel_heading_is_case_insensitive():
    sections = split_kompetenz_body_sections("# Titel\n\n## BEISPIEL\n\nText.")

    assert sections.beispiel_text == "Text."


def test_beispiel_heading_tolerates_surrounding_whitespace():
    sections = split_kompetenz_body_sections("# Titel\n\n##   Beispiel   \n\nText.")

    assert sections.beispiel_text == "Text."


def test_empty_beispiel_section_immediately_followed_by_another_heading():
    sections = split_kompetenz_body_sections("# Titel\n\n## Beispiel\n## Weiter\n\nText.")

    assert sections.beispiel_text == ""
    assert "## Weiter" in sections.rest_text


def test_empty_body_text():
    sections = split_kompetenz_body_sections("")

    assert sections.beispiel_text == ""
    assert sections.rest_text == ""


def test_beispiel_with_embedded_sub_heading_ends_before_it_migration_regression():
    """Semantik-Regressionstest (Konsolidierung auf markdown_sections.py): eine
    Unterueberschrift direkt im Beispiel-Abschnitt beendet ihn weiterhin (any-level-stop),
    exakt wie vor der Migration auf `extract_section()`."""
    body = "# Titel\n\n## Beispiel\n\nText im Beispiel.\n\n### Unterpunkt\n\nText im Unterpunkt."

    sections = split_kompetenz_body_sections(body)

    assert sections.beispiel_text == "Text im Beispiel."
    assert "### Unterpunkt" in sections.rest_text
    assert "Text im Unterpunkt." in sections.rest_text
