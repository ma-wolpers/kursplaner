"""Port-Vertragstypen der Sequenzplan-Exporttabelle.

Die Exporttabelle wird von Use Cases (`sequence_export_table.export_row_cells`)
medienneutral zusammengestellt und von der Infrastruktur dargestellt
(Markdown-Tabelle in der Sequenzdatei, Markdown-/PDF-Export). Der Zelltyp ist
damit ein stabiler Vertrag zwischen Use Cases und Infrastruktur und liegt —
wie es `core/ports/README.md` für solche Verträge vorsieht — hier in
``core/ports``: Ports importieren nicht aus ``core/usecases``, und der Typ ist
Darstellungsform, keine Fachlogik (gehört also nicht ins Domain-Modell).
"""

from __future__ import annotations

ExportCell = tuple[str, ...]
"""Eine Tabellenzelle als Folge von Zeilen (medienneutral; jedes Medium verbindet selbst).

Bewusst ein Tupel und kein ``str``: Ein String ist selbst eine Sequenz aus
Zeichen und würde sonst unbemerkt zeichenweise als „Zeilen“ dargestellt.
"""

ExportTableRow = tuple[ExportCell, ...]
"""Eine Tabellenzeile: eine `ExportCell` je Spalte, Reihenfolge wie `EXPORT_TABLE_HEADERS`."""
