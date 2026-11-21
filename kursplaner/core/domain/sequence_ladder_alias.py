"""Alias eines Netz-Bausteins: einzige Stelle der Bearbeitungsregeln (§37).

Ein Netz-Baustein wird als ``[[ID|Alias]]`` gespeichert. Der Alias ist frei
bearbeitbar; der Originaltitel wird über die ID im Kompetenznetz nachgeschlagen
(`CompetenceOriginals`) und nie in der Leiter gespeichert – so bleibt das Netz
die einzige Quelle des Originals.

Regeln:

- Eingegebener Text wird wie beim Import normalisiert (`network_block_text`),
  damit der Primärschlüssel vor und nach dem Speichern derselbe ist.
- Eine **leere Eingabe** setzt den Alias auf den Originaltitel zurück.
- Kollidiert dieses Original im Eindeutigkeitsbereich mit einem anderen
  Baustein, wird ein freier Vorschlag „<Original> (Kopie)“ gemacht
  (`alias_problem`); der Editor setzt ihn ins Feld.
- Das Original wird nur angezeigt, wenn der Alias davon abweicht (`shows_original`).

Diese Funktionen kennen keine GUI; der Controller übersetzt das Ergebnis von
`alias_problem` in die Editor-Rückmeldung.
"""

from __future__ import annotations

from dataclasses import dataclass

from kursplaner.core.domain.sequence_ladder import BlockRef, LadderBlock, LadderSide, SequenceLadder, block_text_error
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


def resolve_alias(raw: str, kompetenz_id: str, original: str | None) -> str:
    """Text, den ein Netz-Baustein nach der Eingabe *raw* trägt.

    Args:
        raw: Eingabe der Nutzerin (ungetrimmt).
        kompetenz_id: ID des Bausteins (bestimmt die Normalisierung).
        original: Normalisierter Originaltitel aus dem Netz oder ``None``,
            wenn er nicht bekannt ist (ID nicht im Netz, Netz nicht geladen).

    Returns:
        Bei leerer Eingabe das Original (ohne bekanntes Original ``""``, was
        `block_text_error` als fehlende Beschreibung meldet), sonst die
        normalisierte Eingabe.

    Example::

        resolve_alias("  ", "K-31", "stellen Brüche dar")   # -> "stellen Brüche dar"
        resolve_alias("Brüche zeigen", "K-31", None)          # -> "Brüche zeigen"
    """
    text = str(raw).strip()
    if not text:
        return original or ""
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
    original: str | None,
    ignore: BlockRef | None = None,
) -> AliasProblem | None:
    """Prüft eine Alias-Eingabe mit denselben Regeln wie die Operation; ``None`` = annehmbar.

    Geprüft wird der aufgelöste Text (`resolve_alias`) mit `block_text_error`.
    Nur wenn die Eingabe leer war (Zurücksetzen auf das Original) und das
    Original im Bereich schon steht, kommt ein Vorschlag hinzu – sonst hätte
    die Nutzerin den Text selbst getippt und soll ihn auch selbst ändern.

    Args:
        raw: Eingabe der Nutzerin.
        ladder: Aktuelle Leiter.
        side: Seite des Bausteins.
        rung: Sprosse des Bausteins.
        kompetenz_id: ID des Bausteins.
        original: Normalisierter Originaltitel oder ``None``.
        ignore: Baustein, der beim Eindeutigkeitsvergleich nicht zählt (der umbenannte selbst).
    """
    text = resolve_alias(raw, kompetenz_id, original)
    error = block_text_error(text, ladder, side=side, rung=rung, ignore=ignore)
    if error is None:
        return None
    if str(raw).strip() or not original:
        return AliasProblem(error)
    suggestion = _free_copy(original, ladder, side, rung, ignore)
    if suggestion is None:
        return AliasProblem(error)
    return AliasProblem(f"{error} Vorschlag eingesetzt – Enter übernimmt ihn.", suggestion)


def shows_original(block: LadderBlock, original: str | None) -> bool:
    """Ob unter einem Baustein der Originaltitel angezeigt wird: Netz-Baustein mit abweichendem Alias.

    Verglichen wird exakt (auch Groß-/Kleinschreibung), weil jede sichtbare
    Änderung eine Bearbeitung ist. Ohne bekanntes Original wird nichts angezeigt.
    """
    return block.is_network and bool(original) and block.text != original
