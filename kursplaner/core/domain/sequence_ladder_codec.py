"""Dateiformat der Leiter-Ablage in der Sequenzdatei: einzige Lese-/Schreibstelle (§27, §37).

Die Sequenzdatei speichert nur die **Ablage** – Sprossen jenseits der Termine
(„??“). Alle Sprossen mit Termin leben in ihren Einheiten (`sequence_ladder_homes`).
Der Abschnitt ``## Sequenzleiter`` ist eine verschachtelte Markdown-Liste, von
der ersten Ablage-Sprosse über dem letzten Termin (1) nach oben::

    - Ablage 1
      - Inhalt: Eigener Baustein
      - Inhalt: [[Mat-RF-14|Titel der Kompetenz]]
      - Prozess: [[Mat-DA-2|Titel der Kompetenz]]
      - Material: [[Material/AB Brüche.pdf|AB 1]]
      - Idee: eine Zeile des Ideenfelds
    - Ablage 2

Die Bausteinlabels sind die Werte von `LadderSide` (eine Zeile je Baustein, in
Seiten-Reihenfolge), ``Idee`` ist eine Zeile des Ideenfelds.

Gelesen und geschrieben wird die Ablage als `SequenceLadder`, deren Sprosse 0
„Ablage 1“ ist. Einträge übersetzt ausschließlich `sequence_ladder_entries`.
Der Parser ist strikt: jede unbekannte Zeile ist ein `LadderFormatError`, damit
Handeingaben nie still verloren gehen; ebenso ein Baustein, der die
Eindeutigkeitsregel (`uniqueness_scope`) innerhalb der Ablage verletzt.
"""

from __future__ import annotations

import re

from kursplaner.core.domain.sequence_ladder import (
    SIDE_RULES,
    LadderBlock,
    LadderRung,
    LadderSide,
    SequenceLadder,
    conflict_message,
)
from kursplaner.core.domain.sequence_ladder_entries import block_from_entry, entry_from_block
from kursplaner.core.domain.wiki_links import whole_wiki_link

LADDER_HEADING = "Sequenzleiter"
"""Überschrift (Ebene 2) des Ablage-Abschnitts in der Sequenzdatei."""

_RUNG_LABEL = "Ablage"
_IDEA_LABEL = "Idee"
_RUNG_RE = re.compile(rf"^- {_RUNG_LABEL} (\d+)\s*$")
_ENTRY_RE = re.compile(r"^  - ([A-Za-zÄÖÜäöüß]+):(?: (.*))?$")


class LadderFormatError(ValueError):
    """Der Ablage-Abschnitt ist nicht im erwarteten Format.

    Attributes:
        line_no: 1-basierte Zeilennummer innerhalb des Abschnitts.
    """

    def __init__(self, line_no: int, message: str) -> None:
        super().__init__(f"Sequenzleiter-Ablage, Zeile {line_no}: {message}")
        self.line_no = line_no


def format_ablage_section(ablage: SequenceLadder) -> list[str]:
    """Abschnittsinhalt (ohne Überschrift) als Zeilenliste; leere Ablage → keine Zeilen."""
    lines: list[str] = []
    for index, rung in enumerate(ablage.trimmed().rungs):
        lines.append(f"- {_RUNG_LABEL} {index + 1}")
        for side in LadderSide:
            lines.extend(f"  - {side.value}: {entry_from_block(block)}" for block in rung.blocks(side))
        lines.extend(f"  - {_IDEA_LABEL}: {line}".rstrip() for line in rung.ideen)
    return lines


def _parse_block(value: str, side: LadderSide, line_no: int) -> LadderBlock:
    if SIDE_RULES[side].network and value.startswith("[[") and whole_wiki_link(value) is None:
        raise LadderFormatError(line_no, "Ein Netz-Baustein muss genau ein Wiki-Link sein.")
    if not value:
        raise LadderFormatError(line_no, "Baustein ohne Beschreibung.")
    return block_from_entry(value, side)


_LABELS = (*(side.value for side in LadderSide), _IDEA_LABEL)
"""Erlaubte Eintragslabels einer Ablage-Sprosse (Fehlermeldung und Parser)."""


def parse_ablage_section(body: str) -> SequenceLadder:
    """Liest den Abschnittsinhalt (ohne Überschrift); Sprosse 0 = „Ablage 1“.

    Raises:
        LadderFormatError: Bei jeder Abweichung vom Format (unbekannte Zeile,
            Ablage-Sprossen nicht lückenlos ab 1, Eintrag vor der ersten Sprosse, …).
    """
    rungs: list[dict[str, list]] = []
    for line_no, raw in enumerate(str(body).splitlines(), start=1):
        line = raw.rstrip()
        if not line.strip():
            continue
        rung_match = _RUNG_RE.match(line)
        if rung_match is not None:
            if int(rung_match.group(1)) != len(rungs) + 1:
                raise LadderFormatError(line_no, f"Erwartet „{_RUNG_LABEL} {len(rungs) + 1}“.")
            rungs.append({label: [] for label in _LABELS})
            continue
        entry = _ENTRY_RE.match(line)
        if entry is None:
            raise LadderFormatError(line_no, f"Unbekannte Zeile: {line.strip()}")
        if not rungs:
            raise LadderFormatError(line_no, "Eintrag vor der ersten Ablage-Sprosse.")
        label, value = entry.group(1), (entry.group(2) or "").strip()
        if label not in rungs[-1]:
            raise LadderFormatError(line_no, f"Unbekannte Spalte „{label}“ (erlaubt: {', '.join(_LABELS)}).")
        if label == _IDEA_LABEL:
            rungs[-1][label].append(value)
            continue
        side = LadderSide(label)
        block = _parse_block(value, side, line_no)
        clash = _build(rungs).conflict(side, len(rungs) - 1, block.text, kompetenz_id=block.kompetenz_id)
        if clash is not None:
            raise LadderFormatError(line_no, conflict_message(clash, side))
        rungs[-1][label].append(block)
    return _build(rungs)


def _build(rungs: list[dict[str, list]]) -> SequenceLadder:
    built: list[LadderRung] = []
    for entries in rungs:
        rung = LadderRung(ideen=tuple(entries[_IDEA_LABEL]))
        for side in LadderSide:
            rung = rung.with_blocks(side, tuple(entries[side.value]))
        built.append(rung)
    return SequenceLadder(tuple(built))
