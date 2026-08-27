from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GradeRequirement:
    """Eine Jahrgangsstufen-Vorgabe fuer ein Fach, z. B. "mind. 1 UB in 5./6."."""

    label: str
    grade_min: int
    grade_max: int
    min_count: int


@dataclass(frozen=True)
class GradeGroupProgress:
    """Fortschritt einer einzelnen Jahrgangsstufen-Vorgabe (current/target wie bei anderen Achievements)."""

    label: str
    current: int
    target: int


def parse_grade_requirements(raw: object) -> dict[str, tuple[GradeRequirement, ...]]:
    """Parst die `grade_requirements.json`-Struktur zu validierten Domain-Objekten.

    Ein Fach mit leerer Liste gilt als nicht konfiguriert (kein Fehler) --
    `compute_grade_group_progress` erzeugt fuer eine leere Vorgaben-Liste
    bewusst keine Eintraege, um keinen vorgetaeuschten Fortschritt zu zeigen.
    """
    if not isinstance(raw, dict):
        raise ValueError("grade_requirements muss ein JSON-Objekt (Fach -> Liste) sein.")

    result: dict[str, tuple[GradeRequirement, ...]] = {}
    for subject, entries in raw.items():
        if not isinstance(entries, list):
            raise ValueError(f"grade_requirements['{subject}'] muss eine Liste sein.")

        parsed: list[GradeRequirement] = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError(f"Ungueltiger grade_requirements-Eintrag in '{subject}'.")

            label = str(entry.get("label", "")).strip()
            grade_min = entry.get("grade_min")
            grade_max = entry.get("grade_max")
            min_count = entry.get("min_count")
            if (
                not label
                or not isinstance(grade_min, int)
                or not isinstance(grade_max, int)
                or not isinstance(min_count, int)
            ):
                raise ValueError(f"Unvollstaendiger grade_requirements-Eintrag in '{subject}': {entry}")

            parsed.append(
                GradeRequirement(label=label, grade_min=grade_min, grade_max=grade_max, min_count=min_count)
            )

        result[str(subject)] = tuple(parsed)

    return result


def compute_grade_group_progress(
    *,
    jahrgangsstufen: list[int],
    requirements: tuple[GradeRequirement, ...],
) -> list[GradeGroupProgress]:
    """Berechnet den Fortschritt je Jahrgangsstufen-Vorgabe eines Fachs.

    `current` ist die rohe Anzahl passender UB-Zeilen, `target` die geforderte
    Mindestanzahl -- dieselbe current/target-Semantik wie bei den bestehenden
    Achievement-Kategorien (half/full/ubplus/bub). Ein Fach ohne Vorgaben
    (leeres `requirements`-Tupel) liefert eine leere Liste, nie ein Item mit
    `target=0` oder `current=0`.
    """
    return [
        GradeGroupProgress(
            label=requirement.label,
            current=sum(1 for grade in jahrgangsstufen if requirement.grade_min <= grade <= requirement.grade_max),
            target=requirement.min_count,
        )
        for requirement in requirements
    ]
