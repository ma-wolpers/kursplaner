from kursplaner.core.domain.markdown_lists import render_markdown_bullet_section


def test_render_markdown_bullet_section_with_items():
    rendered = render_markdown_bullet_section("Inhalte", ["[[a]]", "[[b]]"])

    assert rendered == "## Inhalte\n\n- [[a]]\n- [[b]]"


def test_render_markdown_bullet_section_empty_list_renders_heading_only():
    rendered = render_markdown_bullet_section("Inhalte", [])

    assert rendered == "## Inhalte\n"


def test_render_markdown_bullet_section_placeholder_pattern_matches_ub_usage():
    """UB-Nutzung reproduziert den alten Platzhalter-Bullet, indem sie [""] statt [] übergibt."""
    rendered = render_markdown_bullet_section("Professionalisierungsschritte", [""])

    assert rendered == "## Professionalisierungsschritte\n\n- "
