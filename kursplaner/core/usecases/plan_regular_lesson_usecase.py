from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.lesson_naming import build_lesson_stem, row_mmdd
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.domain.wiki_links import strip_wiki_link
from kursplaner.core.ports.repositories import LessonRepository, PlanRepository
from kursplaner.core.usecases.lesson_commands_usecase import LessonCommandsUseCase
from kursplaner.core.usecases.lesson_context_query_usecase import LessonContextQueryUseCase
from kursplaner.core.usecases.lesson_transfer_usecase import LessonTransferUseCase
from kursplaner.core.usecases.subject_sources_usecase import SubjectSourcesUseCase


@dataclass(frozen=True)
class PlanRegularLessonInput:
    """Repräsentiert Eingabeparameter für Plan Regular Lesson Input.

    Die Instanz bündelt validierte Nutzereingaben für einen fachlichen Verarbeitungsschritt.
    """

    title: str
    row_index: int
    topic: str
    stunden_raw: str
    oberthema_input: str
    stundenziel_input: str
    was_lzk: bool
    content_before: str
    kompetenzen_refs: list[str]
    inhalte_refs: list[str]
    methodik_refs: list[str]


@dataclass(frozen=True)
class PlanRegularLessonWriteResult:
    """Ergebnis eines vollständigen Write-Flows für reguläre Unterrichtsstunden."""

    proceed: bool
    lesson_path: Path | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class RegularLessonDialogContext:
    """Fachlicher Kontext für den Builder-Dialog "Einheit planen"."""

    row_index: int
    was_lzk: bool
    current_topic: str
    content_before: str
    stunden_raw: str
    date_label: str
    link: Path | None
    has_existing_link: bool
    title_initial: str
    topic_initial: str
    oberthema_initial: str
    kompetenzen_options: list[str]
    inhalte_options: list[str]
    methodik_options: list[str]


