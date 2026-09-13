from kursplaner.core.domain.yaml_registry import (
    body_after_frontmatter,
    frontmatter_text,
    parse_stufe,
    render_yaml_frontmatter,
)


def test_body_after_frontmatter_strips_frontmatter_block():
    text = "---\nStundenthema: X\n---\n\nBody-Text\n"

    assert body_after_frontmatter(text) == "Body-Text\n"


def test_body_after_frontmatter_without_frontmatter_returns_text_unchanged():
    text = "# Kein Frontmatter\nBody"

    assert body_after_frontmatter(text) == text


def test_body_after_frontmatter_unterminated_frontmatter_returns_text_unchanged():
    text = "---\nStundenthema: X\nBody ohne schliessendes Frontmatter"

    assert body_after_frontmatter(text) == text


def test_body_after_frontmatter_strips_multiple_leading_blank_lines():
    text = "---\nStundenthema: X\n---\n\n\n\nBody"

    assert body_after_frontmatter(text) == "Body"


def test_frontmatter_text_returns_the_raw_yaml_block():
    text = "---\nStundenthema: X\n---\n\nBody-Text\n"

    assert frontmatter_text(text) == "Stundenthema: X"


def test_frontmatter_text_returns_none_without_frontmatter():
    assert frontmatter_text("# Kein Frontmatter\nBody") is None


def test_frontmatter_text_returns_none_when_unterminated():
    assert frontmatter_text("---\nStundenthema: X\nBody ohne schliessendes Frontmatter") is None


def test_body_after_frontmatter_and_frontmatter_text_have_different_error_semantics():
    """Vertrag explizit abgesichert: `body_after_frontmatter()` gibt bei fehlendem/kaputtem
    Frontmatter still den unveraenderten Text zurueck (Passthrough), waehrend
    `frontmatter_text()` denselben Fall als harten `None` signalisiert -- beide teilen sich
    dieselbe Grenzerkennung (`_frontmatter_bounds()`), unterscheiden sich aber bewusst in der
    Fehlerbehandlung."""
    broken = "---\nStundenthema: X\nBody ohne schliessendes Frontmatter"

    assert body_after_frontmatter(broken) == broken
    assert frontmatter_text(broken) is None


def test_render_yaml_frontmatter_renders_scalars_and_lists():
    rendered = render_yaml_frontmatter(
        ["Stundentyp", "Kompetenzen"],
        {"Stundentyp": "LZK", "Kompetenzen": ["PK1", "PK2"]},
    )

    assert rendered == '---\nStundentyp: LZK\nKompetenzen:\n  - "PK1"\n  - "PK2"\n---\n\n'


def test_render_yaml_frontmatter_skips_missing_key():
    rendered = render_yaml_frontmatter(["Stundentyp", "Oberthema"], {"Stundentyp": "Unterricht"})

    assert "Oberthema" not in rendered
    assert "Stundentyp: Unterricht" in rendered


def test_render_yaml_frontmatter_escapes_link_looking_scalar():
    rendered = render_yaml_frontmatter(["Oberthema"], {"Oberthema": "[[11.1 Potenzfunktionen]]"})

    assert 'Oberthema: "[[11.1 Potenzfunktionen]]"' in rendered


def test_render_yaml_frontmatter_renders_bool_as_lowercase():
    rendered = render_yaml_frontmatter(["Langentwurf"], {"Langentwurf": True})

    assert "Langentwurf: true" in rendered


def test_parse_stufe_accepts_full_1_to_13_range():
    assert parse_stufe("1") == 1
    assert parse_stufe(7) == 7
    assert parse_stufe("13") == 13


def test_parse_stufe_returns_none_for_missing_or_out_of_range():
    assert parse_stufe(None) is None
    assert parse_stufe("") is None
    assert parse_stufe("keine Zahl") is None
    assert parse_stufe("0") is None
    assert parse_stufe("14") is None
