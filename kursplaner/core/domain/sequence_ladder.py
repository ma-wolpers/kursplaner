"""Sequenzleiter: reines Modell und Regeln (kein Dateizugriff, keine GUI).

Eine Leiter besteht aus Sprossen (Index 0 = unterste Sprosse = erste Einheit
der Sequenz). Jede Sprosse hat zwei Bausteinspalten (inhaltsbezogen links,
prozessbezogen rechts) und ein Ideenfeld. Innerhalb einer Zelle ist Index 0 der
oberste Baustein.

Der Baustein-Text ist Primärschlüssel über die ganze Leiter (verglichen nach
Trimmen und ohne Groß-/Kleinschreibung, `block_key`). Bausteine aus dem
Kompetenznetz tragen zusätzlich die Kompetenz-ID und sind nicht umbenennbar.
Siehe `docs/ARCHITEKTUR_KERN.md` §37.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum


class LadderSide(str, Enum):
    """Bausteinspalte einer Sprosse; der Wert ist das Label im Dateiformat."""

    INHALT = "Inhalt"
    PROZESS = "Prozess"


class LadderRuleError(ValueError):
    """Eine Leiter-Operation verletzt eine fachliche Regel; der Text ist nutzerlesbar."""


@dataclass(frozen=True)
class LadderBlock:
    """Ein Baustein.

    Attributes:
        text: Beschreibung und Primärschlüssel (einzeilig).
        kompetenz_id: ID der Kompetenz im Netz (z. B. ``"Mat-RF-14"``) oder
            ``None`` für einen eigenen Baustein.
    """

    text: str
    kompetenz_id: str | None = None

    @property
    def is_network(self) -> bool:
        """``True`` für Bausteine aus dem Kompetenznetz (nicht umbenennbar)."""
        return self.kompetenz_id is not None


@dataclass(frozen=True)
class LadderRung:
    """Eine Sprosse: Bausteine je Spalte (oben → unten) und die Zeilen des Ideenfelds."""

    inhalt: tuple[LadderBlock, ...] = ()
    prozess: tuple[LadderBlock, ...] = ()
    ideen: tuple[str, ...] = ()

    def blocks(self, side: LadderSide) -> tuple[LadderBlock, ...]:
        """Bausteine einer Spalte."""
        return self.inhalt if side is LadderSide.INHALT else self.prozess

    def with_blocks(self, side: LadderSide, blocks: tuple[LadderBlock, ...]) -> LadderRung:
        """Kopie mit neuen Bausteinen in einer Spalte."""
        return replace(self, inhalt=blocks) if side is LadderSide.INHALT else replace(self, prozess=blocks)

    @property
    def is_empty(self) -> bool:
        """Keine Bausteine und kein nicht-leerer Ideentext."""
        return not self.inhalt and not self.prozess and not any(line.strip() for line in self.ideen)


@dataclass(frozen=True)
class LadderSlot:
    """Position: Sprosse (0 = unten), Spalte und Index in der Zelle (0 = oben)."""

    rung: int
    side: LadderSide
    index: int


def block_key(text: str) -> str:
    """Vergleichsschlüssel des Primärschlüssels: getrimmt, ohne Groß-/Kleinschreibung."""
    return str(text).strip().casefold()


@dataclass(frozen=True)
class SequenceLadder:
    """Die ganze Leiter; unveränderlich, Operationen liefern neue Leitern."""

    rungs: tuple[LadderRung, ...] = ()

    def rung(self, index: int) -> LadderRung:
        """Sprosse *index*; jenseits der gespeicherten Sprossen eine leere Sprosse."""
        return self.rungs[index] if 0 <= index < len(self.rungs) else LadderRung()

    def with_rung(self, index: int, rung: LadderRung) -> SequenceLadder:
        """Kopie mit ersetzter Sprosse; fehlende Sprossen darunter werden leer ergänzt."""
        if index < 0:
            raise LadderRuleError("Unter der ersten Sprosse gibt es keine Sprosse.")
        rungs = list(self.rungs) + [LadderRung()] * max(0, index + 1 - len(self.rungs))
        rungs[index] = rung
        return SequenceLadder(tuple(rungs))

    def locate(self, text: str) -> tuple[LadderSlot, LadderBlock] | None:
        """Position und Baustein zu einem Text (Vergleich über `block_key`), sonst ``None``."""
        key = block_key(text)
        for rung_index, rung in enumerate(self.rungs):
            for side in LadderSide:
                for index, block in enumerate(rung.blocks(side)):
                    if block_key(block.text) == key:
                        return LadderSlot(rung_index, side, index), block
        return None

    def contains_kompetenz(self, kompetenz_id: str) -> bool:
        """Ob eine Kompetenz bereits als Baustein auf der Leiter liegt."""
        return any(
            block.kompetenz_id == kompetenz_id
            for rung in self.rungs
            for side in LadderSide
            for block in rung.blocks(side)
        )

    def highest_occupied(self, side: LadderSide) -> int:
        """Index der höchsten Sprosse mit Bausteinen in *side*, ``-1`` wenn keine."""
        return max((index for index, rung in enumerate(self.rungs) if rung.blocks(side)), default=-1)

    def trimmed(self) -> SequenceLadder:
        """Kopie ohne leere Sprossen am oberen Ende (werden nicht gespeichert)."""
        rungs = list(self.rungs)
        while rungs and rungs[-1].is_empty:
            rungs.pop()
        return SequenceLadder(tuple(rungs))

    @property
    def is_empty(self) -> bool:
        """Keine Sprosse trägt Inhalt."""
        return all(rung.is_empty for rung in self.rungs)


def block_text_error(text: str, ladder: SequenceLadder, *, ignore: str | None = None) -> str | None:
    """Prüft den Text eines eigenen Bausteins; liefert eine Fehlermeldung oder ``None``.

    Regeln: nicht leer, einzeilig, beginnt nicht mit ``[[`` (im Dateiformat für
    Netz-Bausteine reserviert) und ist auf der ganzen Leiter eindeutig.

    Args:
        text: Gewünschter Text.
        ladder: Aktuelle Leiter.
        ignore: Text eines Bausteins, der beim Eindeutigkeitsvergleich nicht zählt
            (der umzubenennende Baustein selbst).
    """
    stripped = str(text).strip()
    if not stripped:
        return "Der Baustein braucht eine Beschreibung."
    if "\n" in stripped or "\r" in stripped:
        return "Die Beschreibung muss einzeilig sein."
    if stripped.startswith("[["):
        return "Eigene Bausteine dürfen nicht mit „[[“ beginnen (reserviert für Kompetenzen aus dem Netz)."
    found = ladder.locate(stripped)
    if found is not None and (ignore is None or block_key(found[1].text) != block_key(ignore)):
        return f"Es gibt bereits einen Baustein „{found[1].text}“."
    return None
