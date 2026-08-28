from __future__ import annotations

from dataclasses import dataclass

_KNOWN_TARGET_KEYS = {"half", "full", "ubplus", "bub"}
_REQUIRED_TARGET_KEYS = {"half", "full"}


class AchievementRequirementsParseError(RuntimeError):
    """Signalisiert ungueltige Struktur in der Achievement-Anforderungen-JSON."""


@dataclass(frozen=True)
class AchievementTargets:
    """Schwellenwerte eines Fachs/Paedagogik fuer die bestehenden Achievement-Kategorien."""

    half: int
    full: int
    ubplus: int | None = None
    bub: int | None = None


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


@dataclass(frozen=True)
class DomainAchievementRequirements:
    """Alle konfigurierbaren Achievement-Vorgaben fuer ein Fach/Paedagogik."""

    targets: AchievementTargets
    grade_groups: tuple[GradeRequirement, ...] = ()


def _parse_targets(raw: object, *, subject: str) -> AchievementTargets:
    if not isinstance(raw, dict):
        raise AchievementRequirementsParseError(f"'targets' fehlt/ungueltig fuer '{subject}'.")

    unknown = set(raw.keys()) - _KNOWN_TARGET_KEYS
    if unknown:
        raise AchievementRequirementsParseError(f"Unbekannte Target-Keys {sorted(unknown)} in '{subject}'.")

    missing = _REQUIRED_TARGET_KEYS - set(raw.keys())
    if missing:
        raise AchievementRequirementsParseError(f"Pflicht-Targets {sorted(missing)} fehlen in '{subject}'.")

    def _positive_int(key: str) -> int:
        value = raw[key]
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise AchievementRequirementsParseError(f"Target '{key}' in '{subject}' muss eine positive Zahl sein.")
        return value

    def _optional_positive_int(key: str) -> int | None:
        if key not in raw:
            return None
        return _positive_int(key)

    return AchievementTargets(
        half=_positive_int("half"),
        full=_positive_int("full"),
        ubplus=_optional_positive_int("ubplus"),
        bub=_optional_positive_int("bub"),
    )


def _parse_grade_groups(raw: object, *, subject: str) -> tuple[GradeRequirement, ...]:
    if not isinstance(raw, list):
        raise AchievementRequirementsParseError(f"'grade_groups' muss eine Liste sein fuer '{subject}'.")

    parsed: list[GradeRequirement] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise AchievementRequirementsParseError(f"Ungueltiger grade_groups-Eintrag in '{subject}'.")

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
            raise AchievementRequirementsParseError(f"Unvollstaendiger grade_groups-Eintrag in '{subject}': {entry}")

        parsed.append(GradeRequirement(label=label, grade_min=grade_min, grade_max=grade_max, min_count=min_count))

    return tuple(parsed)


def parse_achievement_requirements(raw: object) -> dict[str, DomainAchievementRequirements]:
    """Parst die `requirements.json`-Struktur zu validierten Domain-Objekten.

    Erwartet pro Fach `{"targets": {...}, "grade_groups": [...]}`. `targets.half`/`.full`
    sind Pflicht, `.ubplus`/`.bub` optional -- ihr Fehlen bedeutet "diese Achievement-Art
    ist fuer dieses Fach nicht relevant" (ersetzt die vormalige `UBPLUS_BUB_SUBJECTS`-
    Konstante). Ein Fach mit leerer `grade_groups`-Liste gilt als "nicht konfiguriert" fuer
    Jahrgangsstufen-Tracking -- `compute_grade_group_progress` erzeugt dafuer bewusst keine
    Eintraege, um keinen vorgetaeuschten Fortschritt zu zeigen. Ein optionales Top-Level-Feld
    `schema_version` wird ignoriert (rein dokumentarisch, analog zu `catalog_manifest.json`).
    """
    if not isinstance(raw, dict):
        raise AchievementRequirementsParseError("Achievement-Anforderungen muessen ein JSON-Objekt sein.")

    result: dict[str, DomainAchievementRequirements] = {}
    for subject, entry in raw.items():
        if subject == "schema_version":
            continue
        if not isinstance(entry, dict):
            raise AchievementRequirementsParseError(f"Eintrag fuer '{subject}' muss ein JSON-Objekt sein.")

        targets = _parse_targets(entry.get("targets"), subject=str(subject))
        grade_groups = _parse_grade_groups(entry.get("grade_groups", []), subject=str(subject))
        result[str(subject)] = DomainAchievementRequirements(targets=targets, grade_groups=grade_groups)

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
