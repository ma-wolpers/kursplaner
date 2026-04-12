from __future__ import annotations

from pathlib import Path

from kursplaner.core.config.path_store import (
    BAUKASTEN_DIR_KEY,
    CALENDAR_DIR_KEY,
    FACHDIDAKTIK_DIR_KEY,
    FACHINHALTE_DIR_KEY,
    KOMPETENZ_MANIFEST_PATH_KEY,
    MATERIALIEN_DIR_KEY,
    PATH_FIELD_BY_KEY,
    PATH_FIELD_DEFINITIONS,
    UNTERRICHT_DIR_KEY,
    ManagedPaths,
    PathFieldDefinition,
    PathIssue,
    get_managed_paths,
    load_path_values,
    normalize_path_value,
    save_path_values,
    validate_paths,
)


class PathSettingsUseCase:
    """Kapselt Pfad-Konfiguration inkl. Laden, Validieren und Persistenz."""

    UNTERRICHT_KEY = UNTERRICHT_DIR_KEY
    CALENDAR_KEY = CALENDAR_DIR_KEY
    BAUKASTEN_KEY = BAUKASTEN_DIR_KEY
    FACHINHALTE_KEY = FACHINHALTE_DIR_KEY
    FACHDIDAKTIK_KEY = FACHDIDAKTIK_DIR_KEY
    MATERIALIEN_KEY = MATERIALIEN_DIR_KEY
    KOMPETENZ_MANIFEST_KEY = KOMPETENZ_MANIFEST_PATH_KEY

    @staticmethod
    def load_values() -> dict[str, str]:
        """Lädt persistierte Pfadwerte aus dem Path-Store."""
        return load_path_values()

    @staticmethod
    def save_values(values: dict[str, str]) -> dict[str, str]:
        """Persistiert Pfadwerte und gibt die normalisierte Version zurück."""
        return save_path_values(values)

    @staticmethod
    def to_managed_paths(values: dict[str, str] | None = None) -> ManagedPaths:
        """Konvertiert rohe Stringwerte in das typisierte `ManagedPaths`-Modell."""
        return get_managed_paths(values)

    @staticmethod
    def validate_values(values: dict[str, str]) -> list[PathIssue]:
        """Validiert Pfadwerte und liefert strukturierte Issues zurück."""
        return validate_paths(get_managed_paths(values))

    @staticmethod
    def path_field_definitions() -> tuple[PathFieldDefinition, ...]:
        """Liefert alle im UI pflegbaren Pfadfelder in stabiler Reihenfolge."""
        return PATH_FIELD_DEFINITIONS

    @staticmethod
    def path_field_by_key(key: str) -> PathFieldDefinition | None:
        """Liefert Metadaten zu einem bekannten Pfadkey oder `None`."""
        return PATH_FIELD_BY_KEY.get(key)

    def first_issue(self, values: dict[str, str]) -> PathIssue | None:
        """Liefert das erste Validierungsproblem oder `None` bei gültigen Pfaden."""
        issues = self.validate_values(values)
        return issues[0] if issues else None

    @staticmethod
    def suggest_initial_dir(problem_path: Path) -> str:
        """Schlägt ein sinnvolles Startverzeichnis für Dateidialoge vor."""
        if problem_path.exists() and problem_path.is_dir():
            return str(problem_path)
        if problem_path.parent.exists() and problem_path.parent.is_dir():
            return str(problem_path.parent)
        return str(Path.home())

    @staticmethod
    def apply_selected_path(values: dict[str, str], key: str, selected: str) -> tuple[dict[str, str], bool]:
        """Übernimmt eine Nutzerauswahl für bekannte Pfadkeys inkl. Änderungsflag."""
        if key not in PATH_FIELD_BY_KEY:
            return values, False
        normalized = normalize_path_value(selected)
        if not normalized:
            return values, False
        updated = dict(values)
        changed = updated.get(key, "") != normalized
        updated[key] = normalized
        return updated, changed

    def resolve_unterricht_dir(self, values: dict[str, str]) -> Path:
        """Liefert den aufgelösten Unterrichtspfad aus den gespeicherten Werten."""
        return self.to_managed_paths(values).unterricht_dir

    def resolve_calendar_dir(self, values: dict[str, str]) -> Path:
        """Liefert den aufgelösten Kalenderpfad aus den gespeicherten Werten."""
        return self.to_managed_paths(values).calendar_dir

    def resolve_for_key(self, values: dict[str, str], key: str) -> Path:
        """Liefert den aufgelösten Pfad für einen beliebigen bekannten Path-Key."""
        paths = self.to_managed_paths(values)
        mapping = {
            UNTERRICHT_DIR_KEY: paths.unterricht_dir,
            CALENDAR_DIR_KEY: paths.calendar_dir,
            BAUKASTEN_DIR_KEY: paths.baukasten_dir,
            FACHINHALTE_DIR_KEY: paths.fachinhalte_dir,
            FACHDIDAKTIK_DIR_KEY: paths.fachdidaktik_dir,
            MATERIALIEN_DIR_KEY: paths.materialien_dir,
            KOMPETENZ_MANIFEST_PATH_KEY: paths.kompetenz_manifest_path,
        }
        if key not in mapping:
            raise KeyError(f"Unbekannter Path-Key: {key}")
        return mapping[key]
