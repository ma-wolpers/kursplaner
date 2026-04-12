from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.content_markers import build_hospitation_marker
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.wiki_links import build_wiki_link, strip_wiki_link
from kursplaner.core.ports.repositories import LessonRepository, PlanRepository
from kursplaner.core.usecases.lesson_commands_usecase import LessonCommandsUseCase
from kursplaner.core.usecases.lesson_transfer_usecase import LessonTransferUseCase


@dataclass(frozen=True)
class ConvertToHospitationWriteResult:
    """Ergebnis der Umwandlung einer Zeile in eine Hospitation."""

    proceed: bool
    lesson_path: Path | None = None
    error_message: str | None = None


class ConvertToHospitationUseCase:
    """Wandelt eine Planzeile fachlich in eine Hospitation um."""

    def __init__(
        self,
        plan_repo: PlanRepository,
        lesson_repo: LessonRepository,
        lesson_commands: LessonCommandsUseCase,
        lesson_transfer: LessonTransferUseCase,
    ):
        """Initialisiert Umwandlungslogik und Persistenzabhängigkeiten."""
        self.plan_repo = plan_repo
        self.lesson_repo = lesson_repo
        self.lesson_commands = lesson_commands
        self.lesson_transfer = lesson_transfer

    @staticmethod
    def _header_index(table: PlanTableData, key: str) -> int:
        mapping = {name.lower(): idx for idx, name in enumerate(table.headers)}
        idx = mapping.get(key.lower())
        if idx is None:
            raise RuntimeError(f"Plan-Tabelle muss Spalte '{key}' enthalten.")
        return idx

    @staticmethod
    def _group_name(table: PlanTableData) -> str:
        raw = strip_wiki_link(str(table.metadata.get("Lerngruppe", "")))
        return raw or "Gruppe"

    def execute_write(
        self,
        *,
        table: PlanTableData,
        row_index: int,
        focus_text: str,
        default_hours: int,
        allow_create_link: bool,
        allow_yaml_save: bool,
        allow_plan_save: bool,
    ) -> ConvertToHospitationWriteResult:
        """Führt den vollständigen Hospitations-Write-Flow aus."""
        group_name = self._group_name(table)
        marker = build_hospitation_marker(group_name=group_name, note_text=focus_text)

        link = self.lesson_transfer.resolve_existing_link(table, row_index)
        if not (isinstance(link, Path) and link.exists() and link.is_file()):
            if not allow_create_link:
                return ConvertToHospitationWriteResult(
                    proceed=False,
                    error_message="Hospitations-Stunden-Datei wurde nicht angelegt.",
                )
            topic = f"Hospitation {group_name}"
            link = self.lesson_commands.create_regular_lesson_link(table, row_index, topic, max(1, int(default_hours)))

        if not isinstance(link, Path):
            return ConvertToHospitationWriteResult(
                proceed=False,
                error_message="Keine verlinkte Hospitations-Datei verfügbar.",
            )

        idx_inhalt = self._header_index(table, "inhalt")
        table.rows[row_index][idx_inhalt] = f"{marker} {build_wiki_link(link.stem)}"

        if not allow_yaml_save:
            return ConvertToHospitationWriteResult(
                proceed=False,
                error_message="Speichern der Hospitations-YAML wurde abgebrochen.",
            )

        lesson = self.lesson_repo.load_lesson_yaml(link)
        data = lesson.data
        if not isinstance(data, dict):
            data = {}
            lesson.data = data

        if not str(data.get("Stundenthema", "")).strip():
            data["Stundenthema"] = f"Hospitation {group_name}"
        data["Stundentyp"] = "Hospitation"
        data["Beobachtungsschwerpunkte"] = str(focus_text or "").strip()
        data.setdefault("Ressourcen", [])
        data.setdefault("Baustellen", [])
        self.lesson_repo.save_lesson_yaml(lesson)

        if not allow_plan_save:
            return ConvertToHospitationWriteResult(
                proceed=False,
                error_message="Speichern der Planung wurde abgebrochen.",
            )

        self.plan_repo.save_plan_table(table)
        return ConvertToHospitationWriteResult(proceed=True, lesson_path=link)
