from __future__ import annotations

from kursplaner.adapters.gui.warning_banner import WarningBanner
from kursplaner.core.usecases.kompetenzgraph_load_usecase import KompetenzGraphLoadResult

_MAX_CYCLE_LINES = 5
_MAX_TITLE_LINES = 8


def duplicate_title_summary(load_result: KompetenzGraphLoadResult) -> str:
    """Einzige Formulierung der Titel-Duplikat-Meldung (Banner und Warnfenster beim Öffnen).

    Leerer Text, wenn alle Titel pro Fach eindeutig sind.
    """
    diagnostics = load_result.title_diagnostics
    if not diagnostics:
        return ""
    lines = [
        f"{d.subject}: „{d.title}“ ({', '.join(d.node_ids)})" + (f" – {d.hint}" if d.hint else "")
        for d in diagnostics[:_MAX_TITLE_LINES]
    ]
    remaining = len(diagnostics) - _MAX_TITLE_LINES
    suffix = f"\n(+{remaining} weitere)" if remaining > 0 else ""
    return (
        f"{len(diagnostics)} Kompetenz-Titel kommen in einem Fach mehrfach vor. Bitte zusammenführen oder "
        "die Titel unterscheidbar machen (Schema-Invariante 17) – in der Sequenzleiter ist der Titel der "
        "Name des Bausteins:\n" + "\n".join(lines) + suffix
    )


class KompetenzGraphDiagnosticsBanner:
    """Warnbanner für Zyklen-/Datei-/Duplicate-ID-Diagnosen -- rein informativ, blockiert nichts.

    Ein Zyklus ist ein Datenintegritätsproblem, aber kein Grund, den
    Graphen unbrauchbar zu machen (siehe `kompetenzgraph_dag.py`): dieses
    Banner macht gefundene Probleme sichtbar, der Graph selbst bleibt in
    jedem Fall vollständig aufgebaut und interaktiv.
    """

    def __init__(self, parent):
        """Baut das (zunächst verborgene) Banner auf (Darstellung: `WarningBanner`)."""
        self._banner = WarningBanner(parent, wraplength=900)

    def update(self, load_result: KompetenzGraphLoadResult) -> None:
        """Zeigt das Banner mit einer Zusammenfassung, oder verbirgt es, wenn es nichts zu melden gibt."""
        messages: list[str] = []

        if load_result.cycle_diagnostics:
            cycle_lines = []
            for diagnostic in load_result.cycle_diagnostics[:_MAX_CYCLE_LINES]:
                kind_label = "Oberkompetenzen" if diagnostic.edge_kind == "hierarchy" else "Voraussetzungen"
                cycle_lines.append(f"{kind_label}: {' → '.join(diagnostic.member_ids)}")
            remaining = len(load_result.cycle_diagnostics) - _MAX_CYCLE_LINES
            suffix = f" (+{remaining} weitere)" if remaining > 0 else ""
            messages.append("Zyklen gefunden -- " + "; ".join(cycle_lines) + suffix)

        if load_result.file_diagnostics:
            messages.append(
                f"{len(load_result.file_diagnostics)} Datei(en) mit Warnungen/Fehlern übersprungen oder eingeschränkt geladen."
            )

        if load_result.title_diagnostics:
            messages.append(f"{len(load_result.title_diagnostics)} doppelte Kompetenz-Titel (Details beim Öffnen).")

        duplicate_count = len(load_result.snapshot.duplicate_ids)
        if duplicate_count:
            messages.append(
                f"{duplicate_count} doppelt vergebene ID(s) gefunden -- jeweils eine Version wurde ignoriert."
            )

        self._banner.show(messages)
