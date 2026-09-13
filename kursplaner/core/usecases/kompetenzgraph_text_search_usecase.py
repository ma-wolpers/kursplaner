from __future__ import annotations

import re
from pathlib import Path

from kursplaner.core.domain.kompetenzgraph_filter import KompetenzGraphFilter
from kursplaner.core.domain.kompetenzgraph_mapping import BodySections, split_kompetenz_body_sections
from kursplaner.core.domain.kompetenzgraph_node import KompetenzNode
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot
from kursplaner.core.usecases.kompetenzgraph_load_body_usecase import LoadKompetenzNodeBodyUseCase

_EMPTY_SECTIONS = BodySections(beispiel_text="", rest_text="")


class KompetenzTextSearchIndex:
    """Pro Dialog-Sitzung lebender, mtime-basierter Cache für `BodySections`.

    Wird ausschließlich auf Klick des "Suchen"-Buttons konsultiert, nie
    live beim Tippen -- siehe Implementierungsplan, Teil B. Liest Bodies
    ausschließlich über das bestehende `LoadKompetenzNodeBodyUseCase` (die
    einzige Markdown-Lesequelle für Kompetenz-Dateien); tastet die
    "Lazy Body"-Entscheidung (KompetenzNode/kompetenzgraph_repository_cache.py
    halten den Body nie eager) nicht an -- der Cache hier lebt ausschließlich
    im Arbeitsspeicher dieser einen Dialog-Instanz und wird nirgends
    persistiert.

    Freshness über `mtime_ns`: ändert sich eine Datei zwischen zwei
    "Suchen"-Klicks derselben Dialog-Sitzung, wird sie beim nächsten Klick
    automatisch neu gelesen, ohne dass unveränderte Dateien erneut
    angefasst werden.
    """

    def __init__(self, load_body_usecase: LoadKompetenzNodeBodyUseCase | None):
        self._load_body_usecase = load_body_usecase
        self._cache: dict[Path, tuple[int, BodySections]] = {}

    def get_sections(self, node: KompetenzNode) -> BodySections:
        """Liefert die `BodySections` eines Knotens, bei Bedarf frisch von der Platte gelesen."""
        if self._load_body_usecase is None:
            return _EMPTY_SECTIONS

        path = node.source.path
        try:
            mtime_ns = path.stat().st_mtime_ns
        except OSError:
            return _EMPTY_SECTIONS

        cached = self._cache.get(path)
        if cached is not None and cached[0] == mtime_ns:
            return cached[1]

        body = self._load_body_usecase.execute(path)
        sections = split_kompetenz_body_sections(body)
        self._cache[path] = (mtime_ns, sections)
        return sections


def compute_text_search_matches(
    snapshot: KompetenzGraphSnapshot,
    candidate_ids: frozenset[str],
    filter: KompetenzGraphFilter,
    text_search_index: KompetenzTextSearchIndex,
) -> frozenset[str]:
    """Berechnet die Knoten-IDs aus `candidate_ids`, die den aktuellen Textsuchbegriff erfüllen.

    Wird ausschließlich bei einem "Suchen"-Klick aufgerufen, mit einem zu
    diesem Zeitpunkt bereits als gültig garantierten `filter.text_query`
    (Kompilierung/Validierung liegt beim Aufrufer, siehe
    `kompetenzgraph_dialog.py::_on_text_search_triggered`). `candidate_ids`
    ist die bereits strukturell vorgefilterte Menge (`compute_visible_node_ids`)
    -- Body-Dateien werden nur für diese Kandidaten und nur bei aktivem
    Beispiel-/Rest-Toggle gelesen, nie für den gesamten Snapshot.
    """
    pattern = re.compile(filter.text_query)
    matched: set[str] = set()
    for node_id in candidate_ids:
        node = snapshot.nodes.get(node_id)
        if node is None:
            continue
        if filter.text_search_kc_verweis and any(pattern.search(entry.kc_verweis) for entry in node.kc_zuordnung):
            matched.add(node_id)
            continue
        if filter.text_search_titel and pattern.search(node.title):
            matched.add(node_id)
            continue
        if filter.text_search_beispiel or filter.text_search_rest:
            sections = text_search_index.get_sections(node)
            if filter.text_search_beispiel and pattern.search(sections.beispiel_text):
                matched.add(node_id)
                continue
            if filter.text_search_rest and pattern.search(sections.rest_text):
                matched.add(node_id)
                continue
    return frozenset(matched)
