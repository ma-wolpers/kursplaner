"""Eintrag ↔ Baustein: einzige Übersetzung zwischen gespeichertem Text und Leiter-Baustein (§37).

Ein Eintrag ist der Text, wie er in einer Einheit (``Stundenziel``, ein
``Teilziele``-/``Kompetenzen``-/``Material``-Listeneintrag) oder in der Ablage
der Sequenzdatei steht. Dieselben zwei Funktionen gelten für beide Speicherorte:

- Auf einer Netz-Seite (`SIDE_RULES`, Inhalt/Prozess) ist ein **Netz-Baustein**
  genau ein Wiki-Link mit Alias, ``[[ID|Titel]]`` (Ziel = Kompetenz-ID, Alias = Titel).
- Alles andere ist ein **eigener Baustein**, dessen Text der Eintrag selbst ist
  (auch ein Link ohne Alias wie ``[[Notiz]]`` – er bleibt so erhalten). Material
  ist immer ein eigener Baustein: ``[[Material/AB.pdf|AB 1]]`` bleibt wörtlich
  stehen und wird nie zur „Kompetenz Material/AB.pdf“.

Links erkennen, bauen und lesen ausschließlich `wiki_links`.
"""

from __future__ import annotations

from kursplaner.core.domain.sequence_ladder import SIDE_RULES, LadderBlock, LadderSide
from kursplaner.core.domain.wiki_links import build_wiki_link, whole_wiki_link, wiki_link_display_text


def block_from_entry(entry: str, side: LadderSide) -> LadderBlock:
    """Baustein zu einem gespeicherten Eintrag auf *side* (Netz-Baustein nur bei ``[[ID|Titel]]`` einer Netz-Seite)."""
    text = str(entry).strip()
    parts = whole_wiki_link(text) if SIDE_RULES[side].network else None
    if parts is not None and parts[0] and parts[1]:
        return LadderBlock(parts[1], parts[0])
    return LadderBlock(text)


def block_display_text(block: LadderBlock, side: LadderSide) -> str:
    """Anzeigetext eines Bausteins: Netz-Seiten zeigen den Text, Material den Link-Anzeigenamen.

    Material nutzt dieselbe Regel wie die Material-Zelle im Grid (`wiki_link_display_text`:
    ``[[Material/AB.pdf|AB 1]]`` → ``AB 1``); der Baustein-Text (Schlüssel) bleibt der Eintrag.
    """
    return block.text if SIDE_RULES[side].network else wiki_link_display_text(block.text)


def entry_from_block(block: LadderBlock) -> str:
    """Gespeicherter Eintrag eines Bausteins (Umkehrung von `block_from_entry`)."""
    if block.kompetenz_id is not None:
        return build_wiki_link(block.kompetenz_id, block.text)
    return block.text


def network_block_text(kompetenz_id: str, title: str) -> str:
    """Text, den ein Netz-Baustein nach dem Rundweg durch die Datei trägt.

    Baut den Link wie beim Schreiben und liest den Alias wie beim Lesen; so ist
    der Primärschlüssel vor und nach dem Speichern identisch, auch wenn der
    Titel Zeichen enthält, die `build_wiki_link` normalisiert.
    """
    return wiki_link_display_text(build_wiki_link(kompetenz_id, title or kompetenz_id))
