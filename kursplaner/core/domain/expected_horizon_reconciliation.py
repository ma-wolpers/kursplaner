"""Fachlicher Abgleich eines neu erzeugten Kompetenzhorizonts mit einer bestehenden KH-Datei.

Beim erneuten Export sollen bereits eingetragene Bewertungsspalten (AFB,
Aufgabe, Punkte) erhalten bleiben. Diese Reconciliation ist reine
Domain-Logik (kein I/O): Die bestehende Datei liest ein Infrastruktur-Leser
über den Port `ExistingExpectedHorizonReaderPort` in `ExistingHorizonRow`s ein,
das Ergebnis rendert der Markdown-Renderer nur noch.

Regeln (unverändert gegenüber der früheren Renderer-internen Logik):

* **Schlüssel** ist ``(Datum, Ziel)`` nach Entfernen von Markdown-Hervorhebungen.
  Ein Datum gehört zu genau einer Stunde und damit zu genau einem Thema — das
  Thema muss nicht in den Schlüssel, und Legacy-Dateien ohne Überschriften
  mergen unverändert.
* Übereinstimmende Zeilen übernehmen AFB/Aufg/Pkte.
* Neue Zeilen werden vor der nächsten übereinstimmenden Altzeile verankert,
  damit Altzeilen an ihrem Platz bleiben; ohne Anker ans Ende.
* Entfallene, bereits bewertete Ziele bleiben als durchgestrichene Zeile erhalten
  (`ReconciledRow.removed`); unbewertete entfallene Ziele verschwinden.

Neu mit mehreren Themen — Zuordnung entfallener, bewerteter Zeilen:

* Trägt die Altzeile eine Section (aus einer ``### <Thema>``-Überschrift), bleibt
  sie in dieser Section, solange das Thema noch gewählt ist, sonst kommt sie in
  die abschließende Section `REMOVED_SECTION_TITLE`.
* Ohne Section (Legacy-Datei) gilt die Section ihres Ankers: der nächsten
  übereinstimmenden Altzeile, sonst der vorigen; ohne Anker ebenfalls
  `REMOVED_SECTION_TITLE`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from kursplaner.core.domain.expected_horizon import ExpectedHorizonLine, ExpectedHorizonSection, GoalKind

REMOVED_SECTION_TITLE = "Nicht mehr enthalten"
"""Überschrift der Section für bewertete Ziele, deren Thema nicht mehr gewählt ist."""


@dataclass(frozen=True)
class ExistingHorizonRow:
    """Eine Zeile einer bestehenden KH-Datei, wie sie der Leser-Port liefert.

    Args:
        section: Thema der letzten ``### <Thema>``-Überschrift davor, oder ``None``
            (Legacy-Datei ohne Überschriften).
        datum: Roher Datumszellwert (ggf. mit Markdown-Hervorhebung).
        ich_kann: Roher Zielzellwert (ggf. mit Markdown-Hervorhebung).
        afb: Eingetragene Anforderungsbereich-Zelle.
        aufg: Eingetragene Aufgaben-Zelle.
        pkte: Eingetragene Punkte-Zelle.
    """

    section: str | None
    datum: str
    ich_kann: str
    afb: str
    aufg: str
    pkte: str

    @property
    def is_graded(self) -> bool:
        """``True``, wenn mindestens eine Bewertungsspalte ausgefüllt ist."""
        return any(str(cell).strip() for cell in (self.afb, self.aufg, self.pkte))


@dataclass(frozen=True)
class ReconciledRow:
    """Eine abgeglichene Zeile für den Markdown-Renderer.

    Args:
        datum: Datum (bei entfallenen Zeilen ohne Hervorhebung).
        ich_kann: Zieltext (bei entfallenen Zeilen ohne Hervorhebung/Durchstreichung).
        kind: Art des Ziels (entfallene Zeilen: `GoalKind.TEILZIEL`, also schlicht).
        afb: Übernommene bzw. leere AFB-Zelle.
        aufg: Übernommene bzw. leere Aufgaben-Zelle.
        pkte: Übernommene bzw. leere Punkte-Zelle.
        removed: ``True`` für ein entfallenes, bereits bewertetes Ziel.
    """

    datum: str
    ich_kann: str
    kind: GoalKind
    afb: str = ""
    aufg: str = ""
    pkte: str = ""
    removed: bool = False


@dataclass(frozen=True)
class ReconciledSection:
    """Abgeglichene Zeilen eines Themas."""

    oberthema: str
    rows: tuple[ReconciledRow, ...]


@dataclass(frozen=True)
class ReconciledHorizon:
    """Ergebnis der Reconciliation: Sections in Ausgabereihenfolge."""

    sections: tuple[ReconciledSection, ...]


def strip_markdown_wrappers(value: str) -> str:
    """Entfernt umschließende ``**``/``~~``/``*``-Hervorhebungen (auch verschachtelt)."""
    text = str(value or "").strip()
    changed = True
    while changed and text:
        changed = False
        for marker in ("**", "~~", "*"):
            if text.startswith(marker) and text.endswith(marker) and len(text) >= 2 * len(marker):
                text = text[len(marker) : -len(marker)].strip()
                changed = True
    return text


def _merge_key(datum: str, ich_kann: str) -> tuple[str, str]:
    normalized_datum = re.sub(r"\s+", " ", strip_markdown_wrappers(datum)).strip()
    normalized_goal = re.sub(r"\s+", " ", strip_markdown_wrappers(ich_kann)).strip()
    return normalized_datum, normalized_goal


@dataclass(frozen=True)
class _Planned:
    topic: str
    line: ExpectedHorizonLine
    old_index: int | None


def _plan_rows(
    sections: Sequence[ExpectedHorizonSection], existing_rows: Sequence[ExistingHorizonRow]
) -> list[_Planned]:
    """Ordnet jeder neuen Zeile die erste noch freie Altzeile mit gleichem Schlüssel zu."""
    by_key: dict[tuple[str, str], list[int]] = {}
    for index, old in enumerate(existing_rows):
        by_key.setdefault(_merge_key(old.datum, old.ich_kann), []).append(index)
    planned: list[_Planned] = []
    for section in sections:
        for line in section.rows:
            matches = by_key.get(_merge_key(line.datum, line.ich_kann), [])
            planned.append(_Planned(section.oberthema, line, matches.pop(0) if matches else None))
    return planned


def _removed_topic(
    old_index: int,
    old: ExistingHorizonRow,
    matched: dict[int, _Planned],
    new_topics: set[str],
) -> str:
    """Section einer entfallenen, bewerteten Altzeile (siehe Modul-Docstring)."""
    if old.section is not None:
        return old.section if old.section in new_topics else REMOVED_SECTION_TITLE
    later = [index for index in matched if index > old_index]
    if later:
        return matched[min(later)].topic
    earlier = [index for index in matched if index < old_index]
    if earlier:
        return matched[max(earlier)].topic
    return REMOVED_SECTION_TITLE


def reconcile(
    sections: Sequence[ExpectedHorizonSection], existing_rows: Sequence[ExistingHorizonRow]
) -> ReconciledHorizon:
    """Gleicht neu erzeugte Sections mit den Zeilen einer bestehenden KH-Datei ab.

    Args:
        sections: Neu erzeugte Sections in Ausgabereihenfolge.
        existing_rows: Zeilen der Merge-Quelle (leer, wenn es keine gibt).

    Returns:
        Sections mit übernommenen Bewertungen; ggf. zusätzlich eine abschließende
        Section `REMOVED_SECTION_TITLE` für bewertete Ziele abgewählter Themen.
    """
    planned = _plan_rows(sections, existing_rows)
    matched = {entry.old_index: entry for entry in planned if entry.old_index is not None}
    new_topics = {section.oberthema for section in sections}

    before_old: dict[int, list[tuple[str, ReconciledRow]]] = {}
    tail_new: list[tuple[str, ReconciledRow]] = []
    for position, entry in enumerate(planned):
        if entry.old_index is not None:
            continue
        row = (entry.topic, ReconciledRow(entry.line.datum, entry.line.ich_kann, entry.line.kind))
        anchor = next((later.old_index for later in planned[position + 1 :] if later.old_index is not None), None)
        if anchor is None:
            tail_new.append(row)
        else:
            before_old.setdefault(anchor, []).append(row)

    merged: list[tuple[str, ReconciledRow]] = []
    for old_index, old in enumerate(existing_rows):
        merged.extend(before_old.get(old_index, []))
        entry = matched.get(old_index)
        if entry is not None:
            line = entry.line
            merged.append(
                (entry.topic, ReconciledRow(line.datum, line.ich_kann, line.kind, old.afb, old.aufg, old.pkte))
            )
        elif old.is_graded:
            removed = ReconciledRow(
                strip_markdown_wrappers(old.datum),
                strip_markdown_wrappers(old.ich_kann),
                GoalKind.TEILZIEL,
                old.afb,
                old.aufg,
                old.pkte,
                removed=True,
            )
            merged.append((_removed_topic(old_index, old, matched, new_topics), removed))
    merged.extend(tail_new)

    order = [section.oberthema for section in sections] + [REMOVED_SECTION_TITLE]
    grouped = {topic: [row for row_topic, row in merged if row_topic == topic] for topic in order}
    return ReconciledHorizon(
        sections=tuple(ReconciledSection(topic, tuple(grouped[topic])) for topic in order if grouped[topic])
    )
