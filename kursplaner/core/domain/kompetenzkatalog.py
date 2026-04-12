from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KompetenzAbschnitt:
    """Gruppiert Kompetenzen unter einer Zwischenueberschrift."""

    title: str
    competencies: tuple[str, ...]


@dataclass(frozen=True)
class Kompetenzkatalog:
    """Definiert einen fachlichen Kompetenzkatalog fuer ein Fachprofil."""

    profile_id: str
    profile_label: str
    subject_code: str
    grade_min: int
    grade_max: int
    process_sections: tuple[KompetenzAbschnitt, ...]
    content_sections: tuple[KompetenzAbschnitt, ...]

    @property
    def process_competencies(self) -> tuple[str, ...]:
        """Flache Sicht auf alle prozessbezogenen Kompetenzen."""
        items: list[str] = []
        for section in self.process_sections:
            items.extend(section.competencies)
        return tuple(items)

    @property
    def content_competencies(self) -> tuple[str, ...]:
        """Flache Sicht auf alle inhaltsbezogenen Kompetenzen."""
        items: list[str] = []
        for section in self.content_sections:
            items.extend(section.competencies)
        return tuple(items)


@dataclass(frozen=True)
class KompetenzkatalogManifestEntry:
    """Beschreibt einen Katalogeintrag im JSON-Manifest inklusive Dateipfad."""

    profile_id: str
    profile_label: str
    subject_code: str
    grade_min: int
    grade_max: int
    file_path: Path


class KompetenzkatalogParseError(RuntimeError):
    """Signalisiert ungueltige Struktur in Kompetenzkatalog-JSON-Dateien."""


def parse_kompetenzkatalog(raw: dict[str, object], source_label: str) -> Kompetenzkatalog:
    """Parst einen JSON-Katalog in das fachliche Kompetenzkatalog-Modell."""

    def _required_str(key: str) -> str:
        value = raw.get(key)
        if not isinstance(value, str) or not value.strip():
            raise KompetenzkatalogParseError(f"Ungueltiges Feld '{key}' in {source_label}.")
        return value.strip()

    def _required_int(key: str) -> int:
        value = raw.get(key)
        if not isinstance(value, int):
            raise KompetenzkatalogParseError(f"Ungueltiges Feld '{key}' in {source_label}.")
        return value

    def _parse_sections(key: str) -> tuple[KompetenzAbschnitt, ...]:
        value = raw.get(key)
        if not isinstance(value, list):
            raise KompetenzkatalogParseError(f"Ungueltiges Feld '{key}' in {source_label}.")
        sections: list[KompetenzAbschnitt] = []
        for section in value:
            if not isinstance(section, dict):
                raise KompetenzkatalogParseError(f"Ungueltiger Abschnitt in '{key}' in {source_label}.")
            title = str(section.get("title", "")).strip()
            competencies_raw = section.get("competencies")
            if not title or not isinstance(competencies_raw, list):
                raise KompetenzkatalogParseError(f"Ungueltiger Abschnitt in '{key}' in {source_label}.")
            competencies = tuple(str(item).strip() for item in competencies_raw if str(item).strip())
            if not competencies:
                raise KompetenzkatalogParseError(f"Leerer Abschnitt '{title}' in '{key}' in {source_label}.")
            sections.append(KompetenzAbschnitt(title=title, competencies=competencies))
        if not sections:
            raise KompetenzkatalogParseError(f"Leeres Feld '{key}' in {source_label}.")
        return tuple(sections)

    return Kompetenzkatalog(
        profile_id=_required_str("profile_id"),
        profile_label=_required_str("profile_label"),
        subject_code=_required_str("subject_code").upper(),
        grade_min=_required_int("grade_min"),
        grade_max=_required_int("grade_max"),
        process_sections=_parse_sections("process_sections"),
        content_sections=_parse_sections("content_sections"),
    )
