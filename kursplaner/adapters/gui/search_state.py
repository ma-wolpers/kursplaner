from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class SearchOverlayState:
    """Veränderlicher Zustand der Strg+F-Einheitensuche im Hauptfenster-Grid.

    Bewusst NICHT `frozen` -- reiner, pro Hauptfenster gehaltener GUI-
    Zustand, den `search_controller.py` bei jeder Interaktion direkt
    mutiert. `is_active` ist die alleinige Quelle, ob `SelectionLayerStack`
    Enter/Escape/Umschalt+Enter an die Such-Ebene statt an die reguläre
    Kursauswahl-/Spalten-/Zell-/Editier-Kette weiterleitet (siehe
    `selection_layer_stack.py`).

    Attributes:
        is_active: Ob das Suchfeld aktuell eingeblendet ist.
        query: Roher, IMMER aktueller Suchtext (auch waehrend er gerade ungueltig ist) --
            getrennt von `pattern`/`matches`, damit das Statuslabel ehrlich den aktuellen
            Tippzustand zeigen kann, ohne den zuletzt gueltigen Trefferzustand zu verlieren.
        pattern: Zuletzt ERFOLGREICH kompiliertes Muster, oder `None` ohne (gültige) Suche.
            Bleibt bei ungueltiger Eingabe unveraendert auf dem vorherigen Wert stehen.
        is_query_invalid: Ob der AKTUELLE `query`-Text ein ungueltiges, nicht-leeres Regex
            ist. Getrennt von `pattern is None` gehalten, weil `pattern` bei ungueltiger
            Eingabe bewusst NICHT zurueckgesetzt wird (siehe oben) -- ohne dieses Feld gaebe
            es keine Moeglichkeit, "aktuell ungueltig" von "es gab noch nie ein gueltiges
            Muster" zu unterscheiden.
        matches: Sortierte `day_index`-Werte aller aktuell passenden
            Einheiten (bezogen auf `app.day_columns`, nicht `raw_day_columns`).
        current_match_index: Position in `matches`, auf die zuletzt gesprungen
            wurde, oder `None` vor dem ersten Sprung.
    """

    is_active: bool = False
    query: str = ""
    pattern: re.Pattern[str] | None = None
    is_query_invalid: bool = False
    matches: list[int] = field(default_factory=list)
    current_match_index: int | None = None