class PlanRegularLessonUseCase:
    """Orchestriert den fachlichen Ablauf für Plan Regular Lesson Use-Case.

    Die Klasse bündelt Anwendungslogik zwischen Domain-Regeln und Port-basiertem I/O.
    """

    def __init__(
        self,
        lesson_repo: LessonRepository,
        lesson_commands: LessonCommandsUseCase,
        plan_repo: PlanRepository,
        lesson_transfer: LessonTransferUseCase,
        subject_sources: SubjectSourcesUseCase,
        lesson_context_query: LessonContextQueryUseCase,
    ):
        """Initialisiert den Ablauf zur Planung regulärer Unterrichtsstunden.

        Args:
            lesson_repo: Repository für bestehende Stundenlinks.
            lesson_commands: Kommandos für Erzeugen und Aktualisieren von Stunden.
            plan_repo: Repository zum Persistieren der Planung.
            lesson_transfer: Dateioperationen für Rename/Relink.
            subject_sources: Fachquellen-UseCase für Inhalte/Methodik-Auswahl.
            lesson_context_query: Query-UseCase für Planableitungen wie Oberthema.
        """
        self.lesson_repo = lesson_repo
        self.lesson_commands = lesson_commands
        self.plan_repo = plan_repo
        self.lesson_transfer = lesson_transfer
        self.subject_sources = subject_sources
        self.lesson_context_query = lesson_context_query

    def build_dialog_context(
        self,
        *,
        table: PlanTableData,
        day: dict[str, object],
        unterricht_dir: Path,
    ) -> RegularLessonDialogContext:
        """Bereitet alle fachlichen Dialog-Eingaben für "Einheit planen" vor."""
        row_index = int(day.get("row_index", 0))
        was_lzk = bool(day.get("is_lzk", False))
        current_topic = str(day.get("Stundenthema", "")).strip()
        content_before = str(day.get("inhalt", "")).strip()
        stunden_raw = str(day.get("stunden", "")).strip()
        date_label = str(day.get("datum", "")).strip()

        link = self.resolve_existing_link(table, row_index)
        has_existing_link = self.has_existing_link(link)

        subject_name = str(table.metadata.get("Kursfach", ""))
        inhalte_options, methodik_options = self.subject_sources.resolve_subject_sources(
            unterricht_dir,
            subject_name,
        )

        return RegularLessonDialogContext(
            row_index=row_index,
            was_lzk=was_lzk,
            current_topic=current_topic,
            content_before=content_before,
            stunden_raw=stunden_raw,
            date_label=date_label,
            link=link,
            has_existing_link=has_existing_link,
            title_initial=(current_topic or "Unterrichtseinheit"),
            topic_initial=(current_topic or "Unterrichtseinheit"),
            oberthema_initial=self.lesson_context_query.last_oberthema_before_row(table, row_index),
            kompetenzen_options=[],
            inhalte_options=inhalte_options,
            methodik_options=methodik_options,
        )

    @staticmethod
    def has_existing_link(link: Path | None) -> bool:
        """Prüft, ob ein gültiger und existierender Stundenlink vorliegt.

        Args:
            link: Potenzieller Dateilink aus der Planzeile.

        Returns:
            ``True`` bei vorhandener Datei.
        """
        return isinstance(link, Path) and link.exists() and link.is_file()

    def resolve_existing_link(self, table: PlanTableData, row_index: int) -> Path | None:
        """Liest den aktuell verlinkten Stundenpfad der Zielzeile.

        Args:
            table: Planungstabelle.
            row_index: Zielzeile.

        Returns:
            Verlinkter Stundenpfad oder ``None``.
        """
        return self.lesson_repo.resolve_row_link_path(table, row_index)

    @staticmethod
    def topic_initial(current_topic: str, content_before: str) -> str:
        """Ermittelt ein Startthema aus Eingabe oder Altinhalt.

        Args:
            current_topic: Aktuell eingegebener Themenwert.
            content_before: Vorheriger Inhaltswert der Planzeile.

        Returns:
            Thema für die anzulegende oder zu aktualisierende Stunde.
        """
        return current_topic or "Unterrichtseinheit"

    @staticmethod
    def default_hours(stunden_raw: str) -> int:
        """Leitet die Stundenzahl aus dem Tabellenwert oder Default ab.

        Args:
            stunden_raw: Rohwert aus der Spalte ``stunden``.

        Returns:
            Positive Stundenanzahl, standardmäßig ``2``.
        """
        value = (stunden_raw or "").strip()
        return int(value) if value.isdigit() else 2

    def ensure_link(self, table: PlanTableData, row_index: int, topic: str, default_hours: int) -> Path:
        """Stellt sicher, dass die Zielzeile auf eine Stunden-Datei verlinkt ist.

        Args:
            table: Planungstabelle.
            row_index: Zielzeile.
            topic: Thema für eine neue Datei, falls noch kein Link existiert.
            default_hours: Initiale Stundenanzahl für die Neuanlage.

        Returns:
            Sicherer Link auf die zu bearbeitende Stunden-Datei.
        """
        link = self.resolve_existing_link(table, row_index)
        if self.has_existing_link(link):
            return link  # type: ignore[return-value]
        return self.lesson_commands.create_regular_lesson_link(table, row_index, topic, default_hours)

    def update_regular_lesson(
        self,
        lesson_path: Path,
        topic: str,
        oberthema_input: str,
        *,
        was_lzk: bool,
        content_before: str,
    ) -> None:
        """Überträgt Themen- und Oberthema-Änderungen in die Stunden-YAML.

        Args:
            lesson_path: Pfad der zu aktualisierenden Stunden-Datei.
            topic: Neues Stundenthema.
            oberthema_input: Optionales Oberthema aus der UI.
            was_lzk: Kennzeichnet eine vorherige LZK-Konvertierung.
            content_before: Vorheriger Tabelleninhalt für Fallback-Logik.
        """
        self.lesson_commands.update_regular_lesson_content(
            lesson_path,
            topic,
            oberthema_input,
            was_lzk=was_lzk,
            content_before=content_before,
        )

    def update_sections(self, lesson_path: Path, inhalte_refs: list[str], methodik_refs: list[str]) -> None:
        """Aktualisiert optionale Inhalte-/Methodik-Abschnitte der Stunde.

        Args:
            lesson_path: Pfad der Stunden-Datei.
            inhalte_refs: Verweise für den Abschnitt ``Inhalte``.
            methodik_refs: Verweise für den Abschnitt ``Methodik``.
        """
        if inhalte_refs or methodik_refs:
            self.lesson_commands.update_lesson_sections(lesson_path, inhalte_refs, methodik_refs)

    def update_competencies(self, lesson_path: Path, kompetenzen_refs: list[str], stundenziel_input: str) -> None:
        """Aktualisiert optionale Kompetenzlisten der Stunde in der YAML-Struktur."""
        if kompetenzen_refs or stundenziel_input.strip():
            self.lesson_commands.update_lesson_competencies(lesson_path, kompetenzen_refs, stundenziel_input)

    def execute_write(
        self,
        *,
        table: PlanTableData,
        row_index: int,
        title: str,
        topic: str,
        stunden_raw: str,
        oberthema_input: str,
        stundenziel_input: str,
        was_lzk: bool,
        content_before: str,
        kompetenzen_refs: list[str],
        inhalte_refs: list[str],
        methodik_refs: list[str],
        allow_create_link: bool,
        allow_yaml_save: bool,
        allow_sections_save: bool,
        allow_rename: bool,
        allow_plan_save: bool,
    ) -> PlanRegularLessonWriteResult:
        """Führt den vollständigen Write-Flow für "Einheit planen" als eine Transaktion aus."""
        link = self.resolve_existing_link(table, row_index)
        has_link = self.has_existing_link(link)

        if not has_link:
            if not allow_create_link:
                return PlanRegularLessonWriteResult(
                    proceed=False,
                    error_message="Anlegen der Stunden-Datei wurde nicht bestätigt.",
                )
            default_hours = self.default_hours(stunden_raw)
            link = self.ensure_link(table, row_index, title, default_hours)

        if not isinstance(link, Path):
            return PlanRegularLessonWriteResult(
                proceed=False,
                error_message="Kein gültiger Stunden-Link für die Planung verfügbar.",
            )

        if not allow_yaml_save:
            return PlanRegularLessonWriteResult(
                proceed=False,
                error_message="Speichern der Stunden-YAML wurde nicht bestätigt.",
            )
        self.update_regular_lesson(
            lesson_path=link,
            topic=topic,
            oberthema_input=oberthema_input,
            was_lzk=was_lzk,
            content_before=content_before,
        )

        if kompetenzen_refs or stundenziel_input.strip():
            if not allow_sections_save:
                return PlanRegularLessonWriteResult(
                    proceed=False,
                    error_message="Ergaenzen der Kompetenzen wurde nicht bestaetigt.",
                )
            self.update_competencies(link, kompetenzen_refs, stundenziel_input)

        if inhalte_refs or methodik_refs:
            if not allow_sections_save:
                return PlanRegularLessonWriteResult(
                    proceed=False,
                    error_message="Ergänzen der Inhalte/Methodik wurde nicht bestätigt.",
                )
            self.update_sections(link, inhalte_refs, methodik_refs)

        final_path = link
        if allow_rename:
            group_token = strip_wiki_link(str(table.metadata.get("Lerngruppe", "gruppe")))
            mmdd_token = row_mmdd(table, row_index)
            desired_stem = build_lesson_stem(group_token, mmdd_token, title)
            rename_target = self.lesson_transfer.compute_rename_target(final_path, desired_stem)
            if rename_target != final_path:
                final_path = self.lesson_transfer.rename_lesson_file(final_path, rename_target)
        self.lesson_transfer.relink_row_to_stem(table, row_index, final_path.stem, preserve_alias=False)

        if not allow_plan_save:
            return PlanRegularLessonWriteResult(
                proceed=False,
                error_message="Speichern der Planungstabelle wurde nicht bestätigt.",
            )
        self.plan_repo.save_plan_table(table)

        return PlanRegularLessonWriteResult(
            proceed=True,
            lesson_path=final_path,
        )
