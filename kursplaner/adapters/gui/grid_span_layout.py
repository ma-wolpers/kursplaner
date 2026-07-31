"""Reine Grid-Spalten-Gruppierung für zusammenhängende Zellen (columnspan).

⚠ Übergangslösung: Dieser Baustein ist bewusst Tk-frei und ohne Kursplaner-
spezifische Importe geschnitten, weil er eigentlich in `bw-gui` als generische
Spanning-Grid-Abstraktion gehört. Da `bw-gui` aktuell grundlegend umgebaut
wird, lebt er vorübergehend hier. Nach Abschluss der bw-gui-Refaktorierung
muss geprüft werden, ob/wie er dorthin verschoben wird (siehe Plan-Notiz
"OFFENER NACHARBEITS-SCHRITT: bw-gui-Migration steht noch aus").
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class GridSpanSegment:
    """Ein zusammenhängender Block von Tk-Grid-Spalten.

    Attributes:
        start_column: Erste Tk-Grid-Spaltennummer des Blocks.
        column_span: Anzahl der Spalten, die der Block umfasst (für `columnspan`).
    """

    start_column: int
    column_span: int


def compute_contiguous_spans(grid_columns: Sequence[int]) -> list[GridSpanSegment]:
    """Gruppiert Grid-Spaltennummern in maximale, zusammenhängende Blöcke.

    Wird genutzt, um eine fachliche Sequenz (eine Kette benachbarter Einheiten)
    auf ein oder mehrere spannende Grid-Widgets abzubilden: sind alle
    zugehörigen Tages-Spalten aktuell sichtbar und lückenlos benachbart, ergibt
    sich genau ein Segment; ist eine Zwischenspalte durch eine
    Sichtbarkeits-Einstellung ausgeblendet, entstehen entsprechend mehrere
    Segmente.

    Args:
        grid_columns: Tk-Grid-Spaltennummern der sichtbaren Mitglieder einer
            Sequenz, in beliebiger Reihenfolge.

    Returns:
        Die Segmente in aufsteigender Spaltenreihenfolge. Leere Eingabe liefert
        eine leere Liste.
    """
    sorted_columns = sorted(set(grid_columns))
    if not sorted_columns:
        return []

    segments: list[GridSpanSegment] = []
    segment_start = sorted_columns[0]
    previous = sorted_columns[0]

    for column in sorted_columns[1:]:
        if column == previous + 1:
            previous = column
            continue
        segments.append(GridSpanSegment(start_column=segment_start, column_span=previous - segment_start + 1))
        segment_start = column
        previous = column

    segments.append(GridSpanSegment(start_column=segment_start, column_span=previous - segment_start + 1))
    return segments
