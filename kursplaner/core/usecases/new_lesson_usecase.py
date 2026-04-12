from __future__ import annotations

from typing import Callable

from kursplaner.core.domain.models import StartRequest, StartResult
from kursplaner.core.ports.repositories import LessonSetupRepository, PlanRepository
from kursplaner.core.usecases.create_plan_usecase import CreatePlanUseCase

ConfirmChange = Callable[[str, str], bool]


def _require_confirmation(confirm_change: ConfirmChange | None, action: str, details: str):
    """Erzwingt einen bestätigten Dateisystem-Schritt oder bricht die Aktion fachlich ab."""
    if confirm_change is None:
        return
    if not confirm_change(action, details):
        raise RuntimeError(f"Aktion abgebrochen: {action}")


class NewLessonUseCase:
    """Orchestriert den fachlichen Ablauf für New Lesson Use-Case.

    Die Klasse bündelt Anwendungslogik zwischen Domain-Regeln und Port-basiertem I/O.
    """

    def __init__(
        self,
        create_plan_usecase: CreatePlanUseCase,
        plan_repo: PlanRepository,
        lesson_setup_repo: LessonSetupRepository,
    ):
        """Initialisiert den Use Case mit austauschbarer Planerzeugungs-Orchestrierung."""
        self._plan_repo = plan_repo
        self._create_plan_usecase = create_plan_usecase
        self._lesson_setup_repo = lesson_setup_repo

    def execute(self, request: StartRequest, confirm_change: ConfirmChange | None = None) -> StartResult:
        """Legt einen neuen Unterricht inklusive Plan-Datei und Startplanung transaktional an.

        Transaktionsgrenze: Ordner anlegen -> Plan-Datei erzeugen -> Metadaten schreiben -> Planzeilen erzeugen.
        Bei Fehler wird der angelegte Unterrichtsordner vollständig zurückgerollt.
        """
        self._lesson_setup_repo.validate_required_paths(request.base_dir, request.calendar_dir)

        _require_confirmation(
            confirm_change,
            "Unterrichtsordner erstellen",
            f"Nach:\n{request.base_dir / request.folder_name}",
        )

        lesson_dir = self._lesson_setup_repo.create_lesson_folder(request.base_dir, request.folder_name)

        try:
            _require_confirmation(
                confirm_change,
                "Plan-Datei erstellen",
                f"Ordner:\n{lesson_dir}\n\nNeuer Dateiname:\n{request.folder_name}.md",
            )
            lesson_md = self._lesson_setup_repo.create_plan_markdown(lesson_dir, request.folder_name)
            _require_confirmation(
                confirm_change,
                "Plan-Metadaten schreiben",
                f"Datei:\n{lesson_md}",
            )
            self._plan_repo.write_plan_metadata(
                markdown_path=lesson_md,
                group_name=request.group_name,
                course_subject=request.course_subject,
                grade_level=request.grade_level,
                kc_profile_label=request.kc_profile_label,
                process_competencies=request.process_competencies,
                content_competency=request.content_competency,
            )

            plan_result = self._create_plan_usecase.execute(
                target_markdown=lesson_md,
                term=request.term,
                day_hours=request.day_hours,
                calendar_dir=request.calendar_dir,
                takeover_start=request.takeover_start,
                stop_at_next_break=request.stop_at_next_break,
                vacation_break_horizon=request.vacation_break_horizon,
                write_mode="replace",
                confirm_change=confirm_change,
            )
        except Exception:
            self._lesson_setup_repo.rollback_lesson_folder(lesson_dir)
            raise

        return StartResult(
            lesson_dir=lesson_dir,
            lesson_markdown=lesson_md,
            planned_rows=plan_result.rows_count,
            range_start=plan_result.range_start,
            range_end=plan_result.range_end,
            warnings=plan_result.warnings,
        )
