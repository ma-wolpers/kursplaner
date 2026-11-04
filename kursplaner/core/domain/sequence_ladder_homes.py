"""Speicherorte der Sequenzleiter: einzige Stelle, die festlegt, wo eine Sprosse lebt (§37).

Die Leiter ist eine **Sicht auf die Einheiten** – jede Information hat genau einen
Speicherort, es gibt keine Kopie, die synchron gehalten werden müsste:

| Sprosse | Zuhause | links | rechts | Ideen |
|---|---|---|---|---|
| Termin mit Unterricht-Einheit | `UnitHome` | ``Stundenziel`` + ``Teilziele`` | ``Kompetenzen`` | ``## Ideen`` im Body |
| LZK / Hospitation / Ausfall | `MarkerHome` | gesperrt | gesperrt | gesperrt |
| jenseits der Termine („??“) | `AblageHome` | Sequenzdatei | Sequenzdatei | Sequenzdatei |

**Positionsregel** (nur hier): der oberste linke Baustein einer Einheit ist ihr
``Stundenziel``, die übrigen sind ``Teilziele`` (`goals_from_left`). Wird das
Stundenziel gelöscht oder verschoben, rückt der nächste Baustein nach.

`compose_ladder` setzt die Leiter aus Einheiten und Ablage zusammen,
`split_ladder` verteilt eine geänderte Leiter zurück. Beim Zurückverteilen wird
je Einheit und Teil (links, rechts, Ideen) verglichen: unveränderte Teile
bleiben wörtlich, wie sie gespeichert sind, und unveränderte Bausteine behalten
ihren gespeicherten Eintragstext. Einträge übersetzt `sequence_ladder_entries`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Union

from kursplaner.core.domain.day_column import DayColumn
from kursplaner.core.domain.lesson_yaml_policy import LessonType, lesson_list_entries
from kursplaner.core.domain.sequence_ladder import (
    LadderBlock,
    LadderRuleError,
    LadderRung,
    LadderSide,
    SequenceLadder,
    collision_keys,
    locked_message,
)
from kursplaner.core.domain.sequence_ladder_entries import block_from_entry, entry_from_block
from kursplaner.core.domain.topic_sequence_runs import row_lesson_type

IDEEN_HEADING = "Ideen"
"""Überschrift (Ebene 2) des Ideen-Abschnitts im Body einer Einheit."""


class RungKind(str, Enum):
    """Art des Termins einer Sprosse (steuert Speicherort und Markierung)."""

    UNTERRICHT = "unterricht"
    LZK = "lzk"
    HOSPITATION = "hospitation"
    AUSFALL = "ausfall"
    OFFEN = "offen"


_KIND_BY_LESSON_TYPE = {"Ausfall": RungKind.AUSFALL, "LZK": RungKind.LZK, "Hospitation": RungKind.HOSPITATION}


def rung_kind(day: DayColumn) -> RungKind:
    """Terminart einer Tagesspalte – übersetzt nur `topic_sequence_runs.row_lesson_type` (dort die Regel)."""
    return _KIND_BY_LESSON_TYPE.get(row_lesson_type(day), RungKind.UNTERRICHT)


@dataclass(frozen=True)
class UnitHome:
    """Sprosse lebt in einer Unterrichts-Einheit."""

    lesson_path: Path


@dataclass(frozen=True)
class MarkerHome:
    """Gesperrte Sprosse (LZK, Hospitation, Ausfall oder Termin ohne eigene Unterrichts-Einheit)."""

    kind: RungKind


@dataclass(frozen=True)
class AblageHome:
    """Sprosse jenseits der Termine; lebt in der Ablage der Sequenzdatei (``number`` ab 1)."""

    number: int


RungHome = Union[UnitHome, MarkerHome, AblageHome]


@dataclass(frozen=True)
class LadderHomes:
    """Zuhause jeder Sprosse: je Termin eines, darüber beliebig viele Ablage-Sprossen."""

    terms: tuple[UnitHome | MarkerHome, ...] = ()

    def home(self, rung: int) -> RungHome:
        """Zuhause der Sprosse *rung* (0 = unten)."""
        return self.terms[rung] if rung < len(self.terms) else AblageHome(rung - len(self.terms) + 1)

    @property
    def locked_rungs(self) -> frozenset[int]:
        """Sprossen, die nichts aufnehmen (alle `MarkerHome`)."""
        return frozenset(index for index, home in enumerate(self.terms) if isinstance(home, MarkerHome))

    @property
    def unit_paths(self) -> tuple[Path, ...]:
        """Einheiten-Dateien in Sprossen-Reihenfolge."""
        return tuple(home.lesson_path for home in self.terms if isinstance(home, UnitHome))


def ladder_homes(term_days: Sequence[DayColumn]) -> LadderHomes:
    """Zuhause je Termin (`sequence_term_days`, chronologisch = Sprossen von unten).

    Nur ein Unterrichtstermin mit verlinkter Unterricht-Einheit wird `UnitHome`;
    alles andere ist gesperrt. Verweisen zwei Termine auf dieselbe Datei, ist
    nur der erste ihr Zuhause, damit kein Inhalt doppelt erscheint.
    """
    seen: set[Path] = set()
    terms: list[UnitHome | MarkerHome] = []
    for day in term_days:
        kind = rung_kind(day)
        link = day.link
        if row_lesson_type(day) == UNIT_LESSON_TYPE and isinstance(link, Path):
            if link not in seen:
                seen.add(link)
                terms.append(UnitHome(link))
                continue
        terms.append(MarkerHome(kind))
    return LadderHomes(tuple(terms))


@dataclass(frozen=True)
class UnitContent:
    """Leiter-relevanter Inhalt einer Einheit, wie gespeichert (Einträge roh)."""

    stundenziel: str = ""
    teilziele: tuple[str, ...] = ()
    kompetenzen: tuple[str, ...] = ()
    ideen: tuple[str, ...] = ()


UNIT_LESSON_TYPE: LessonType = "Unterricht"
"""Nur dieser Stundentyp trägt Ziele und Kompetenzen (`lesson_yaml_policy`)."""


def unit_content_from_yaml(data: Mapping[str, object], ideen: Sequence[str]) -> UnitContent:
    """Leiter-relevanter Inhalt aus kanonisiertem Lesson-YAML und den ``## Ideen``-Zeilen."""
    return UnitContent(
        stundenziel=str(data.get("Stundenziel", "") or ""),
        teilziele=lesson_list_entries(data, "Teilziele"),
        kompetenzen=lesson_list_entries(data, "Kompetenzen"),
        ideen=tuple(ideen),
    )


