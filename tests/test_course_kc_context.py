"""Kurs-KC-Kontext: Bundesland/Schulform lesen, schreiben, mit dem Netz abgleichen (synthetische Daten)."""

from __future__ import annotations

import json

import pytest
from kompetenzgraph_test_support import make_node

from kursplaner.core.config import ui_preferences_store
from kursplaner.core.domain.course_kc_context import (
    CourseKcContext,
    course_kc_context,
    kc_context_fields,
    schulform_matches,
)
from kursplaner.core.domain.course_rhythm import WeekdayRhythm
from kursplaner.core.domain.kompetenzgraph_filter import (
    KompetenzGraphFilter,
    build_initial_kompetenz_graph_filter,
    node_matches_filter,
)
from kursplaner.core.domain.kompetenzgraph_types import KcZuordnungEintrag
from kursplaner.core.domain.yaml_registry import PLAN_METADATA_SCHEMA, parse_yaml_frontmatter
from kursplaner.infrastructure.repositories.plan_repository import FileSystemPlanRepository

IGS_NDS = CourseKcContext("Niedersachsen", "IGS")


@pytest.mark.parametrize(
    ("entry", "wanted", "expected"),
    [
        ("IGS", "IGS", True),
        ("Gymnasium", "IGS", False),
        ("SekI", "IGS", True),
        ("SekI", "Hauptschule", True),
        ("SekII", "IGS", True),
        ("SekII", "Gymnasium", True),
        ("SekII", "Berufliches Gymnasium", False),
        ("IGS", None, True),
    ],
)
def test_schulform_matching_knows_stage_values(entry, wanted, expected):
    assert schulform_matches(entry, wanted) is expected


def test_context_reads_trimmed_fields_and_writes_only_set_ones():
    assert course_kc_context({"Bundesland": " Niedersachsen ", "Schulform": ""}) == CourseKcContext("Niedersachsen")
    assert kc_context_fields(IGS_NDS) == (("Bundesland", "Niedersachsen"), ("Schulform", "IGS"))
    assert kc_context_fields(CourseKcContext()) == ()


def test_initial_net_filter_takes_the_course_context():
    filter_ = build_initial_kompetenz_graph_filter(
        {"Kursfach": "Informatik", "Stufe": "10", **dict(kc_context_fields(IGS_NDS))}
    )
    assert (filter_.bundesland, filter_.schulform) == ("Niedersachsen", "IGS")
    entry = KcZuordnungEintrag("Niedersachsen", "SekI", None, 10, "basis", "zitat")
    node = make_node("Inf-ID-1", subject="Informatik", kc_zuordnung=(entry,))
    assert node_matches_filter(node, filter_)
    assert node_matches_filter(node, KompetenzGraphFilter(schulform="Berufliches Gymnasium"))
    sek2 = make_node("Mat-KO-4", kc_zuordnung=(KcZuordnungEintrag("Niedersachsen", "SekII", None, 11, "basis", "z"),))
    assert not node_matches_filter(sek2, KompetenzGraphFilter(schulform="Berufliches Gymnasium"))


def _plan(tmp_path, extra=""):
    path = tmp_path / "Plan.md"
    path.write_text(
        f'---\nLerngruppe: "[[gruppe-1]]"\nKursfach: "Mathematik"\nStufe: 8\n{extra}Rhythmus:\n  - "Mo 08:00 2"\n'
        "KC-Profil: x\n---\n\n| Datum | Inhalt | Thema/Ausfall |\n",
        encoding="utf-8",
    )
    return path


def test_new_course_writes_the_context_after_the_grade(tmp_path):
    path = tmp_path / "Neu.md"
    path.write_text("# Plan\n", encoding="utf-8")
    FileSystemPlanRepository().write_plan_metadata(
        path, "gruppe-1", "Mathematik", 8, rhythm=(WeekdayRhythm(0, "08:00", 2),), kc_context=IGS_NDS
    )
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[3:6] == ["Stufe: 8", 'Bundesland: "Niedersachsen"', 'Schulform: "IGS"']


def test_update_inserts_after_grade_replaces_existing_and_is_idempotent(tmp_path):
    repo = FileSystemPlanRepository()
    path = _plan(tmp_path, extra='Schulform: "Gymnasium"\n')
    assert repo.update_plan_kc_context(path, IGS_NDS) is True
    text = path.read_text(encoding="utf-8")
    assert 'Stufe: 8\nBundesland: "Niedersachsen"\nSchulform: "IGS"\nRhythmus:' in text
    assert text.endswith("| Datum | Inhalt | Thema/Ausfall |\n")
    assert repo.update_plan_kc_context(path, IGS_NDS) is False
    data, _body = parse_yaml_frontmatter(path.read_text(encoding="utf-8"), PLAN_METADATA_SCHEMA)
    assert course_kc_context(data) == IGS_NDS


def test_empty_context_values_are_rejected_by_the_plan_schema(tmp_path):
    path = _plan(tmp_path, extra='Schulform: ""\n')
    with pytest.raises(RuntimeError):
        parse_yaml_frontmatter(path.read_text(encoding="utf-8"), PLAN_METADATA_SCHEMA)


def test_defaults_round_trip_through_the_preferences(tmp_path, monkeypatch):
    target = tmp_path / "ui_preferences.json"
    monkeypatch.setattr(ui_preferences_store, "_preferences_file", lambda: target)
    assert ui_preferences_store.load_course_kc_defaults() == CourseKcContext()
    ui_preferences_store.save_course_kc_defaults(IGS_NDS)
    assert json.loads(target.read_text(encoding="utf-8"))["course_kc_defaults"] == {
        "Bundesland": "Niedersachsen",
        "Schulform": "IGS",
    }
    assert ui_preferences_store.load_course_kc_defaults() == IGS_NDS
