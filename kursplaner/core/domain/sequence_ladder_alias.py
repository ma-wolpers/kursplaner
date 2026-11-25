"""Alias eines Netz-Bausteins: einzige Stelle der Bearbeitungsregeln (§37).

Ein Netz-Baustein wird als ``[[ID|Text]]`` gespeichert. Der Text ist frei
bearbeitbar; die Formulierung der Kompetenz wird über die ID im Kompetenznetz
nachgeschlagen (`CompetenceOriginals` → `CompetenceWording`) und nie in der
Leiter gespeichert – so bleibt das Netz die einzige Quelle des Originals.
**Original** ist immer die Variante der Seite des Bausteins
(`CompetenceWording.for_side`: Infinitiv bei Lernzielen, Satzform bei Kompetenzen).

Regeln:

- Eingegebener Text wird wie beim Import normalisiert (`network_block_text`),
  damit der Primärschlüssel vor und nach dem Speichern derselbe ist.
- Eine **leere Eingabe** setzt den Text auf das Original der Seite zurück.
- Kollidiert dieses Original im Eindeutigkeitsbereich mit einem anderen
  Baustein, wird ein freier Vorschlag „<Original> (Kopie)“ gemacht
  (`alias_problem`); der Editor setzt ihn ins Feld.
- Das Original wird nur angezeigt, wenn der Baustein einen Alias trägt
  (`shows_original` → `CompetenceWording.alias_on`, die einzige Stelle der Regel).
- Kopieren überträgt den Alias-Zustand, nicht den Seitentext (`CopiedBlock`).

Diese Funktionen kennen keine GUI; der Controller übersetzt das Ergebnis von
`alias_problem` in die Editor-Rückmeldung.
"""

from __future__ import annotations

from dataclasses import dataclass

from kursplaner.core.domain.competence_wording import CompetenceWording
from kursplaner.core.domain.sequence_ladder import (
    SIDE_RULES,
    BlockRef,
    LadderBlock,
    LadderSide,
    SequenceLadder,
    block_text_error,
)
from kursplaner.core.domain.sequence_ladder_entries import network_block_text

COPY_SUFFIX = "Kopie"
"""Wort im Vorschlag für ein schon vorhandenes Original: „Titel (Kopie)“, „Titel (Kopie 2)“, …"""

_MAX_COPY_NUMBER = 99
"""Obergrenze der Vorschlagsnummer; danach gibt es keinen Vorschlag, nur die Meldung."""


@dataclass(frozen=True)
class AliasProblem:
    """Warum ein Alias nicht angenommen wird, mit optionalem Ersatzvorschlag.

    Attributes:
        message: Nutzerlesbare Meldung (aus `block_text_error`, ggf. ergänzt).
        suggestion: Freier Text, den der Editor ins Feld setzen soll, oder ``None``.
    """

    message: str
    suggestion: str | None = None


def side_original(wording: CompetenceWording | None, side: LadderSide) -> str | None:
    """Normalisiertes Original auf *side* oder ``None``, wenn die Formulierung unbekannt ist."""
    return wording.for_side(side) if wording is not None else None


def resolve_alias(raw: str, kompetenz_id: str, wording: CompetenceWording | None, side: LadderSide) -> str:
    """Text, den ein Netz-Baustein auf *side* nach der Eingabe *raw* trägt.

    Args:
        raw: Eingabe der Nutzerin (ungetrimmt).
        kompetenz_id: ID des Bausteins (bestimmt die Normalisierung).
        wording: Formulierung aus dem Netz oder ``None``, wenn sie nicht
            bekannt ist (ID nicht im Netz, Netz nicht geladen).
        side: Seite des Bausteins (bestimmt das Original).

    Returns:
        Bei leerer Eingabe das Original der Seite (ohne bekannte Formulierung
        ``""``, was `block_text_error` als fehlende Beschreibung meldet), sonst
        die normalisierte Eingabe.

    Example::

        resolve_alias("  ", "K-31", wording, LadderSide.INHALT)   # -> "Brüche darstellen"
        resolve_alias("Brüche zeigen", "K-31", None, LadderSide.INHALT)  # -> "Brüche zeigen"
    """
    text = str(raw).strip()
    if not text:
        return side_original(wording, side) or ""
    return network_block_text(kompetenz_id, text)


