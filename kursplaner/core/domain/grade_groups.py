"""Gruppierung von Jahrgangsstufen in GS/Sek I/Sek II fuer schulweite Ausfaelle.

Die Grenzen entsprechen der bestehenden Konvention im Informatik-Kompetenz-
katalog-Manifest (`inf-sek1`: Stufe 5-10, `inf-sek2`: Stufe 11-13).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GradeGroup:
    """Eine Jahrgangsstufen-Gruppe mit Schluessel, Anzeigename und Stufenbereich."""

    key: str
    label: str
    grade_min: int
    grade_max: int

    def grades(self) -> frozenset[int]:
        """Liefert alle konkreten Jahrgangsstufen dieser Gruppe."""
        return frozenset(range(self.grade_min, self.grade_max + 1))


GRADE_GROUPS: tuple[GradeGroup, ...] = (
    GradeGroup(key="gs", label="Grundschule", grade_min=1, grade_max=4),
    GradeGroup(key="sek1", label="Sek I", grade_min=5, grade_max=10),
    GradeGroup(key="sek2", label="Sek II", grade_min=11, grade_max=13),
)

GRADE_GROUP_BY_KEY: dict[str, GradeGroup] = {group.key: group for group in GRADE_GROUPS}


def expand_grade_selection(
    *,
    fully_selected_group_keys: frozenset[str],
    individually_selected_grades: frozenset[int],
) -> frozenset[int]:
    """Wandelt eine UI-Auswahl (vollstaendig markierte Gruppen + Einzelstufen) in ein Stufen-Set.

    Reine Mengen-Operation ohne UI-Zustand (kein Tri-State-Checkbox-Wissen):
    Aufrufer teilen mit, welche Gruppen als Ganzes markiert sind und welche
    Einzelstufen zusaetzlich (oder aus einer nicht vollstaendig markierten
    Gruppe) ausgewaehlt sind.

    Example::

        expand_grade_selection(
            fully_selected_group_keys=frozenset({"sek2"}),
            individually_selected_grades=frozenset({8}),
        )
        # -> frozenset({8, 11, 12, 13})
    """
    grades: set[int] = set(individually_selected_grades)
    for key in fully_selected_group_keys:
        group = GRADE_GROUP_BY_KEY.get(key)
        if group is not None:
            grades |= group.grades()
    return frozenset(grades)
