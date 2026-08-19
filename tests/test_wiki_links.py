from kursplaner.core.domain.course_rhythm import WeekdayRhythm
from kursplaner.core.domain.plan_table import PlanTableData, read_yaml_oberthema
from kursplaner.core.domain.wiki_links import build_dataview_lesson_link, build_wiki_link, strip_group_prefixed_link
from kursplaner.infrastructure.repositories.plan_repository import FileSystemPlanRepository
from kursplaner.infrastructure.repositories.plan_table_file_repository import create_linked_lesson_file

_RHYTHM = (WeekdayRhythm(weekday=0, start_time="08:00", hours=2),)


def test_build_wiki_link_formats_target_and_alias():
    built = build_wiki_link(" gruen-6 ]", " Lautstaerke [ im Raum ")

    assert built == "[[gruen-6|Lautstaerke im Raum]]"


def test_build_dataview_lesson_link_formats_stem():
    built = build_dataview_lesson_link("ab12cd")

    assert built == '`= link("ab12cd", [[ab12cd]].Stundenthema)`'


def test_build_dataview_lesson_link_normalizes_brackets_and_whitespace():
    built = build_dataview_lesson_link(" gruen-6 ]\n02-06[ Thema ")

    assert built == '`= link("gruen-6 02-06 Thema", [[gruen-6 02-06 Thema]].Stundenthema)`'


def test_build_dataview_lesson_link_empty_stem_is_empty():
    assert build_dataview_lesson_link("") == ""
    assert build_dataview_lesson_link("   ") == ""


def test_build_dataview_lesson_link_strips_backtick():
    built = build_dataview_lesson_link("ab`12cd")

    assert "`" not in built[1:-1]
    assert built == '`= link("ab12cd", [[ab12cd]].Stundenthema)`'


def test_strip_group_prefixed_link_decodes_bracketed_group_prefixed_text():
    assert strip_group_prefixed_link("[[11.1 EFl1 Potenzfunktionen]]", "11.1") == "EFl1 Potenzfunktionen"


def test_strip_group_prefixed_link_decodes_without_group_prefix():
    assert strip_group_prefixed_link("[[Algorithmen]]", "lila-5") == "Algorithmen"


def test_strip_group_prefixed_link_leaves_plain_text_unchanged():
    assert strip_group_prefixed_link("EFl1 Potenzfunktionen", "11.1") == "EFl1 Potenzfunktionen"


def test_strip_group_prefixed_link_handles_wiki_linked_group_name():
    assert strip_group_prefixed_link("[[li2 Kodierung]]", "[[li2]]") == "Kodierung"


def test_strip_group_prefixed_link_empty_input_is_empty():
    assert strip_group_prefixed_link("", "11.1") == ""


def test_read_yaml_oberthema_matches_regardless_of_representation():
    """Klartext und Wiki-Link desselben Themas muessen denselben Wert liefern (Vergleichbarkeit)."""
    plain = read_yaml_oberthema({"Oberthema": "EFl1 Potenzfunktionen"}, "11.1")
    linked = read_yaml_oberthema({"Oberthema": "[[11.1 EFl1 Potenzfunktionen]]"}, "11.1")

    assert plain == linked == "EFl1 Potenzfunktionen"


def test_read_yaml_oberthema_missing_field_is_empty():
    assert read_yaml_oberthema({}, "11.1") == ""


def test_create_linked_lesson_file_writes_dataview_link(tmp_path):
    plan_path = tmp_path / "Informatik" / "Informatik.md"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text("", encoding="utf-8")

    table = PlanTableData(
        markdown_path=plan_path,
        headers=["Datum", "Inhalt", "Thema/Ausfall"],
        rows=[["2026-03-09", "", ""]],
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
    inhalt_value = table.rows[0][1]
    assert inhalt_value.startswith('`= link("')
    assert inhalt_value.endswith("`")
    assert f'"{lesson_path.stem}"' in inhalt_value
    assert f"[[{lesson_path.stem}]].Stundenthema" in inhalt_value


def test_create_linked_lesson_file_generates_unique_random_stem(tmp_path):
    """Neuer Stem ist ein eindeutiger 6-Zeichen-Code aus [a-z0-9], der von bestehenden abweicht."""
    plan_path = tmp_path / "Informatik" / "Informatik.md"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text("", encoding="utf-8")

    einheiten_dir = plan_path.parent / "Einheiten"
    einheiten_dir.mkdir(parents=True)
    existing_stem = "ab12cd"
    (einheiten_dir / f"{existing_stem}.md").write_text(
        "---\nStundentyp: Unterricht\nDauer: 2\nStundenthema: Hardware\n---\n", encoding="utf-8"
    )

    table = PlanTableData(
        markdown_path=plan_path,
        headers=["Datum", "Inhalt", "Thema/Ausfall"],
        rows=[["10-03-26", "", ""]],
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
    assert len(lesson_path.stem) == 6
    assert lesson_path.stem.isalnum() and lesson_path.stem == lesson_path.stem.lower()
    assert lesson_path.stem != existing_stem
    assert table.rows[0][1] == f'`= link("{lesson_path.stem}", [[{lesson_path.stem}]].Stundenthema)`'


def test_write_plan_metadata_uses_valid_wiki_link(tmp_path):
    markdown_path = tmp_path / "Plan.md"
    markdown_path.write_text("# Plan\n", encoding="utf-8")

    repo = FileSystemPlanRepository()
    repo.write_plan_metadata(markdown_path, "gruen-6]", "Informatik", 6, rhythm=_RHYTHM)

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
        rhythm=_RHYTHM,
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
