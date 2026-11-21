"""Einheiten-Nutzlast einer Planzeile – der **einzige** Weg, eine Einheit in eine andere Zeile zu bewegen.

Eine Planzeile hat zwei Teile:

- den **Termin** (Datum und ein Ausfall-/Ferien-Marker in ``Thema/Ausfall``) – er
  gehört zur Zeile und bewegt sich nie;
- die **Nutzlast** der Einheit: der Link in ``Inhalt`` und – sofern dort kein
  Termin-Marker steht – die Zelle ``Thema/Ausfall`` (``[[Gruppe Oberthema]]``,
  ``LZK [[…]]``, ``HO …`` oder das Oberthema einer noch nicht angelegten Einheit).

Früher verschoben Verschieben und Spaltentausch nur ``Inhalt``; die Thema-Zelle
blieb stehen und gehörte danach zur falschen Einheit. Wer eine Einheit bewegt,
liest und schreibt deshalb nur noch `RowPayload` über `PayloadColumns`. Zwei
Invarianten machen den Versatz unmöglich:

1. Link und Thema-Zelle wandern immer gemeinsam (`read`/`write`).
2. Ein Termin-Marker wird beim Schreiben nie überschrieben und beim Lesen nie
   mitgenommen. Wer ihn bewusst entfernen will (Rücknahme eines Ausfalls),
   ruft `clear_slot_marker`.

`shift_moves` ist die reine Planung des Verschiebens „ab Zeile X um einen Termin
nach hinten“: Ausfall-/Ferienzeilen und feste Zeilen (LZK) werden übersprungen,
Ziel ist der erste freie Termin. Vorschau (Dialogtext) und Ausführung nutzen
dieselbe Funktion.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from kursplaner.core.domain.content_markers import is_ausfall_marker, resolve_row_cancel_state
from kursplaner.core.domain.plan_table import COLUMN_INHALT, COLUMN_THEMA_AUSFALL, PlanTableData

Move = tuple[int, int]
"""``(Quellzeile, Zielzeile)`` einer Nutzlast."""


@dataclass(frozen=True)
class RowPayload:
    """Der an die Einheit gebundene Teil einer Planzeile (Link + Thema-Zelle)."""

    inhalt: str = ""
    thema: str = ""

    @property
    def is_empty(self) -> bool:
        """``True``, wenn die Zeile keine Einheit trägt (weder Link noch Thema)."""
        return not self.inhalt.strip() and not self.thema.strip()


def _cell(row: Sequence[str], index: int | None) -> str:
    return str(row[index]) if index is not None and index < len(row) else ""


@dataclass(frozen=True)
class PayloadColumns:
    """Spaltenpositionen der Nutzlast in einer Plantabelle (``thema`` fehlt in Alt-Tabellen)."""

    inhalt: int
    thema: int | None

    @classmethod
    def of(cls, table: PlanTableData) -> PayloadColumns:
        """Spalten der Tabelle (``Inhalt`` ist Pflicht; Suche über `PlanTableData.column_index`)."""
        return cls(table.column_index(COLUMN_INHALT), table.column_index_optional(COLUMN_THEMA_AUSFALL))

    def has_slot_marker(self, row: Sequence[str]) -> bool:
        """``True``, wenn ``Thema/Ausfall`` einen Ausfall-/Ferien-Marker (Termin) trägt."""
        return is_ausfall_marker(_cell(row, self.thema))

    def read(self, row: Sequence[str]) -> RowPayload:
        """Nutzlast der Zeile; ein Termin-Marker gehört nicht dazu."""
        thema = "" if self.has_slot_marker(row) else _cell(row, self.thema)
        return RowPayload(_cell(row, self.inhalt), thema)

    def write(self, row: list[str], payload: RowPayload) -> None:
        """Setzt die Nutzlast; ein Termin-Marker der Zeile bleibt stehen."""
        if self.inhalt < len(row):
            row[self.inhalt] = payload.inhalt
        if self.thema is not None and self.thema < len(row) and not self.has_slot_marker(row):
            row[self.thema] = payload.thema

    def clear(self, row: list[str]) -> None:
        """Entfernt die Nutzlast (Termin-Marker bleibt)."""
        self.write(row, RowPayload())

    def clear_slot_marker(self, row: list[str]) -> None:
        """Entfernt einen Termin-Marker bewusst (z. B. Rücknahme eines Ausfalls)."""
        if self.thema is not None and self.thema < len(row) and self.has_slot_marker(row):
            row[self.thema] = ""


def swap_payloads(table: PlanTableData, row_a: int, row_b: int) -> None:
    """Tauscht die Nutzlasten zweier Zeilen (Termine bleiben)."""
    columns, rows = PayloadColumns.of(table), table.rows
    payload_a, payload_b = columns.read(rows[row_a]), columns.read(rows[row_b])
    columns.write(rows[row_a], payload_b)
    columns.write(rows[row_b], payload_a)


def shift_moves(
    table: PlanTableData,
    start_row: int,
    is_fixed: Callable[[int], bool] = lambda _row: False,
) -> tuple[Move, ...] | None:
    """Plant „ab *start_row* alles um einen Termin nach hinten bis zum ersten freien Termin“.

    Args:
        table: Plantabelle (wird nicht verändert).
        start_row: Zeile, die frei werden soll. Sie selbst wird auch dann
            verschoben, wenn sie fest wäre (der Nutzer hat sie ausdrücklich gewählt).
        is_fixed: Feste Zeilen (LZK) – bleiben stehen und werden übersprungen.

    Returns:
        Die Bewegungen in Ausführungsreihenfolge (hinten zuerst; leer, wenn
        *start_row* schon frei ist) oder ``None``, wenn *start_row* ein Ausfall
        ist oder bis zum Tabellenende kein freier Termin kommt.
    """
    columns, rows = PayloadColumns.of(table), table.rows
    slots = [
        index
        for index, row in enumerate(rows)
        if not resolve_row_cancel_state(table.headers, row) and (index == start_row or not is_fixed(index))
    ]
    if start_row not in slots:
        return None
    start = slots.index(start_row)
    free = next((pos for pos in range(start, len(slots)) if columns.read(rows[slots[pos]]).is_empty), None)
    if free is None:
        return None
    return tuple((slots[pos - 1], slots[pos]) for pos in range(free, start, -1))


def apply_moves(table: PlanTableData, moves: Sequence[Move], start_row: int) -> None:
    """Führt `shift_moves` aus und leert danach *start_row*."""
    columns, rows = PayloadColumns.of(table), table.rows
    for source, target in moves:
        columns.write(rows[target], columns.read(rows[source]))
    columns.clear(rows[start_row])
