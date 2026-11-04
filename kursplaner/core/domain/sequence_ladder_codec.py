"""Dateiformat der Sequenzleiter: einzige Lese-/Schreibstelle (§27, §37).

Der Abschnitt ``## Sequenzleiter`` einer Sequenzdatei ist eine verschachtelte
Markdown-Liste, Sprossen von unten (1) nach oben::

    - Sprosse 1
      - Inhalt: Eigener Baustein
      - Inhalt: [[Mat-RF-14|Titel der Kompetenz]]
      - Prozess: [[Mat-DA-2|Titel der Kompetenz]]
      - Idee: eine Zeile des Ideenfelds
    - Sprosse 2

Netz-Bausteine sind genau ein Wiki-Link (Ziel = Kompetenz-ID, Alias = Titel);
Links bauen und lesen ausschließlich `wiki_links`. Der Parser ist strikt: jede
unbekannte Zeile ist ein `LadderFormatError`, damit Handeingaben nie still
verloren gehen.
"""

from __future__ import annotations

import re

from kursplaner.core.domain.sequence_ladder import LadderBlock, LadderRung, LadderSide, SequenceLadder
from kursplaner.core.domain.wiki_links import build_wiki_link, extract_wiki_link_target, wiki_link_display_text

LADDER_HEADING = "Sequenzleiter"
"""Überschrift (Ebene 2) des Leiter-Abschnitts in der Sequenzdatei."""

_IDEA_LABEL = "Idee"
_RUNG_RE = re.compile(r"^- Sprosse (\d+)\s*$")
_ENTRY_RE = re.compile(r"^  - ([A-Za-zÄÖÜäöüß]+):(?: (.*))?$")
_LINK_RE = re.compile(r"\[\[[^\[\]]+\]\]")


class LadderFormatError(ValueError):
    """Der Leiter-Abschnitt ist nicht im erwarteten Format.

    Attributes:
        line_no: 1-basierte Zeilennummer innerhalb des Abschnitts.
    """

    def __init__(self, line_no: int, message: str) -> None:
        super().__init__(f"Sequenzleiter, Zeile {line_no}: {message}")
        self.line_no = line_no


def network_block_text(kompetenz_id: str, title: str) -> str:
    """Text, den ein Netz-Baustein nach dem Rundweg durch die Datei trägt.

    Baut den Link wie beim Schreiben und liest den Alias wie beim Lesen; so ist
    der Primärschlüssel vor und nach dem Speichern identisch, auch wenn der
    Titel Zeichen enthält, die `build_wiki_link` normalisiert.
    """
    return wiki_link_display_text(build_wiki_link(kompetenz_id, title or kompetenz_id))


def _format_block(side: LadderSide, block: LadderBlock) -> str:
    if block.kompetenz_id is not None:
        return f"  - {side.value}: {build_wiki_link(block.kompetenz_id, block.text)}"
    return f"  - {side.value}: {block.text}"


def format_ladder_section(ladder: SequenceLadder) -> list[str]:
    """Abschnittsinhalt (ohne Überschrift) als Zeilenliste; leere Leiter → keine Zeilen."""
    lines: list[str] = []
    for index, rung in enumerate(ladder.trimmed().rungs):
        lines.append(f"- Sprosse {index + 1}")
        for side in LadderSide:
            lines.extend(_format_block(side, block) for block in rung.blocks(side))
        lines.extend(f"  - {_IDEA_LABEL}: {line}".rstrip() for line in rung.ideen)
    return lines


def _parse_block(value: str, line_no: int) -> LadderBlock:
    if value.startswith("[["):
        if _LINK_RE.fullmatch(value) is None:
            raise LadderFormatError(line_no, "Ein Netz-Baustein muss genau ein Wiki-Link sein.")
        return LadderBlock(wiki_link_display_text(value), extract_wiki_link_target(value))
    if not value:
        raise LadderFormatError(line_no, "Baustein ohne Beschreibung.")
    return LadderBlock(value)


def parse_ladder_section(body: str) -> SequenceLadder:
    """Liest den Abschnittsinhalt (ohne Überschrift).

    Raises:
        LadderFormatError: Bei jeder Abweichung vom Format (unbekannte Zeile,
            Sprossen nicht lückenlos ab 1, Eintrag vor der ersten Sprosse, …).
    """
    rungs: list[dict[str, list]] = []
    for line_no, raw in enumerate(str(body).splitlines(), start=1):
        line = raw.rstrip()
        if not line.strip():
            continue
        rung_match = _RUNG_RE.match(line)
        if rung_match is not None:
            if int(rung_match.group(1)) != len(rungs) + 1:
                raise LadderFormatError(line_no, f"Erwartet „Sprosse {len(rungs) + 1}“.")
            rungs.append({LadderSide.INHALT.value: [], LadderSide.PROZESS.value: [], _IDEA_LABEL: []})
            continue
        entry = _ENTRY_RE.match(line)
        if entry is None:
            raise LadderFormatError(line_no, f"Unbekannte Zeile: {line.strip()}")
        if not rungs:
            raise LadderFormatError(line_no, "Eintrag vor der ersten Sprosse.")
        label, value = entry.group(1), (entry.group(2) or "").strip()
        if label not in rungs[-1]:
            raise LadderFormatError(line_no, f"Unbekannte Spalte „{label}“ (erlaubt: Inhalt, Prozess, Idee).")
        rungs[-1][label].append(value if label == _IDEA_LABEL else _parse_block(value, line_no))
    return SequenceLadder(
        tuple(
            LadderRung(
                tuple(rung[LadderSide.INHALT.value]), tuple(rung[LadderSide.PROZESS.value]), tuple(rung[_IDEA_LABEL])
            )
            for rung in rungs
        )
    )
