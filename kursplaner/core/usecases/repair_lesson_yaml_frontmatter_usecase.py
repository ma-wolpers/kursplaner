from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.domain.lesson_yaml_policy import default_yaml_for_type, normalize_stundentyp
from kursplaner.core.domain.plan_table import LessonYamlData, sanitize_hour_title
from kursplaner.core.ports.repositories import LessonRepository


@dataclass(frozen=True)
class RepairLessonYamlFrontmatterResult:
    """Ergebnis der Frontmatter-Reparatur für eine Stunden-Datei."""

    lesson_path: Path
    kind: str


class RepairLessonYamlFrontmatterUseCase:
    """Ergänzt fehlendes YAML-Frontmatter in Stunden-Dateien typabhängig."""

    VALID_KINDS = {"unterricht", "lzk", "ausfall", "hospitation"}

    def __init__(self, lesson_repo: LessonRepository):
        """Initialisiert den Reparatur-Use-Case mit Lesson-Repository-Port."""
        self.lesson_repo = lesson_repo

    @classmethod
    def normalize_kind(cls, kind: str) -> str:
        """Normalisiert Art-Bezeichner auf kanonische Werte."""
        resolved = normalize_stundentyp(kind)
        return resolved.lower()

    def _defaults_for_kind(self, *, kind: str, lesson_path: Path) -> dict[str, object]:
        """Leitet typspezifische YAML-Defaults für Unterricht, LZK oder Hospitation ab.

        Args:
            kind: Kanonischer Typ (`unterricht`, `lzk`, `hospitation`).
            lesson_path: Zielpfad der Stunden-Datei zur Themenableitung.

        Returns:
            Vollständige YAML-Defaults mit typabhängig angepasstem Stundenthema.
        """
        stem_topic = sanitize_hour_title(lesson_path.stem) or lesson_path.stem or "Neue Stunde"
        canonical_kind = normalize_stundentyp(kind)
        return default_yaml_for_type(canonical_kind, topic=stem_topic)

    def execute(self, *, lesson_path: Path, kind: str) -> RepairLessonYamlFrontmatterResult:
        """Schreibt ein neues YAML-Frontmatter in eine bestehende Stunden-Datei."""
        normalized_kind = self.normalize_kind(kind)
        resolved = lesson_path.expanduser().resolve()
        if not resolved.exists() or not resolved.is_file():
            raise RuntimeError(f"Stunden-Datei nicht gefunden: {resolved}")

        lesson = LessonYamlData(
            lesson_path=resolved,
            data=self._defaults_for_kind(kind=normalized_kind, lesson_path=resolved),
        )
        self.lesson_repo.save_lesson_yaml(lesson)
        return RepairLessonYamlFrontmatterResult(lesson_path=resolved, kind=normalized_kind)