def unit_goal_fields(unit: UnitContent) -> dict[str, object]:
    """YAML-Felder, in die die Bausteine einer Einheit geschrieben werden (Gegenstück zum Lesen)."""
    return {"Stundenziel": unit.stundenziel, "Teilziele": list(unit.teilziele), "Kompetenzen": list(unit.kompetenzen)}


def left_entries(unit: UnitContent) -> tuple[str, ...]:
    """Linke Einträge oben → unten: Stundenziel (falls gesetzt), dann Teilziele."""
    ziel = unit.stundenziel.strip()
    return ((ziel,) if ziel else ()) + tuple(unit.teilziele)


def goals_from_left(entries: Sequence[str]) -> tuple[str, tuple[str, ...]]:
    """Positionsregel: oberster Eintrag = Stundenziel, Rest = Teilziele."""
    return (entries[0], tuple(entries[1:])) if entries else ("", ())


def _unrepresentable(unit: UnitContent) -> str | None:
    for entry in left_entries(unit) + tuple(unit.kompetenzen):
        if "\n" in entry or "\r" in entry:
            return "mehrzeiliges Ziel bzw. mehrzeilige Kompetenz"
    return None


def _cell_blocks(entries: Sequence[str]) -> tuple[tuple[LadderBlock, ...], bool]:
    """Bausteine einer Zelle; doppelte Einträge derselben Zelle werden einmal gezeigt (zweiter Wert)."""
    blocks: list[LadderBlock] = []
    keys: set[tuple[str, str]] = set()
    dropped = False
    for entry in entries:
        block = block_from_entry(entry)
        own = collision_keys(block)
        if own & keys:
            dropped = True
            continue
        keys |= own
        blocks.append(block)
    return tuple(blocks), dropped


@dataclass(frozen=True)
class ComposedLadder:
    """Zusammengesetzte Leiter und Hinweise (gesperrte oder gekürzte Sprossen)."""

    ladder: SequenceLadder
    notes: tuple[str, ...] = ()


