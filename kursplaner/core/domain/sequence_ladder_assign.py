"""Regeln zum Zuordnen einer Ablage-Sprosse („??“) zu einer Plan-Zeile (§37).

Ablage-Sprossen leben in der Sequenzdatei; ihr Inhalt wandert nie automatisch in
eine Einheit. Das Zuordnen ist der ausdrückliche Weg dorthin. Hier stehen nur
die reinen Regeln, der Use Case `assign_ablage_rung_usecase` liest und schreibt:

| Zielzeile (`target_kind`) | Verhalten |
|---|---|
| Termin dieser Sequenz (`MEMBER`) | nicht wählbar |
| LZK, Hospitation, Ausfall (`BLOCKED`) | nicht wählbar (`assign_target_error`) |
| leerer Termin (`FREE`) | Unterrichtsdatei anlegen, dann übernehmen |
| belegt (`OCCUPIED`: andere Sequenz, geplantes Thema, …) | neue Einheit einfügen, ab dort rückt alles einen Termin nach hinten (LZKs bleiben, `plan_row_payload.shift_moves`) |
| Unterricht ohne Oberthema (`LOOSE_UNIT`) | wie `OCCUPIED` **oder** Inhalt übernehmen; vorher warnen, was überschrieben wird |

**Übernahme** (`merge_rung_into_unit`): Eine Kompetenz-Seite (links Ziele, rechts
Kompetenzen) wird nur ersetzt, wenn die Sprosse dort Bausteine hat – dann
vollständig, mit der Positionsregel (oberster linker Baustein = Stundenziel).
Material und Ideen werden **angehängt** (Material ohne Doppelte nach
`collision_keys`). Das Oberthema der Einheit wird das der Sequenz.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import replace
from enum import Enum

from kursplaner.core.domain.day_column import DayColumn
from kursplaner.core.domain.plan_row_payload import RowPayload
from kursplaner.core.domain.sequence_ladder import COMPETENCE_SIDES, LadderRung, LadderSide, collision_keys
from kursplaner.core.domain.sequence_ladder_entries import block_from_entry, entry_from_block
from kursplaner.core.domain.sequence_ladder_homes import (
    MarkerHome,
    RungKind,
    UnitContent,
    UnitHome,
    left_entries,
    locked_reason,
    term_home,
    unit_entries,
    unit_with_entries,
)

BLOCKED_TARGET_KINDS = frozenset({RungKind.LZK, RungKind.HOSPITATION, RungKind.AUSFALL})
"""Terminarten, denen keine Sprosse zugeordnet werden kann (keine Ziel-/Kompetenzfelder)."""


def assign_target_error(day: DayColumn) -> str | None:
    """Fehlertext, wenn *day* keine Sprosse aufnehmen kann (LZK, Hospitation, Ausfall), sonst ``None``."""
    home = term_home(day)
    if isinstance(home, MarkerHome) and home.kind in BLOCKED_TARGET_KINDS:
        where = day.datum.strip() or "Diese Zeile"
        return f"{where}: {locked_reason(home.kind)} – dorthin kann keine Sprosse zugeordnet werden."
    return None


class TargetKind(Enum):
    """Art einer angebotenen Zielzeile beim Zuordnen (siehe `target_kind`)."""

    MEMBER = "member"
    """Termin dieser Sequenz – nicht wählbar."""
    BLOCKED = "blocked"
    """LZK, Hospitation oder Ausfall – nicht wählbar (`assign_target_error`)."""
    FREE = "free"
    """Leerer Termin – eine neue Unterrichtsdatei wird angelegt."""
    OCCUPIED = "occupied"
    """Belegt (Einheit einer anderen Sequenz, geplantes Thema, Datei fehlt) – nur Einfügen + Verschieben."""
    LOOSE_UNIT = "loose_unit"
    """Unterrichtseinheit ohne Oberthema – Einfügen + Verschieben oder Übernehmen."""


SELECTABLE_KINDS = frozenset({TargetKind.FREE, TargetKind.OCCUPIED, TargetKind.LOOSE_UNIT})
"""Zielarten, die der Nutzer wählen kann."""


def target_kind(day: DayColumn, member_rows: Collection[int]) -> TargetKind:
    """Einzige Regel, wie eine Plan-Zeile beim Zuordnen behandelt wird.

    Args:
        day: Die Zeile.
        member_rows: Termine der Sequenz (`sequence_term_days`).
    """
    if day.row_index in member_rows:
        return TargetKind.MEMBER
    if assign_target_error(day):
        return TargetKind.BLOCKED
    if RowPayload.of_cells(day.inhalt, day.thema_ausfall).is_empty:
        return TargetKind.FREE
    if isinstance(term_home(day), UnitHome) and not day.oberthema():
        return TargetKind.LOOSE_UNIT
    return TargetKind.OCCUPIED


def _entries(rung: LadderRung, side: LadderSide) -> tuple[str, ...]:
    return tuple(entry_from_block(block) for block in rung.blocks(side))


def merge_rung_into_unit(rung: LadderRung, old: UnitContent) -> UnitContent:
    """Inhalt der Einheit nach dem Zuordnen von *rung* (siehe Moduldocstring).

    Args:
        rung: Die Ablage-Sprosse.
        old: Bisheriger Inhalt der Einheit (leer bei neu angelegter Einheit).
    """
    merged = old
    for side in COMPETENCE_SIDES:
        if rung.blocks(side):
            merged = unit_with_entries(merged, side, _entries(rung, side))
    merged = unit_with_entries(merged, LadderSide.MATERIAL, _appended_material(rung, old))
    return replace(merged, ideen=tuple(old.ideen) + tuple(rung.ideen))


def _appended_material(rung: LadderRung, old: UnitContent) -> tuple[str, ...]:
    """Material der Einheit, dahinter das der Sprosse, das dort noch nicht steht."""
    side = LadderSide.MATERIAL
    entries = list(unit_entries(old, side))
    seen = set().union(*(collision_keys(block_from_entry(entry, side)) for entry in entries))
    for block in rung.blocks(side):
        if not collision_keys(block) & seen:
            entries.append(entry_from_block(block))
            seen |= collision_keys(block)
    return tuple(entries)


def overwrite_warnings(rung: LadderRung, old: UnitContent, old_oberthema: str, oberthema: str) -> tuple[str, ...]:
    """Was beim Zuordnen von *rung* in einer bestehenden Einheit verloren geht oder sich ändert.

    Leer, wenn nichts überschrieben wird (dann ist keine Rückfrage nötig).

    Args:
        rung: Die Ablage-Sprosse.
        old: Bisheriger Inhalt der Einheit.
        old_oberthema: Bisheriges Oberthema der Einheit.
        oberthema: Oberthema der Sequenz.
    """
    warnings: list[str] = []
    if rung.inhalt and left_entries(old):
        warnings.append(_listed("Stunden-/Teilziele werden ersetzt", left_entries(old)))
    if rung.prozess and old.kompetenzen:
        warnings.append(_listed("Kompetenzen werden ersetzt", old.kompetenzen))
    if rung.material and old.material:
        warnings.append("Das Material der Sprosse wird an das vorhandene Material angehängt.")
    if rung.ideen and old.ideen:
        warnings.append("Die Ideen der Sprosse werden an die vorhandenen Ideen angehängt.")
    if old_oberthema.strip() and old_oberthema.strip() != oberthema.strip():
        warnings.append(f"Das Oberthema „{old_oberthema.strip()}“ wird zu „{oberthema.strip()}“.")
    return tuple(warnings)


def _listed(title: str, entries: Sequence[str]) -> str:
    return title + ":\n" + "\n".join(f"  • {entry}" for entry in entries)
