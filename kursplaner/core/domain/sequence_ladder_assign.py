"""Regeln zum Zuordnen einer Ablage-Sprosse („??“) zu einer Plan-Zeile (§37).

Ablage-Sprossen leben in der Sequenzdatei; ihr Inhalt wandert nie automatisch in
eine Einheit. Das Zuordnen ist der ausdrückliche Weg dorthin. Hier stehen nur
die reinen Regeln, der Use Case `assign_ablage_rung_usecase` liest und schreibt:

| Zielzeile (`term_home`) | Verhalten |
|---|---|
| LZK, Hospitation, Ausfall | Fehler (`assign_target_error`) |
| Unterricht mit Datei | Inhalt übernehmen; vorher warnen, was überschrieben wird |
| Termin ohne Datei | Unterrichtsdatei anlegen, dann übernehmen |

**Übernahme** (`merge_rung_into_unit`): Eine Seite (links Ziele, rechts
Kompetenzen) wird nur ersetzt, wenn die Sprosse dort Bausteine hat – dann
vollständig, mit der Positionsregel (oberster linker Baustein = Stundenziel).
Ideen werden **angehängt**. Das Oberthema der Einheit wird das der Sequenz.
"""

from __future__ import annotations

from collections.abc import Sequence

from kursplaner.core.domain.day_column import DayColumn
from kursplaner.core.domain.sequence_ladder import LadderRung, LadderSide
from kursplaner.core.domain.sequence_ladder_entries import entry_from_block
from kursplaner.core.domain.sequence_ladder_homes import (
    MarkerHome,
    RungKind,
    UnitContent,
    goals_from_left,
    left_entries,
    locked_reason,
    term_home,
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


def needs_new_unit(day: DayColumn) -> bool:
    """``True``, wenn für *day* erst eine Unterrichtsdatei angelegt werden muss (Termin ohne Datei)."""
    return isinstance(term_home(day), MarkerHome) and assign_target_error(day) is None


def _entries(rung: LadderRung, side: LadderSide) -> tuple[str, ...]:
    return tuple(entry_from_block(block) for block in rung.blocks(side))


def merge_rung_into_unit(rung: LadderRung, old: UnitContent) -> UnitContent:
    """Inhalt der Einheit nach dem Zuordnen von *rung* (siehe Moduldocstring).

    Args:
        rung: Die Ablage-Sprosse.
        old: Bisheriger Inhalt der Einheit (leer bei neu angelegter Einheit).
    """
    stundenziel, teilziele = old.stundenziel, old.teilziele
    if rung.inhalt:
        stundenziel, teilziele = goals_from_left(_entries(rung, LadderSide.INHALT))
    kompetenzen = _entries(rung, LadderSide.PROZESS) if rung.prozess else old.kompetenzen
    return UnitContent(stundenziel, tuple(teilziele), tuple(kompetenzen), tuple(old.ideen) + tuple(rung.ideen))


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
    if rung.ideen and old.ideen:
        warnings.append("Die Ideen der Sprosse werden an die vorhandenen Ideen angehängt.")
    if old_oberthema.strip() and old_oberthema.strip() != oberthema.strip():
        warnings.append(f"Das Oberthema „{old_oberthema.strip()}“ wird zu „{oberthema.strip()}“.")
    return tuple(warnings)


def _listed(title: str, entries: Sequence[str]) -> str:
    return title + ":\n" + "\n".join(f"  • {entry}" for entry in entries)