def _free_copy(
    original: str, ladder: SequenceLadder, side: LadderSide, rung: int, ignore: BlockRef | None
) -> str | None:
    """Erster kollisionsfreier Vorschlag „<Original> (Kopie)“, „(Kopie 2)“, … oder ``None``."""
    for number in range(1, _MAX_COPY_NUMBER + 1):
        label = COPY_SUFFIX if number == 1 else f"{COPY_SUFFIX} {number}"
        candidate = f"{original} ({label})"
        if block_text_error(candidate, ladder, side=side, rung=rung, ignore=ignore) is None:
            return candidate
    return None


def alias_problem(
    raw: str,
    ladder: SequenceLadder,
    *,
    side: LadderSide,
    rung: int,
    kompetenz_id: str,
    wording: CompetenceWording | None,
    ignore: BlockRef | None = None,
) -> AliasProblem | None:
    """Prüft eine Alias-Eingabe mit denselben Regeln wie die Operation; ``None`` = annehmbar.

    Geprüft wird der aufgelöste Text (`resolve_alias`) mit `block_text_error`.
    Nur wenn die Eingabe leer war (Zurücksetzen auf das Original der Seite) und
    das Original im Bereich schon steht, kommt ein Vorschlag hinzu – sonst hätte
    die Nutzerin den Text selbst getippt und soll ihn auch selbst ändern.

    Args:
        raw: Eingabe der Nutzerin.
        ladder: Aktuelle Leiter.
        side: Seite des Bausteins.
        rung: Sprosse des Bausteins.
        kompetenz_id: ID des Bausteins.
        wording: Formulierung aus dem Netz oder ``None``.
        ignore: Baustein, der beim Eindeutigkeitsvergleich nicht zählt (der umbenannte selbst).
    """
    text = resolve_alias(raw, kompetenz_id, wording, side)
    original = side_original(wording, side)
    error = block_text_error(text, ladder, side=side, rung=rung, ignore=ignore)
    if error is None:
        return None
    if str(raw).strip() or not original:
        return AliasProblem(error)
    suggestion = _free_copy(original, ladder, side, rung, ignore)
    if suggestion is None:
        return AliasProblem(error)
    return AliasProblem(f"{error} Vorschlag eingesetzt – Enter übernimmt ihn.", suggestion)


@dataclass(frozen=True)
class CopiedBlock:
    """Ein kopierter Baustein, wie er über Seiten und Leitern hinweg eingefügt wird (Strg+C/Strg+V).

    Bei Netz-Bausteinen reist der **Alias-Zustand**, nicht der Seitentext: Ohne
    Alias erscheint auf der Zielseite deren Variante (ein Lernziel wird in der
    Kompetenzspalte zur Satzform und umgekehrt), ein Alias bleibt wörtlich. Die
    Formulierung reist mit, weil die Zielleiter die Kompetenz evtl. noch nicht
    enthält.

    Attributes:
        block: Kopierter Baustein (sichtbarer Text, ggf. Kompetenz-ID).
        wording: Formulierung eines Netz-Bausteins oder ``None`` (eigener Baustein, Netz unbekannt).
        alias: Alias auf der Quellseite (`CompetenceWording.alias_on`); ``None`` = ohne Alias.
    """

    block: LadderBlock
    wording: CompetenceWording | None
    alias: str | None

    @classmethod
    def of(cls, block: LadderBlock, side: LadderSide, wording: CompetenceWording | None) -> CopiedBlock:
        """Kopie von *block* auf *side*; ohne bekannte Formulierung gilt der Text als Alias (bleibt wörtlich)."""
        alias = wording.alias_on(block.text, side) if wording is not None else block.text
        return cls(block, wording, alias)

    def text_for(self, side: LadderSide) -> str:
        """Vorbelegung beim Einfügen auf *side*: auf Netz-Seiten `CompetenceWording.text_on`, sonst der Text."""
        if self.wording is not None and SIDE_RULES[side].network:
            return self.wording.text_on(side, self.alias)
        return self.block.text


def shows_original(block: LadderBlock, wording: CompetenceWording | None, side: LadderSide) -> bool:
    """Ob unter einem Baustein auf *side* sein Original angezeigt wird: Netz-Baustein mit Alias.

    Ob ein Alias vorliegt, entscheidet allein `CompetenceWording.alias_on`
    (exakter Vergleich mit dem Original der Seite). Ohne bekannte Formulierung
    wird nichts angezeigt.
    """
    return block.is_network and wording is not None and wording.alias_on(block.text, side) is not None
