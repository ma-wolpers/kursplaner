"""Sequenzleiter: reines Modell und Regeln (kein Dateizugriff, keine GUI).

Eine Leiter besteht aus Sprossen (Index 0 = unterste Sprosse = erste Einheit
der Sequenz). Jede Sprosse hat zwei Bausteinspalten (inhaltsbezogen links,
prozessbezogen rechts) und ein Ideenfeld. Innerhalb einer Zelle ist Index 0 der
oberste Baustein.

Der Baustein-Text ist innerhalb seines Eindeutigkeitsbereichs Schlüssel
(verglichen nach Trimmen und ohne Groß-/Kleinschreibung, `block_key`): links
(Stunden-/Teilziele) über die ganze Spalte, rechts (geförderte Kompetenzen) nur
innerhalb einer Sprosse – dieselbe Prozesskompetenz darf in mehreren Sprossen
stehen. Die Regel steht allein in `uniqueness_scope`; ein Baustein wird daher
über `BlockRef` (Sprosse, Spalte, Text) angesprochen. Bausteine aus dem
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


@dataclass(frozen=True)
class BlockRef:
    """Verweis auf einen Baustein: Sprosse, Spalte und Text (innerhalb der Zelle eindeutig)."""

    rung: int
    side: LadderSide
    text: str


def block_key(text: str) -> str:
    """Vergleichsschlüssel eines Baustein-Texts: getrimmt, ohne Groß-/Kleinschreibung."""
    return str(text).strip().casefold()


def uniqueness_scope(side: LadderSide, rung: int) -> tuple[object, ...]:
    """Eindeutigkeitsbereich eines Bausteins – die einzige Stelle dieser Regel.

    Links (Stunden-/Teilziele) ist die ganze Spalte ein Bereich, rechts
    (vorrangig geförderte Kompetenzen) jede Sprosse für sich. Zwei Bausteine
    kollidieren genau dann, wenn ihr Bereich gleich ist und Text oder
    Kompetenz-ID übereinstimmen.
    """
    return (side,) if side is LadderSide.INHALT else (side, rung)


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

    def find(self, ref: BlockRef) -> tuple[LadderSlot, LadderBlock] | None:
        """Position und Baustein zu *ref* (Textvergleich über `block_key`), sonst ``None``."""
        key = block_key(ref.text)
        for index, block in enumerate(self.rung(ref.rung).blocks(ref.side)):
            if block_key(block.text) == key:
                return LadderSlot(ref.rung, ref.side, index), block
        return None

    def ref_at(self, slot: LadderSlot) -> BlockRef | None:
        """Verweis auf den Baustein an *slot*, ``None`` wenn dort keiner liegt."""
        blocks = self.rung(slot.rung).blocks(slot.side)
        return BlockRef(slot.rung, slot.side, blocks[slot.index].text) if 0 <= slot.index < len(blocks) else None

    def conflict(
        self,
        side: LadderSide,
        rung: int,
        text: str,
        *,
        kompetenz_id: str | None = None,
        ignore: BlockRef | None = None,
    ) -> LadderBlock | None:
        """Baustein, mit dem ein Baustein (*text*/*kompetenz_id*) an Sprosse *rung* kollidieren würde.

        Args:
            side: Spalte des geprüften Bausteins.
            rung: Zielsprosse des geprüften Bausteins.
            text: Sein Text.
            kompetenz_id: Seine Kompetenz-ID (Netz-Baustein) oder ``None``.
            ignore: Baustein, der nicht zählt (der verschobene/umbenannte selbst).
        """
        scope, key = uniqueness_scope(side, rung), block_key(text)
        ignored = (ignore.rung, ignore.side, block_key(ignore.text)) if ignore is not None else None
        for rung_index, other in enumerate(self.rungs):
            if uniqueness_scope(side, rung_index) != scope:
                continue
            for block in other.blocks(side):
                if (rung_index, side, block_key(block.text)) == ignored:
                    continue
                if block_key(block.text) == key or (kompetenz_id is not None and block.kompetenz_id == kompetenz_id):
                    return block
        return None

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


def conflict_message(block: LadderBlock, side: LadderSide) -> str:
    """Nutzerlesbare Meldung zu einer Kollision im Eindeutigkeitsbereich von *side*."""
    where = "in dieser Spalte" if side is LadderSide.INHALT else "in dieser Sprosse"
    return f"Es gibt {where} bereits einen Baustein „{block.text}“."


def block_text_error(
    text: str, ladder: SequenceLadder, *, side: LadderSide, rung: int, ignore: BlockRef | None = None
) -> str | None:
    """Prüft den Text eines eigenen Bausteins; liefert eine Fehlermeldung oder ``None``.

    Regeln: nicht leer, einzeilig, beginnt nicht mit ``[[`` (im Dateiformat für
    Netz-Bausteine reserviert) und ist in seinem Eindeutigkeitsbereich
    (`uniqueness_scope`) eindeutig.

    Args:
        text: Gewünschter Text.
        ladder: Aktuelle Leiter.
        side: Spalte, in der der Baustein liegen soll.
        rung: Sprosse, in der der Baustein liegen soll.
        ignore: Baustein, der beim Eindeutigkeitsvergleich nicht zählt
            (der umzubenennende Baustein selbst).
    """
    stripped = str(text).strip()
    if not stripped:
        return "Der Baustein braucht eine Beschreibung."
    if "\n" in stripped or "\r" in stripped:
        return "Die Beschreibung muss einzeilig sein."
    if stripped.startswith("[["):
        return "Eigene Bausteine dürfen nicht mit „[[“ beginnen (reserviert für Kompetenzen aus dem Netz)."
    found = ladder.conflict(side, rung, stripped, ignore=ignore)
    return conflict_message(found, side) if found is not None else None
