from kursplaner.adapters.gui.lesson_conversion_controller import MainWindowLessonConversionController

_extract = MainWindowLessonConversionController._extract_markdown_section_refs


def test_extracts_wikilink_targets_from_inhalte_section(tmp_path):
    path = tmp_path / "einheit.md"
    path.write_text(
        "---\nStundentyp: Unterricht\n---\n\n# Einheit\n\n## Inhalte\n- [[Thema A]]\n- [[Thema B]]\n\n## Methodik\n- [[Methode X]]",
        encoding="utf-8",
    )

    assert _extract(path, "Inhalte") == ["Thema A", "Thema B"]
    assert _extract(path, "Methodik") == ["Methode X"]


def test_prefers_wikilink_alias_over_target(tmp_path):
    path = tmp_path / "einheit.md"
    path.write_text("## Inhalte\n- [[Thema A|Anzeigename]]\n", encoding="utf-8")

    assert _extract(path, "Inhalte") == ["Anzeigename"]


def test_plain_text_bullet_without_wikilink_is_used_verbatim(tmp_path):
    path = tmp_path / "einheit.md"
    path.write_text("## Inhalte\n- Freitext ohne Link\n", encoding="utf-8")

    assert _extract(path, "Inhalte") == ["Freitext ohne Link"]


def test_sub_heading_inside_inhalte_section_stays_part_of_the_section_migration_regression(tmp_path):
    """Semantik-Regressionstest (Konsolidierung auf markdown_sections.py): eine
    Unterueberschrift innerhalb von ## Inhalte beendet den Abschnitt nicht (stop_at_level=2),
    nachfolgende Bullets darunter werden weiterhin erfasst."""
    path = tmp_path / "einheit.md"
    path.write_text(
        "---\nStundentyp: Unterricht\n---\n\n"
        "## Inhalte\n"
        "- [[Thema A]]\n"
        "### Vertiefung\n"
        "- [[Thema B]]\n\n"
        "## Methodik\n- [[Methode X]]",
        encoding="utf-8",
    )

    assert _extract(path, "Inhalte") == ["Thema A", "Thema B"]


def test_heading_match_is_case_insensitive_after_unification(tmp_path):
    """Vor der Konsolidierung war diese eine Stelle unbeabsichtigt case-sensitiv (kein
    IGNORECASE in der alten Regex) -- jetzt auf case-insensitiv vereinheitlicht wie die
    uebrigen vier Dialekte (siehe Implementierungsplan)."""
    path = tmp_path / "einheit.md"
    path.write_text("## inhalte\n- [[Thema A]]\n", encoding="utf-8")

    assert _extract(path, "Inhalte") == ["Thema A"]


def test_missing_heading_returns_empty_list(tmp_path):
    path = tmp_path / "einheit.md"
    path.write_text("## Methodik\n- [[Methode X]]\n", encoding="utf-8")

    assert _extract(path, "Inhalte") == []


def test_nonexistent_file_returns_empty_list(tmp_path):
    assert _extract(tmp_path / "fehlt.md", "Inhalte") == []
