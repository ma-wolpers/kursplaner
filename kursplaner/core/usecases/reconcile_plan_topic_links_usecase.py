"""Leitet den Sequenz-Link der Plantabelle (Spalte ``Thema/Ausfall``) beim Kursladen aus dem YAML ab.

Die eine Quelle der Sequenzzugehörigkeit einer angelegten Einheit ist ihr
YAML-Feld ``Oberthema``. Die Zelle ``Thema/Ausfall`` ihrer Planzeile spiegelt
es als ``[[Gruppe Oberthema]]`` bzw. ``LZK [[Gruppe Oberthema]]`` – damit die
Plandatei in Obsidian auf die Sequenznotiz verweist.

Früher schrieb nur „Stunde planen“ diesen Spiegel. Die Sequenzleiter
(Sprosse zuordnen), das Speichern der Oberthema-Zelle einer angelegten Einheit
und Bearbeitungen direkt in Obsidian ließen ihn veralten: Der Kursplaner zeigte
die Einheit korrekt in der Sequenz (er liest das YAML), die Plandatei trug aber
keinen oder einen alten Link. Statt jeden Schreibweg zu verpflichten (was
Obsidian-Bearbeitungen nie abdecken könnte), gleicht dieser Use Case den Spiegel
an genau einer Stelle ab: beim Kursladen, im selben Hook wie die
Oberthema-Migration und das KH-Link-Cleanup (`overview_controller.load_selected_table`).

Abgeglichen werden nur Zeilen mit gültiger Einheitendatei, deren Zelle leer ist
oder genau einen Sequenz-Link trägt. Ausfall-/Ferien-Marker, Alt-Marker wie
``HO …`` und sonstiger freier Text bleiben unberührt. Die Ableitung selbst ist
die vorhandene `sync_thema_ausfall_to_plan_row` – eine Regel für alle Wege
(Ausfall-Einheiten und ungültige Oberthemen lässt sie bereits unverändert).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from kursplaner.core.domain.day_column import DayColumn
from kursplaner.core.domain.plan_table import COLUMN_THEMA_AUSFALL, PlanTableData, extract_plan_oberthema
from kursplaner.core.ports.repositories import PlanRepository


@dataclass(frozen=True)
class ReconcilePlanTopicLinksResult:
    """Ergebnis eines Abgleichlaufs.

    Args:
        changed_rows: Planzeilen, deren ``Thema/Ausfall``-Zelle neu geschrieben
            wurde (leer, wenn alles schon stimmte – dann wurde nichts gespeichert).
    """

    changed_rows: tuple[int, ...]


class ReconcilePlanTopicLinksUseCase:
    """Bringt die Sequenz-Links der Plantabelle mit dem ``Oberthema`` der Einheiten in Deckung."""

    def __init__(self, *, plan_repo: PlanRepository) -> None:
        """Initialisiert den Use Case mit dem Plan-Repository-Port.

        Args:
            plan_repo: Liefert die eine Ableitungsregel
                (`sync_thema_ausfall_to_plan_row`) und speichert die Tabelle.
        """
        self._plan_repo = plan_repo

    @staticmethod
    def is_derived_cell(cell: str, group_name: str) -> bool:
        """``True``, wenn die Zelle nur den abgeleiteten Sequenz-Link trägt (oder leer ist).

        Nur solche Zellen darf der Abgleich überschreiben. Ein Ausfall-/Ferien-
        Marker gehört zum Termin der Zeile, ein Alt-Marker wie ``HO …`` oder
        freier Text ist eine bewusste Eintragung – beides bleibt stehen.
        Erkannt wird der Link mit derselben Funktion, die ihn beim Lesen als
        Oberthema-Fallback entschlüsselt (`extract_plan_oberthema`).

        Example::

            is_derived_cell("", "[[ge5]]")                         # -> True
            is_derived_cell("[[ge5 Dezimalbrüche]]", "[[ge5]]")    # -> True
            is_derived_cell("LZK [[ge5 Dezimalbrüche]]", "ge5")    # -> True
            is_derived_cell("X Wandertag", "ge5")                  # -> False
            is_derived_cell("HO ge5 Besuch", "ge5")                # -> False
        """
        text = str(cell or "").strip()
        return not text or bool(extract_plan_oberthema(text, group_name))

    def execute(self, *, table: PlanTableData, day_columns: Sequence[DayColumn]) -> ReconcilePlanTopicLinksResult:
        """Gleicht alle Zeilen mit Einheitendatei ab und speichert die Tabelle nur bei Änderungen.

        Die YAML-Daten stammen aus den bereits geladenen ``day_columns``
        (kein zusätzliches Lesen von der Platte). Gespeichert wird höchstens
        einmal und nur, wenn sich mindestens eine Zelle geändert hat – ein
        unveränderter Kurs bleibt byte-genau, das Öffnen erzeugt keine
        Schreibvorgänge im synchronisierten Vault.

        Args:
            table: Geladene Planungstabelle (wird bei Abweichung in-place geändert).
            day_columns: Vollständige, unprojizierte Tagesliste desselben Ladevorgangs
                (``row_index`` muss zu ``table.rows`` passen).

        Returns:
            Die geänderten Zeilen; der Aufrufer lädt den Kurs dann neu, damit
            die Tagesspalten die neuen Zellwerte tragen.
        """
        if table.column_index_optional(COLUMN_THEMA_AUSFALL) is None:
            return ReconcilePlanTopicLinksResult(changed_rows=())
        group_name = str(table.metadata.get("Lerngruppe", ""))
        changed: list[int] = []
        for day in day_columns:
            row_index = day.row_index
            if not day.yaml or not day.is_valid_unterricht_file or not 0 <= row_index < len(table.rows):
                continue
            before = table.thema_ausfall(row_index)
            if not self.is_derived_cell(before, group_name):
                continue
            self._plan_repo.sync_thema_ausfall_to_plan_row(
                table, row_index, yaml_data=dict(day.yaml), group_name=group_name
            )
            if table.thema_ausfall(row_index) != before:
                changed.append(row_index)
        if changed:
            self._plan_repo.save_plan_table(table)
        return ReconcilePlanTopicLinksResult(changed_rows=tuple(changed))
