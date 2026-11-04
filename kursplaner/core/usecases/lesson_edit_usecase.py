from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from kursplaner.core.domain.lesson_yaml_policy import LIST_FIELDS, LessonType, infer_stundentyp
from kursplaner.core.domain.oberthema_values import OBERTHEMA_KEY, encode_oberthemen, normalize_oberthemen
from kursplaner.core.domain.plan_table import COLUMN_INHALT, LessonYamlData, PlanTableData
from kursplaner.core.ports.repositories import LessonRepository


class LessonEditUseCase:
    """Orchestriert den fachlichen Ablauf für Lesson Edit Use-Case.

    Die Klasse bündelt Anwendungslogik zwischen Domain-Regeln und Port-basiertem I/O.
    """

    def __init__(self, lesson_repo: LessonRepository):
        """Initialisiert den Use Case für tabellarische und YAML-Feldänderungen an Stunden."""
        self.lesson_repo = lesson_repo

    def validate_table(self, table: PlanTableData) -> int:
        """Prüft die Mindeststruktur der Planungstabelle für Edit-Operationen.

        Invariante: Spalte ``Inhalt`` muss vorhanden sein.

        Returns:
            Spaltenindex von ``Inhalt``.
        """
        return table.column_index(COLUMN_INHALT)

    def set_content_value(self, table: PlanTableData, row_index: int, value: str) -> None:
        """Setzt den Inhaltswert einer Tabellenzeile ohne YAML-Nebenwirkungen."""
        table.set_inhalt(row_index, value)

    def set_lesson_oberthemen(self, lesson_path: Path, entries: list[str], group_name: str) -> None:
        """Schreibt das Oberthema einer Stunde als ausdrückliche Korrektur (typabhängige Form).

        * **LZK**: kanonische Liste aus Wiki-Links (entschlüsselt, ohne Duplikate/Leereinträge).
        * **Unterricht/Hospitation**: Einzelwert, gespeichert wie eingegeben;
          mehr als ein (verschiedenes) Thema wird abgelehnt.

        Als bewusstes Speichern der Oberthema-Zelle darf der Vorgang auch einen
        ungültigen Plattenwert ersetzen (``repair_oberthema``).

        Args:
            lesson_path: Pfad der Stunden-Datei.
            entries: Eingegebene Einträge (roh, dürfen Wiki-Links/Duplikate enthalten).
            group_name: Lerngruppen-Bezeichnung des Kurses.

        Raises:
            RuntimeError: Wenn eine Nicht-LZK-Einheit mehr als ein Oberthema bekäme.
        """
        lesson = self.lesson_repo.load_lesson_yaml(lesson_path)
        if infer_stundentyp(lesson.data) == "LZK":
            lesson.data[OBERTHEMA_KEY] = encode_oberthemen(entries, group_name)
        else:
            if len(normalize_oberthemen(entries, group_name)) > 1:
                raise RuntimeError("Nur eine LZK darf mehrere Oberthemen haben.")
            raw_entries = [str(entry).strip() for entry in entries if str(entry).strip()]
            lesson.data[OBERTHEMA_KEY] = raw_entries[0] if raw_entries else ""
        self.lesson_repo.save_lesson_yaml(lesson, repair_oberthema=True)

    def set_lesson_duration(self, lesson_path: Path, value: str) -> None:
        """Schreibt die Unterrichtsdauer in die verlinkte Stunden-YAML."""
        self.set_lesson_fields(lesson_path, {"Dauer": value})

    def set_lesson_field(
        self, lesson_path: Path, field_key: str, value: str, list_entries: list[str] | None = None
    ) -> None:
        """Aktualisiert ein einzelnes YAML-Feld einer Stunde (skalare oder Listenfelder)."""
        new_value: object = (list_entries or []) if field_key in LIST_FIELDS else value
        self.set_lesson_fields(lesson_path, {field_key: new_value})

    def set_lesson_fields(
        self, lesson_path: Path, values: Mapping[str, object], *, require_type: LessonType | None = None
    ) -> None:
        """Einziger Feld-Schreibweg: frisch laden, *values* setzen, in einem Vorgang speichern.

        Den Listenvertrag setzt das Speichern selbst durch (`canonicalize_lesson_yaml`);
        bei einem Verstoß wird nichts geschrieben. Die Sequenzleiter schreibt
        hierüber Stundenziel, Teilziele und Kompetenzen gemeinsam (§37).

        Args:
            lesson_path: Pfad der Stunden-Datei.
            values: Zu setzende Felder.
            require_type: Wenn gesetzt, muss die Einheit diesen Stundentyp haben.

        Raises:
            ValueError: Die Einheit hat nicht den verlangten Stundentyp.
            ListFieldViolationError: Ein Listeneintrag verletzt den Listenvertrag.
        """
        lesson = self.lesson_repo.load_lesson_yaml(lesson_path)
        if require_type is not None and infer_stundentyp(lesson.data) != require_type:
            raise ValueError(f"{lesson_path.name}: Dieses Feld gibt es nur in {require_type}-Einheiten.")
        self.lesson_repo.save_lesson_yaml(LessonYamlData(lesson.lesson_path, {**lesson.data, **values}))
