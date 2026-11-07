"""``## Inhalte``/``## Methodik`` einer Einheit: lesen und schreiben über den gemeinsamen Abschnittsweg (synthetisch)."""

from __future__ import annotations

from kursplaner.core.usecases.lesson_commands_usecase import LessonCommandsUseCase
from kursplaner.infrastructure.repositories.lesson_repository import FileSystemLessonRepository

FRONT = "---\nStundentyp: Unterricht\n---\n\n"


def _commands():
    return LessonCommandsUseCase(FileSystemLessonRepository())


def _write(tmp_path, text, name="einheit.md"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_reads_link_targets_aliases_and_plain_bullets(tmp_path):
    path = _write(
        tmp_path,
        FRONT
        + "# Einheit\n\n## Inhalte\n- [[Thema A]]\n- [[Thema B|Anzeigename]]\n- Freitext\n\n## Methodik\n- [[Methode X]]",
    )
    assert _commands().read_lesson_sections(path) == (["Thema A", "Anzeigename", "Freitext"], ["Methode X"])


def test_sub_heading_inside_a_section_stays_part_of_it_and_heading_is_case_insensitive(tmp_path):
    path = _write(tmp_path, FRONT + "## inhalte\n- [[Thema A]]\n### Vertiefung\n- [[Thema B]]\n\n## Methodik\n- [[M]]")
    assert _commands().read_lesson_sections(path)[0] == ["Thema A", "Thema B"]


def test_missing_sections_and_missing_file_read_as_empty(tmp_path):
    assert _commands().read_lesson_sections(_write(tmp_path, FRONT + "Text\n")) == ([], [])
    assert _commands().read_lesson_sections(tmp_path / "fehlt.md") == ([], [])


def test_writing_replaces_instead_of_appending_and_keeps_the_rest(tmp_path):
    path = _write(tmp_path, FRONT + "# Einheit\n\nVerlauf\n\n## Inhalte\n- [[Alt]]\n\n## Notizen\nbleibt\n")
    commands = _commands()
    commands.update_lesson_sections(path, ["Neu"], ["Methode"])
    commands.update_lesson_sections(path, ["Neu"], ["Methode"])
    text = path.read_text(encoding="utf-8")
    assert text.count("## Inhalte") == 1 and text.count("## Methodik") == 1
    assert "- [[Neu]]" in text and "[[Alt]]" not in text and "## Notizen\nbleibt" in text
    assert commands.read_lesson_sections(path) == (["Neu"], ["Methode"])


def test_empty_list_removes_the_section(tmp_path):
    path = _write(tmp_path, FRONT + "## Inhalte\n- [[A]]\n\n## Methodik\n- [[M]]\n")
    _commands().update_lesson_sections(path, [], ["M"])
    assert "## Inhalte" not in path.read_text(encoding="utf-8")


def test_ebw_frontmatter_stays_byte_identical(tmp_path):
    front = "---\nStundentyp: Unterricht\ndocument_type: kurzentwurf\n---\n"
    path = _write(tmp_path, front + "#einstieg\nS> Hallo\n", name="u.ebw")
    _commands().update_lesson_sections(path, ["Thema"], [])
    assert path.read_text(encoding="utf-8").startswith(front)