def compose_ladder(homes: LadderHomes, units: Mapping[Path, UnitContent], ablage: SequenceLadder) -> ComposedLadder:
    """Leiter aus Einheiten (*units* je Datei) und Ablage zusammensetzen.

    Eine Einheit, die fehlt (nicht lesbar) oder nicht als Bausteine darstellbar
    ist (mehrzeiliger Eintrag), macht ihre Sprosse gesperrt und erzeugt einen
    Hinweis – sie wird nie umgedeutet und daher auch nie zurückgeschrieben.
    """
    rungs: list[LadderRung] = []
    locked = set(homes.locked_rungs)
    notes: list[str] = []
    for index, home in enumerate(homes.terms):
        unit = units.get(home.lesson_path) if isinstance(home, UnitHome) else None
        if isinstance(home, UnitHome) and unit is None:
            notes.append(f"Sprosse {index + 1}: Einheit nicht lesbar – gesperrt.")
        elif unit is not None and (problem := _unrepresentable(unit)):
            notes.append(f"Sprosse {index + 1}: {problem} – bitte im Hauptfenster bearbeiten; gesperrt.")
            unit = None
        if unit is None:
            locked.add(index)
            rungs.append(LadderRung())
            continue
        left, left_dropped = _cell_blocks(left_entries(unit))
        right, right_dropped = _cell_blocks(unit.kompetenzen)
        if left_dropped or right_dropped:
            notes.append(f"Sprosse {index + 1}: doppelter Eintrag in der Einheit wird nur einmal gezeigt.")
        rungs.append(LadderRung(left, right, tuple(unit.ideen)))
    rungs.extend(ablage.trimmed().rungs)
    return ComposedLadder(SequenceLadder(tuple(rungs), frozenset(locked)).trimmed(), tuple(notes))


@dataclass(frozen=True)
class LadderSplit:
    """Zurückverteilte Leiter: nur geänderte Einheiten (neuer Inhalt) und die ganze Ablage."""

    units: Mapping[Path, UnitContent]
    ablage: SequenceLadder


def _raw_entries(units: Mapping[Path, UnitContent], side: LadderSide) -> dict[LadderBlock, str]:
    """Gespeicherter Eintragstext je (unverändertem) Baustein über alle Einheiten (erster gewinnt)."""
    raw: dict[LadderBlock, str] = {}
    for unit in units.values():
        entries = left_entries(unit) if side is LadderSide.INHALT else tuple(unit.kompetenzen)
        for entry in entries:
            raw.setdefault(block_from_entry(entry), entry.strip())
    return raw


def _entries(blocks: Sequence[LadderBlock], raw: Mapping[LadderBlock, str]) -> tuple[str, ...]:
    return tuple(raw.get(block) or entry_from_block(block) for block in blocks)


def _unit_from_rung(
    rung: LadderRung, old: UnitContent, raw: Mapping[LadderSide, Mapping[LadderBlock, str]]
) -> UnitContent:
    """Neuer Inhalt einer Einheit; unveränderte Teile bleiben wörtlich erhalten."""
    stundenziel, teilziele = old.stundenziel, old.teilziele
    if rung.inhalt != _cell_blocks(left_entries(old))[0]:
        stundenziel, teilziele = goals_from_left(_entries(rung.inhalt, raw[LadderSide.INHALT]))
    kompetenzen = old.kompetenzen
    if rung.prozess != _cell_blocks(old.kompetenzen)[0]:
        kompetenzen = _entries(rung.prozess, raw[LadderSide.PROZESS])
    ideen = old.ideen if rung.ideen == tuple(old.ideen) else rung.ideen
    return UnitContent(stundenziel, tuple(teilziele), tuple(kompetenzen), tuple(ideen))


def split_ladder(ladder: SequenceLadder, homes: LadderHomes, units: Mapping[Path, UnitContent]) -> LadderSplit:
    """Verteilt *ladder* auf ihre Speicherorte zurück (Gegenstück zu `compose_ladder`).

    Args:
        ladder: Leiter nach einer Operation.
        homes: Dieselben Speicherorte wie beim Zusammensetzen.
        units: Die Einheiten-Inhalte, aus denen zusammengesetzt wurde.

    Raises:
        LadderRuleError: Eine gesperrte Sprosse trägt Inhalt (darf nach den
            Operationen nie vorkommen; Schutz gegen stilles Verwerfen).
    """
    raw = {side: _raw_entries(units, side) for side in LadderSide}
    changed: dict[Path, UnitContent] = {}
    for index, home in enumerate(homes.terms):
        rung = ladder.rung(index)
        path = home.lesson_path if isinstance(home, UnitHome) else None
        unit = units.get(path) if path is not None else None
        if path is None or unit is None or ladder.is_locked(index):
            if not rung.is_empty:
                raise LadderRuleError(locked_message(index))
            continue
        new = _unit_from_rung(rung, unit, raw)
        if new != unit:
            changed[path] = new
    ablage = SequenceLadder(tuple(ladder.rung(i) for i in range(len(homes.terms), len(ladder.rungs))))
    return LadderSplit(changed, ablage.trimmed())
