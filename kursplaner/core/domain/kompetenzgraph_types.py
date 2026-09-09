from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ANFORDERUNG_BASIS = "basis"
ANFORDERUNG_WEITERFUEHREND_OPTIONAL = "weiterfuehrend-optional"
ANFORDERUNG_VALUES: frozenset[str] = frozenset({ANFORDERUNG_BASIS, ANFORDERUNG_WEITERFUEHREND_OPTIONAL})
"""Zulässige Werte für `kc_zuordnung[].anforderung` (siehe `_Schema.md`).

Bewusst binär, kein Sammelfeld für andere Eigenschaften -- ein Wert außerhalb
dieser Menge ist ein weicher Fehler (dieser `kc_zuordnung`-Eintrag wird
verworfen, siehe `kompetenzgraph_mapping.py`), kein harter Parse-Abbruch.
"""

STATUS_ENTWURF = "entwurf"
STATUS_GEPRUEFT = "geprüft"
STATUS_VALUES: frozenset[str] = frozenset({STATUS_ENTWURF, STATUS_GEPRUEFT})
"""Zulässige Werte für das top-level `status`-Feld einer Kompetenz-Datei.

Ein ungültiger Rohwert fällt beim Mapping weich auf `STATUS_ENTWURF` zurück
(siehe Fehlerklassifizierungs-Tabelle im Implementierungsplan) statt die
gesamte Datei zu verwerfen.
"""

EdgeKind = Literal["hierarchy", "prerequisite", "classification"]
"""Gemeinsame Vokabel für die drei fachlich unterschiedlichen Kantentypen im Kompetenznetz.

- ``"hierarchy"``: `oberkompetenzen` (Kind→Eltern, gespeichert) und die davon
  abgeleitete Rückkante `teilkompetenzen` (nie gespeichert, siehe
  `kompetenzgraph_snapshot_builder.py`).
- ``"prerequisite"``: `voraussetzungen` (Kind→Vorbedingung, gespeichert) und
  die abgeleitete Rückkante `weiterfuehrung`.
- ``"classification"``: `primarer_bereich`/`prozessbereiche` (Kompetenz→
  Bereichs-Hub). Reine Klassifikationsbeziehung, keine Hierarchie- oder
  Voraussetzungskante.

Diese Trennung ist strukturell bereits durch benannte Felder auf
`KompetenzNode` gegeben (siehe `kompetenzgraph_node.py`); `EdgeKind` macht sie
im Layout-/Fokus-/Kontext-/Renderer-Code explizit referenzierbar, statt
implizit über "welches Feld ist gerade gemeint" erraten zu werden. Code, der
Ancestor-/Descendant-/Kontext-Traversierung betreibt (`kompetenzgraph_view_mode.py`,
`kompetenzgraph_context.py`, `kompetenzgraph_focus.py`, `kompetenzgraph_layout.py`),
darf `"classification"`-Kanten dabei niemals folgen.
"""


@dataclass(frozen=True)
class SourceRef:
    """Physische Herkunft einer gescannten Vault-Datei -- reines Persistenz-/Cache-Metadatum.

    `SourceRef` beschreibt AUSSCHLIESSLICH, woher eine Kompetenz- oder
    Bereichs-Datei stammt (Pfad, Änderungszeitpunkt/-größe für die
    Cache-Invalidierung, sowie das Fach, aus dessen Ordner sie gescannt
    wurde). Es ist KEIN Bestandteil der fachlichen Identität einer
    Kompetenz -- diese ist ausschließlich die vault-weit eindeutige ID
    (der Dateiname ohne `.md`). Eine Kompetenzdatei hat genau eine
    physische Herkunft, kann aber von Kompetenzen beliebiger anderer
    Fächer referenziert werden: Wikilinks sind vault-weit über die ID
    auflösbar und fachunabhängig (siehe Kritische Modellentscheidung im
    Implementierungsplan).

    Attributes:
        path: Absoluter Pfad der Quelldatei im Vault.
        mtime_ns: `st_mtime_ns` der Quelldatei zum Zeitpunkt des Scans --
            zusammen mit `size` Grundlage der Cache-Invalidierung in
            `kompetenzgraph_repository.py` (niemals alleinige
            Wahrheitsquelle, siehe dortige Cache-Semantik-Invariante).
        size: `st_size` der Quelldatei zum Zeitpunkt des Scans.
        subject: Name des Fachordners, aus dem die Datei gescannt wurde
            (z. B. ``"Mathematik"``). Herkunftsmetadatum, kein fachliches
            Identitätsmerkmal der Kompetenz selbst.
    """

    path: Path
    mtime_ns: int
    size: int
    subject: str


@dataclass(frozen=True)
class KcZuordnungEintrag:
    """Ein einzelner Eintrag aus `kc_zuordnung` -- eine Bundesland/Schulform/Jahrgang-Zuordnung.

    Mehrere Einträge pro Kompetenz-Datei sind laut Schema zulässig (z. B.
    nach einem Merge mehrerer Kerncurricula-Formulierungen zu einer
    Kompetenz) und müssen von Filterlogik gemeinsam pro Eintrag geprüft
    werden -- siehe die Filter-Semantik-Invariante in
    `kompetenzgraph_filter.py` (Bundesland/Schulform/Niveau/Jahrgang/
    Anforderung dürfen nicht unabhängig voneinander über verschiedene
    Einträge desselben Knotens gemischt werden).

    Attributes:
        bundesland: Bundesland dieser Zuordnung, z. B. ``"Niedersachsen"``.
        schulform: Schulform dieser Zuordnung, z. B. ``"Gymnasium"``.
        niveau: Differenzierungsniveau, z. B. ``"eA"``/``"E"``/``"GK"``/
            ``"LK"``. Legitim leer/`None`, wenn nicht differenziert --
            das ist in den meisten realen Daten der Fall, kein Fehler.
        jahrgang: Jahrgangsstufe dieser Zuordnung, z. B. ``8``.
        anforderung: Muss einer von `ANFORDERUNG_VALUES` sein.
        kc_verweis: Wörtliches Zitat aus dem amtlichen Kerncurriculum, das
            zu genau dieser Zuordnung gehört. Darf laut Schema bewusst
            leer sein (z. B. wenn der Originaltext noch nicht
            nachgeschlagen wurde) -- kein Parse-Fehler.
    """

    bundesland: str | None
    schulform: str | None
    niveau: str | None
    jahrgang: int | None
    anforderung: str
    kc_verweis: str
