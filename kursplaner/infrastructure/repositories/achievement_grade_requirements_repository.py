from __future__ import annotations

import json
from pathlib import Path

from kursplaner.core.domain.achievement_grade_rules import GradeRequirement, parse_grade_requirements


class FileSystemAchievementGradeRequirementsRepository:
    """Laedt Jahrgangsstufen-Vorgaben je Fach aus einer JSON-Ressource."""

    _RESOURCE_PATH = Path(__file__).resolve().parents[2] / "resources" / "achievements" / "grade_requirements.json"

    def load_requirements(self) -> dict[str, tuple[GradeRequirement, ...]]:
        """Liest und validiert die Jahrgangsstufen-Vorgaben-Datei.

        Fehlt die Ressourcendatei, gilt das wie ein leeres Manifest (kein Fach
        konfiguriert) statt eines Fehlers -- die Datei ist Teil des Repos und
        wird bei Neuanlage immer mitgeliefert, ein Fehlen deutet eher auf
        einen ungewoehnlichen Checkout hin als auf einen Nutzerfehler.
        """
        if not self._RESOURCE_PATH.exists():
            return {}
        raw = json.loads(self._RESOURCE_PATH.read_text(encoding="utf-8"))
        return parse_grade_requirements(raw)
