"""Sequenzleiter: reines Modell und Regeln (kein Dateizugriff, keine GUI).

Eine Leiter besteht aus Sprossen (Index 0 = unterste Sprosse = erste Einheit
der Sequenz). Jede Sprosse hat drei Bausteinseiten – inhaltsbezogen links,
prozessbezogen rechts, Material über dem Ideenfeld – und das Ideenfeld. Innerhalb
einer Zelle ist Index 0 der oberste Baustein.

Was eine Seite ausmacht, steht allein in der Regeltabelle `SIDE_RULES`
(Speicherfeld der Sprosse, Eindeutigkeitsbereich, Netz-Bausteine erlaubt,
Nomen für Meldungen). Der Baustein-Text ist innerhalb seines
Eindeutigkeitsbereichs Schlüssel (verglichen nach Trimmen und ohne
Groß-/Kleinschreibung, `block_key`): links (Stunden-/Teilziele) über die ganze
Spalte, rechts (geförderte Kompetenzen) und beim Material nur innerhalb einer
Sprosse – dieselbe Prozesskompetenz oder dasselbe Material darf in mehreren
Sprossen stehen. Ein Baustein wird daher über `BlockRef` (Sprosse, Seite, Text)
angesprochen. Bausteine aus dem Kompetenznetz (nur Inhalt/Prozess) tragen
zusätzlich die Kompetenz-ID und sind nicht umbenennbar.

Gesperrte Sprossen (`SequenceLadder.locked_rungs`, z. B. LZK/Hospitation/Ausfall)
nehmen keine Bausteine und keine Ideen auf; die Sperre wird aus den Terminen
abgeleitet und nie gespeichert (`sequence_ladder_homes`). Bausteine, die schon
vor der Eindeutigkeitsregel doppelt standen, meldet `duplicate_groups`.
Siehe `docs/ARCHITEKTUR_KERN.md` §37.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum

from kursplaner.core.domain.list_cell_text import list_entry_violation


class LadderSide(str, Enum):
    """Bausteinseite einer Sprosse; der Wert ist das Label im Dateiformat der Ablage."""

    INHALT = "Inhalt"
    PROZESS = "Prozess"
    MATERIAL = "Material"


@dataclass(frozen=True)
class SideRules:
    """Regeln einer Bausteinseite (eine Zeile von `SIDE_RULES`).

    Attributes:
        field: Attribut von `LadderRung`, das die Bausteine der Seite hält.
        per_rung: Eindeutigkeit je Sprosse (``True``) oder über die ganze Spalte.
        network: Die Seite nimmt Netz-Bausteine (``[[ID|Titel]]``) auf.
        noun: Was ein Baustein dieser Seite für die Nutzerin ist (Meldungen).
    """

    field: str
    per_rung: bool
    network: bool
    noun: str


SIDE_RULES: dict[LadderSide, SideRules] = {
    LadderSide.INHALT: SideRules("inhalt", per_rung=False, network=True, noun="Lernziel"),
    LadderSide.PROZESS: SideRules("prozess", per_rung=True, network=True, noun="Kompetenz"),
    LadderSide.MATERIAL: SideRules("material", per_rung=True, network=False, noun="Material"),
}
"""Einzige Tabelle der Seitenregeln; alle Abfragen unten und in den Nachbarmodulen lesen sie."""

COMPETENCE_SIDES: tuple[LadderSide, ...] = tuple(side for side, rules in SIDE_RULES.items() if rules.network)
"""Seiten, die Kompetenzen aus dem Netz aufnehmen (Inhalt, Prozess) – Ziel von Import und Bereichswahl."""


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
    """Eine Sprosse: Bausteine je Seite (oben → unten) und die Zeilen des Ideenfelds.

    ``material`` steht als letztes Feld, damit ``LadderRung(inhalt, prozess, ideen)`` gültig bleibt.
    """

    inhalt: tuple[LadderBlock, ...] = ()
    prozess: tuple[LadderBlock, ...] = ()
    ideen: tuple[str, ...] = ()
    material: tuple[LadderBlock, ...] = ()

    def blocks(self, side: LadderSide) -> tuple[LadderBlock, ...]:
        """Bausteine einer Seite (Feld aus `SIDE_RULES`)."""
        return getattr(self, SIDE_RULES[side].field)

    def with_blocks(self, side: LadderSide, blocks: tuple[LadderBlock, ...]) -> LadderRung:
        """Kopie mit neuen Bausteinen auf einer Seite."""
        return replace(self, **{SIDE_RULES[side].field: tuple(blocks)})

    @property
    def is_empty(self) -> bool:
        """Keine Bausteine und kein nicht-leerer Ideentext."""
        return not any(self.blocks(side) for side in LadderSide) and not any(line.strip() for line in self.ideen)


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


def collision_keys(block: LadderBlock) -> frozenset[tuple[str, str]]:
    """Schlüssel, über die zwei Bausteine im selben Bereich kollidieren – die einzige Stelle dieser Regel.

    Gleicher Text (`block_key`) oder – bei Netz-Bausteinen – gleiche Kompetenz-ID.
    """
    keys = {("text", block_key(block.text))}
    if block.kompetenz_id is not None:
        keys.add(("id", block.kompetenz_id))
    return frozenset(keys)


def uniqueness_scope(side: LadderSide, rung: int) -> tuple[object, ...]:
    """Eindeutigkeitsbereich eines Bausteins (aus `SIDE_RULES`, sonst nirgends abgefragt).

    Links (Stunden-/Teilziele) ist die ganze Spalte ein Bereich, rechts
    (vorrangig geförderte Kompetenzen) und beim Material jede Sprosse für sich.
    Zwei Bausteine kollidieren genau dann, wenn ihr Bereich gleich ist und Text
    oder Kompetenz-ID übereinstimmen.
    """
    return (side, rung) if SIDE_RULES[side].per_rung else (side,)


@dataclass(frozen=True)
class SequenceLadder:
    """Die ganze Leiter; unveränderlich, Operationen liefern neue Leitern.

    Attributes:
        rungs: Sprossen von unten nach oben.
        locked_rungs: Indizes gesperrter Sprossen (keine Bausteine, keine Ideen).
    """

    rungs: tuple[LadderRung, ...] = ()
    locked_rungs: frozenset[int] = field(default_factory=frozenset)

    def rung(self, index: int) -> LadderRung:
        """Sprosse *index*; jenseits der gespeicherten Sprossen eine leere Sprosse."""
        return self.rungs[index] if 0 <= index < len(self.rungs) else LadderRung()

    def is_locked(self, index: int) -> bool:
        """``True``, wenn Sprosse *index* gesperrt ist."""
        return index in self.locked_rungs

    def with_rung(self, index: int, rung: LadderRung) -> SequenceLadder:
        """Kopie mit ersetzter Sprosse; fehlende Sprossen darunter werden leer ergänzt."""
        if index < 0:
            raise LadderRuleError("Unter der ersten Sprosse gibt es keine Sprosse.")
        rungs = list(self.rungs) + [LadderRung()] * max(0, index + 1 - len(self.rungs))
        rungs[index] = rung
        return replace(self, rungs=tuple(rungs))

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
        scope, wanted = uniqueness_scope(side, rung), collision_keys(LadderBlock(text, kompetenz_id))
        ignored = (ignore.rung, ignore.side, block_key(ignore.text)) if ignore is not None else None
        for rung_index, other in enumerate(self.rungs):
            if uniqueness_scope(side, rung_index) != scope:
                continue
            for block in other.blocks(side):
                if (rung_index, side, block_key(block.text)) == ignored:
                    continue
                if wanted & collision_keys(block):
                    return block
        return None

    def highest_occupied(self, side: LadderSide) -> int:
        """Index der höchsten Sprosse mit Bausteinen in *side*, ``-1`` wenn keine."""
        return max((index for index, rung in enumerate(self.rungs) if rung.blocks(side)), default=-1)

    def duplicate_groups(self) -> tuple[tuple[BlockRef, ...], ...]:
        """Gruppen von Bausteinen, die in ihrem Eindeutigkeitsbereich miteinander kollidieren.

        Neue Kollisionen verhindern die Operationen; diese Abfrage findet den
        Altbestand (z. B. dasselbe Lernziel in zwei Einheiten), damit er markiert
        werden kann. Eine Gruppe ist zusammenhängend: zwei Bausteine gehören
        dazu, wenn sie – auch über einen dritten hinweg – einen Kollisionsschlüssel
        (`collision_keys`) im selben Bereich teilen. Reihenfolge: unten → oben.
        """
        by_key: dict[tuple[object, ...], list[BlockRef]] = {}
        keys_of: dict[BlockRef, set[tuple[object, ...]]] = {}
        for index, rung in enumerate(self.rungs):
            for side in LadderSide:
                scope = uniqueness_scope(side, index)
                for block in rung.blocks(side):
                    ref = BlockRef(index, side, block.text)
                    keys_of[ref] = {(scope, key) for key in collision_keys(block)}
                    for key in keys_of[ref]:
                        by_key.setdefault(key, []).append(ref)
        groups: list[tuple[BlockRef, ...]] = []
        seen: set[BlockRef] = set()
        for start in keys_of:
            if start in seen:
                continue
            group, todo = [], [start]
            while todo:
                ref = todo.pop()
                if ref in seen:
                    continue
                seen.add(ref)
                group.append(ref)
                todo.extend(other for key in keys_of[ref] for other in by_key[key])
            if len(group) > 1:
                groups.append(tuple(sorted(group, key=lambda r: r.rung)))
        return tuple(groups)

    def without_rung(self, index: int) -> SequenceLadder:
        """Kopie ohne Sprosse *index*; die Sprossen darüber rücken eine Stufe nach unten.

        Gesperrte Indizes oberhalb rücken mit, der entfernte Index entfällt. Genutzt,
        wenn eine Ablage-Sprosse einer Einheit zugeordnet wird (`sequence_ladder_assign`).
        """
        if not 0 <= index < len(self.rungs):
            return self
        rungs = self.rungs[:index] + self.rungs[index + 1 :]
        locked = frozenset(i - 1 if i > index else i for i in self.locked_rungs if i != index)
        return replace(self, rungs=rungs, locked_rungs=locked)

    def trimmed(self) -> SequenceLadder:
        """Kopie ohne leere Sprossen am oberen Ende (werden nicht gespeichert)."""
        rungs = list(self.rungs)
        while rungs and rungs[-1].is_empty:
            rungs.pop()
        return replace(self, rungs=tuple(rungs))

    @property
    def is_empty(self) -> bool:
        """Keine Sprosse trägt Inhalt."""
        return all(rung.is_empty for rung in self.rungs)


def conflict_message(block: LadderBlock, side: LadderSide) -> str:
    """Nutzerlesbare Meldung zu einer Kollision im Eindeutigkeitsbereich von *side*."""
    where = "in dieser Sprosse" if SIDE_RULES[side].per_rung else "in dieser Spalte"
    return f"Es gibt {where} bereits einen Baustein „{block.text}“."


def locked_message(rung: int, reason: str = "") -> str:
    """Nutzerlesbare Meldung: Sprosse *rung* (0-basiert) ist gesperrt.

    Args:
        rung: Index der Sprosse (0 = unten).
        reason: Tatsächlicher Grund (`sequence_ladder_homes.locked_reason`); ohne ihn
            werden alle möglichen Gründe genannt (Aufrufer, die die Terminart nicht kennen).
    """
    why = reason or "LZK, Hospitation, Ausfall oder Termin ohne eigene, lesbare Unterrichtsdatei"
    return f"Sprosse {rung + 1} nimmt keine Bausteine oder Ideen auf ({why})."


def block_text_error(
    text: str, ladder: SequenceLadder, *, side: LadderSide, rung: int, ignore: BlockRef | None = None
) -> str | None:
    """Prüft den Text eines eigenen Bausteins; liefert eine Fehlermeldung oder ``None``.

    Regeln: nicht leer, einzeilig, auf Netz-Seiten (`SIDE_RULES`) nicht mit ``[[``
    beginnend (dort im Dateiformat für Netz-Bausteine reserviert; Material darf ein
    Wiki-Link sein), erfüllt den Listenvertrag der Einheiten-Felder
    (`list_cell_text.list_entry_violation`, z. B. nicht nur Striche) und ist in seinem
    Eindeutigkeitsbereich (`uniqueness_scope`) eindeutig.

    Args:
        text: Gewünschter Text.
        ladder: Aktuelle Leiter.
        side: Seite, auf der der Baustein liegen soll.
        rung: Sprosse, in der der Baustein liegen soll.
        ignore: Baustein, der beim Eindeutigkeitsvergleich nicht zählt
            (der umzubenennende Baustein selbst).
    """
    stripped = str(text).strip()
    if not stripped:
        return "Der Baustein braucht eine Beschreibung."
    if "\n" in stripped or "\r" in stripped:
        return "Die Beschreibung muss einzeilig sein."
    if SIDE_RULES[side].network and stripped.startswith("[["):
        return "Eigene Bausteine dürfen nicht mit „[[“ beginnen (reserviert für Kompetenzen aus dem Netz)."
    violation = list_entry_violation(stripped)
    if violation:
        return violation
    found = ladder.conflict(side, rung, stripped, ignore=ignore)
    return conflict_message(found, side) if found is not None else None
