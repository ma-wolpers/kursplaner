"""Leiter-Ablage in der Sequenzdatei: Abschnitt schreiben/lesen, Rest unangetastet, Schutz vor dem Aufräumen."""

from __future__ import annotations

import pytest
from test_sequence_plan_repository import _build_table

from kursplaner.core.domain.sequence_ladder import LadderBlock, LadderRung, SequenceLadder
from kursplaner.core.domain.sequence_ladder_codec import LadderFormatError
from kursplaner.infrastructure.repositories.sequence_plan_repository import FileSystemSequencePlanRepository

LADDER = SequenceLadder((LadderRung((LadderBlock("Eigen"), LadderBlock("Netz", "Mat-RF-1")), (), ("Idee",)),))


@pytest.fixture
def sequence(tmp_path):
    plan_dir = tmp_path / "M GK test-1 26-2"
    plan_dir.mkdir()
    plan_path = plan_dir / "M GK test-1 26-2.md"
    plan_path.write_text("# Kursplan\n", encoding="utf-8")
    repo = FileSystemSequencePlanRepository()
    return repo, repo.ensure_sequence_document(table=_build_table(plan_path), sequence_name="Brüche")


def test_ladder_roundtrip_places_section_before_export_and_keeps_the_rest(sequence):
    repo, path = sequence
    repo.write_brainstorming(sequence_path=path, brainstorming_text="Brainstorm")
    repo.write_goal_and_focus_competencies(sequence_path=path, sequenzziel="Ziel", leitkompetenzen=("K1",))
    repo.write_ladder_ablage(sequence_path=path, ablage=LADDER)
    text = path.read_text(encoding="utf-8")
    assert text.index("## Brainstorming") < text.index("## Sequenzleiter") < text.index("## Export")
    assert repo.read_ladder_ablage(path) == LADDER
    assert repo.read_brainstorming(path) == "Brainstorm"
    assert repo.read_goal_and_focus_competencies(path) == ("Ziel", ("K1",))


def test_rewrite_replaces_only_the_section_and_empty_ladder_removes_it(sequence):
    repo, path = sequence
    repo.write_ladder_ablage(sequence_path=path, ablage=LADDER)
    repo.write_ladder_ablage(sequence_path=path, ablage=SequenceLadder((LadderRung((LadderBlock("Nur"),)),)))
    assert path.read_text(encoding="utf-8").count("## Sequenzleiter") == 1
    repo.write_ladder_ablage(sequence_path=path, ablage=SequenceLadder())
    assert "## Sequenzleiter" not in path.read_text(encoding="utf-8")
    assert repo.read_ladder_ablage(path) == SequenceLadder()


def test_unchanged_ladder_is_not_written(sequence):
    repo, path = sequence
    repo.write_ladder_ablage(sequence_path=path, ablage=LADDER)
    before = path.stat().st_mtime_ns
    repo.write_ladder_ablage(sequence_path=path, ablage=LADDER)
    assert path.stat().st_mtime_ns == before


def test_export_table_sync_leaves_the_ladder_alone(sequence):
    repo, path = sequence
    repo.write_ladder_ablage(sequence_path=path, ablage=LADDER)
    lines = repo.render_markdown_table(headers=["A"], rows=[(("x",),)])
    repo.replace_trailing_table(sequence_path=path, table_lines=lines)
    assert repo.read_ladder_ablage(path) == LADDER


def test_ladder_protects_the_file_from_pruning_even_when_malformed(sequence):
    repo, path = sequence
    assert repo.is_trivial(path)
    repo.write_ladder_ablage(sequence_path=path, ablage=LADDER)
    assert not repo.is_trivial(path)
    path.write_text(path.read_text(encoding="utf-8").replace("- Ablage 1", "kaputt"), encoding="utf-8")
    assert not repo.is_trivial(path)
    assert repo.delete_if_trivial(path) is False
    with pytest.raises(LadderFormatError):
        repo.read_ladder_ablage(path)


def test_frontmatter_stays_byte_identical(sequence):
    repo, path = sequence
    head = path.read_text(encoding="utf-8").split("\n---", 1)[0]
    repo.write_ladder_ablage(sequence_path=path, ablage=LADDER)
    assert path.read_text(encoding="utf-8").startswith(head + "\n---")


def test_brainstorming_keeps_indentation_and_its_heading_when_emptied(sequence):
    repo, path = sequence
    repo.write_brainstorming(sequence_path=path, brainstorming_text="  - eingerückt\nzweite")
    assert repo.read_brainstorming(path) == "  - eingerückt\nzweite"
    repo.write_brainstorming(sequence_path=path, brainstorming_text="")
    text = path.read_text(encoding="utf-8")
    assert "## Brainstorming" in text and repo.read_brainstorming(path) == ""
    assert text.index("## Brainstorming") < text.index("## Export")
