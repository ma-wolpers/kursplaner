"""Formulierung einer Netz-Kompetenz: einzige Stelle der Regel „Alias = Abweichung vom Seiten-Original“ (§37).

Eine Kompetenz aus dem Netz hat zwei sprachliche Varianten (Schema-Invariante 18):
den **Titel** in Satzform („stellen Brüche dar“ – passt hinter „Die SuS …“) und den
**Infinitiv** aus ``titel_infinitiv`` („Brüche darstellen“ – passt hinter „Die SuS
können …“/„Ich kann …“). Welche Variante eine Leiter-Seite trägt, steht allein in
`sequence_ladder.SIDE_RULES` (Lernziele links: Infinitiv, Kompetenzen rechts: Titel).

Daraus folgt alles Weitere, ohne Sonderfälle:

- Das **Original** eines Netz-Bausteins ist die Variante *seiner* Seite (`for_side`).
- Ein Baustein trägt **keinen Alias**, wenn sein Text exakt diesem Original gleicht;
  jede andere Formulierung – auch die Variante der anderen Seite – ist ein Alias
  (`alias_on`). So bleibt eine falsche Variante sichtbar, statt legitimiert zu werden.
- Beim **Kopieren** über Seiten reist der Alias-Zustand, nicht der Text: ohne Alias
  erscheint auf der Zielseite deren Variante, ein Alias bleibt wörtlich (`text_on`).

Alle Texte sind wie beim Speichern normalisiert (`network_block_text`), damit der
Primärschlüssel eines Bausteins den Rundweg durch die Datei unverändert übersteht.
"""

from __future__ import annotations

from dataclasses import dataclass

from kursplaner.core.domain.kompetenzgraph_node import KompetenzNode
from kursplaner.core.domain.sequence_ladder import SIDE_RULES, LadderSide, NetworkWording
from kursplaner.core.domain.sequence_ladder_entries import network_block_text


@dataclass(frozen=True)
class CompetenceWording:
    """Beide sprachlichen Varianten einer Netz-Kompetenz (unnormalisiert, wie im Netz).

    Attributes:
        kompetenz_id: ID der Kompetenz (bestimmt die Normalisierung).
        title: Satzform (H1-Titel des Netzknotens).
        infinitive: Lernziel-Form (``titel_infinitiv``, Rückfall Titel – `KompetenzNode.infinitive_title`).
    """

    kompetenz_id: str
    title: str
    infinitive: str

    def for_side(self, side: LadderSide) -> str:
        """Normalisiertes Original auf *side*: die Variante, die `SIDE_RULES` für die Seite festlegt.

        Raises:
            ValueError: *side* nimmt keine Netz-Bausteine auf (Material).

        Example::

            wording.for_side(LadderSide.INHALT)    # -> "Brüche darstellen"
            wording.for_side(LadderSide.PROZESS)   # -> "stellen Brüche dar"
        """
        variant = SIDE_RULES[side].wording
        if variant is None:
            raise ValueError(f"Seite {side.value} nimmt keine Netz-Bausteine auf.")
        text = self.infinitive if variant is NetworkWording.INFINITIVE else self.title
        return network_block_text(self.kompetenz_id, text)

    def alias_on(self, text: str, side: LadderSide) -> str | None:
        """Alias eines Bausteins mit *text* auf *side*: ``None`` = exakt das Original der Seite.

        Verglichen wird exakt (auch Groß-/Kleinschreibung), weil jede sichtbare
        Abweichung eine Bearbeitung ist – auch die Variante der anderen Seite.
        """
        return None if text == self.for_side(side) else text

    def text_on(self, side: LadderSide, alias: str | None) -> str:
        """Text eines Bausteins auf *side*: sein Alias oder, ohne Alias, das Original der Seite."""
        return alias if alias else self.for_side(side)


def wording_of(node: KompetenzNode) -> CompetenceWording:
    """Formulierung eines Netzknotens (einzige Übersetzung Knoten → `CompetenceWording`)."""
    return CompetenceWording(node.id, node.title, node.infinitive_title)
