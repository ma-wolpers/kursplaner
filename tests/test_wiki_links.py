from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.wiki_links import build_wiki_link
from kursplaner.infrastructure.repositories.plan_repository import FileSystemPlanRepository
from kursplaner.infrastructure.repositories.plan_table_file_repository import create_linked_lesson_file


def test_build_wiki_link_formats_target_and_alias():
    built = build_wiki_link(" gruen-6 ]", " Lautstaerke [ im Raum ")

    assert built == "[[gruen-6|Lautstaerke im Raum]]"


def test_create_linked_lesson_file_writes_balanced_wiki_link(tmp_path):
    plan_path = tmp_path / "Informatik" / "Informatik.md"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text("", encoding="utf-8")

    table = PlanTableData(
        markdown_path=plan_path,
        headers=["Datum", "Stunden", "Inhalt"],
        rows=[["2026-03-09", "2", ""]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={"Lerngruppe": "[[gruen-6"},
    )

    lesson_path = create_linked_lesson_file(
        plan_table=table,
        row_index=0,
        lesson_topic="Binaerzahlen",
        default_hours=2,
    )

    assert lesson_path.exists()
    inhalt_value = table.rows[0][2]
    assert inhalt_value.startswith("[[")
    assert inhalt_value.endswith("]]")
    assert "|" not in inhalt_value
    assert lesson_path.stem in inhalt_value


def test_create_linked_lesson_file_collision_uses_full_stem_with_numeric_suffix(tmp_path):
    plan_path = tmp_path / "Informatik" / "Informatik.md"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text("", encoding="utf-8")

    einheiten_dir = plan_path.parent / "Einheiten"
    einheiten_dir.mkdir(parents=True)
    (einheiten_dir / "lila-5 03-10 Hardware.md").write_text(
        "---\nStundentyp: Unterricht\nDauer: 2\nStundenthema: Hardware\n---\n", encoding="utf-8"
    )

    table = PlanTableData(
        markdown_path=plan_path,
        headers=["Datum", "Stunden", "Inhalt"],
        rows=[["10-03-26", "2", ""]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={"Lerngruppe": "[[lila-5]]"},
    )

    lesson_path = create_linked_lesson_file(
        plan_table=table,
        row_index=0,
        lesson_topic="Hardware",
        default_hours=2,
    )

    assert lesson_path.exists()
    assert lesson_path.stem == "lila-5 03-10 Hardware 2"
    assert table.rows[0][2] == "[[lila-5 03-10 Hardware 2]]"


def test_write_plan_metadata_uses_valid_wiki_link(tmp_path):
    markdown_path = tmp_path / "Plan.md"
    markdown_path.write_text("# Plan\n", encoding="utf-8")

    repo = FileSystemPlanRepository()
    repo.write_plan_metadata(markdown_path, "gruen-6]", "Informatik", 6)

    text = markdown_path.read_text(encoding="utf-8")
    assert 'Lerngruppe: "[[gruen-6]]"' in text
    assert 'Kursfach: "Informatik"' in text


def test_write_plan_metadata_persists_competency_fields(tmp_path):
    markdown_path = tmp_path / "Plan.md"
    markdown_path.write_text("# Plan\n", encoding="utf-8")

    repo = FileSystemPlanRepository()
    repo.write_plan_metadata(
        markdown_path,
        "gruen-6",
        "Informatik",
        8,
        kc_profile_label="Informatik Sek I (5-9)",
        process_competencies=(
            "P 1.1 zerlegen Problemstellungen in geeignete Teilprobleme",
            "P 2.2 setzen ihre Problemloesungen in ausfuehrbare Prozesse um",
        ),
        content_competency="I 2.2 entwerfen Algorithmen und stellen diese geeignet dar",
    )

    text = markdown_path.read_text(encoding="utf-8")
    assert 'KC-Profil: "Informatik Sek I (5-9)"' in text
    assert "Kompetenzen:" in text
    assert 'Stundenziel: "I 2.2 entwerfen Algorithmen und stellen diese geeignet dar"' in text
