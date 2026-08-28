from __future__ import annotations

import json
from pathlib import Path

from kursplaner.core.domain.achievement_requirements import (
    AchievementRequirementsParseError,
    DomainAchievementRequirements,
    parse_achievement_requirements,
)


class FileSystemAchievementRequirementsRepository:
    """Laedt Achievement-Vorgaben (Schwellenwerte + Jahrgangsstufen-Gruppen) je Fach aus JSON."""

    _RESOURCE_PATH = Path(__file__).resolve().parents[2] / "resources" / "achievements" / "requirements.json"

    def load_requirements(self) -> dict[str, DomainAchievementRequirements]:
        """Liest und validiert die Achievement-Anforderungen-Datei.

        Die Datei ist Teil des Repos und liefert Pflichtdaten (half/full-
        Schwellenwerte fuer jedes Fach) -- fehlt sie oder ist sie ungueltig,
        wird das als echter Konfigurationsfehler gemeldet statt still ein
        leeres Ergebnis zu liefern.
        """
        if not self._RESOURCE_PATH.exists():
            raise AchievementRequirementsParseError(f"Achievement-Anforderungen-Datei fehlt: {self._RESOURCE_PATH}")
        raw = json.loads(self._RESOURCE_PATH.read_text(encoding="utf-8"))
        return parse_achievement_requirements(raw)
