from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.plan_regular_lesson_usecase import PlanRegularLessonUseCase
from tests.day_column_factory import make_day_column


class _NoLinkLessonRepo:
    """Kein verlinkter Stundenlink für irgendeine Zeile."""

    def resolve_row_link_path(self, table, row_index):
        return None


class _NoSubjectSources:
    def resolve_subject_sources(self, unterricht_dir, subject_folder):
        return [], []


class _StubLessonContextQuery:
    """Rückwärtssuche liefert ein anderes Oberthema als in der aktuellen Zeile eingetragen."""

    def last_oberthema_before_row(self, table, row_index):
        return "Oberthema aus Vorzeile"


def _table() -> PlanTableData:
    return PlanTableData(
        markdown_path=Path("Kurs/Kurs.md"),
        headers=["Datum", "Inhalt", "Thema/Ausfall"],
        rows=[["05-01-26", "", ""]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={"Kursfach": "Informatik"},
    )


def _usecase() -> PlanRegularLessonUseCase:
    return PlanRegularLessonUseCase(
        lesson_repo=_NoLinkLessonRepo(),
        lesson_commands=None,
        plan_repo=None,
        lesson_transfer=None,
        subject_sources=_NoSubjectSources(),
        lesson_context_query=_StubLessonContextQuery(),
    )


def test_prefers_oberthema_already_typed_into_current_empty_row():
    """Ein direkt in die leere Zeile eingetragenes Oberthema hat Vorrang vor der Rückwärtssuche."""
    day = make_day_column(
        row_index=0,
        datum="05-01-26",
        thema_ausfall="[[Direkt eingetragenes Oberthema]]",
    )

    context = _usecase().build_dialog_context(table=_table(), day=day, unterricht_dir=Path("."))

    assert context.oberthema_initial == "Direkt eingetragenes Oberthema"


def test_falls_back_to_backward_search_when_row_has_no_oberthema():
    """Ohne eigenes Oberthema in der Zeile greift weiterhin die Rückwärtssuche über Vorzeilen."""
    day = make_day_column(row_index=0, datum="05-01-26")

    context = _usecase().build_dialog_context(table=_table(), day=day, unterricht_dir=Path("."))

    assert context.oberthema_initial == "Oberthema aus Vorzeile"


def test_yaml_oberthema_still_wins_over_plan_oberthema():
    """Ein bereits im YAML gesetztes Oberthema hat weiterhin höchste Priorität."""
    day = make_day_column(
        row_index=0,
        datum="05-01-26",
        thema_ausfall="[[Direkt eingetragenes Oberthema]]",
        yaml={"Oberthema": "Oberthema aus YAML"},
    )

    context = _usecase().build_dialog_context(table=_table(), day=day, unterricht_dir=Path("."))

    assert context.oberthema_initial == "Oberthema aus YAML"
