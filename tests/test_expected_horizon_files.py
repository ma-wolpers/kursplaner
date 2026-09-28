"""Tests für Default-Dateinamen und Link-Form eines Kompetenzhorizonts."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from kursplaner.core.domain.expected_horizon_files import (
    build_horizon_link,
    default_adhoc_horizon_filename,
    default_lzk_horizon_filename,
    resolve_horizon_link,
)

NOW = datetime(2026, 9, 29, 15, 30)


def test_lzk_default_name_lists_topics_readably():
    name = default_lzk_horizon_filename(
        ["Potenzfunktionen", "Exponentialfunktionen"], lzk_date=date(2026, 10, 14), created_at=NOW
    )

    assert name == "KH LZK 2026-10-14 - Potenzfunktionen + Exponentialfunktionen (2026-09-29 1530).md"


def test_more_than_three_topics_are_abbreviated_with_weitere():
    name = default_lzk_horizon_filename(["A", "B", "C", "D"], lzk_date=date(2026, 10, 14), created_at=NOW)

    assert " - A + B + C + weitere (" in name


def test_forbidden_characters_are_removed_and_long_topic_part_is_shortened():
    long_topic = "Sehr langes Thema " * 8
    name = default_lzk_horizon_filename(
        ['Kap. 3: "Potenzen"/Wurzeln?', long_topic], lzk_date=date(2026, 10, 14), created_at=NOW
    )
    topic_part = name.split(" - ", 1)[1].rsplit(" (", 1)[0]

    assert "Kap. 3 PotenzenWurzeln" in topic_part
    assert not any(char in name for char in '\\/:*?"<>|#^[]')
    assert len(topic_part) <= 80 and topic_part.endswith("…")


def test_adhoc_default_name_uses_cutoff_and_extension():
    name = default_adhoc_horizon_filename(["A"], cutoff_date=date(2026, 10, 7), created_at=NOW, extension=".pdf")

    assert name == "KH bis 2026-10-07 - A (2026-09-29 1530).pdf"


def test_link_form_depends_on_location(tmp_path: Path):
    vault = tmp_path / "Vault"
    course = vault / "Unterricht" / "Kurs"

    assert build_horizon_link(course / "KH.md", course_dir=course, vault_root=vault) == "[[KH]]"
    assert build_horizon_link(vault / "Archiv" / "KH x.md", course_dir=course, vault_root=vault) == "[[Archiv/KH x]]"
    assert build_horizon_link(tmp_path / "Extern" / "KH.md", course_dir=course, vault_root=vault) is None
    assert build_horizon_link(vault / "Archiv" / "KH.md", course_dir=course, vault_root=None) is None


def test_resolve_is_inverse_of_build_and_keeps_dots_in_names(tmp_path: Path):
    vault = tmp_path / "Vault"
    course = vault / "Unterricht" / "Kurs"
    target = vault / "Archiv" / "KH Kap. 3.md"

    link = build_horizon_link(target, course_dir=course, vault_root=vault)

    assert resolve_horizon_link(link, course_dir=course, vault_root=vault) == target
    assert resolve_horizon_link("[[KH]]", course_dir=course, vault_root=None) == course / "KH.md"
    assert resolve_horizon_link("[[Archiv/KH]]", course_dir=course, vault_root=None) is None
    assert resolve_horizon_link("", course_dir=course, vault_root=vault) is None
