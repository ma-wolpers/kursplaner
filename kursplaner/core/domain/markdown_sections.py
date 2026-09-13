"""Generische Markdown-Ueberschriften-/Abschnitts-Interpretation, kursplanerweit geteilt.

Analog zu `wiki_links.py`: ein kleines, reines, I/O-freies Domain-Modul. Ersetzt fuenf zuvor
unabhaengig voneinander implementierte Dialekte (Kompetenz-Dateien, Bereichs-Hubs,
UB-Reflexionsdateien, Einheiten-Praefill, Sequenzplan-Dateien) durch dieselben vier Funktionen.

Kennt AUSDRUECKLICH NICHTS von: Dateizugriff, YAML/Frontmatter (siehe `yaml_registry.py` fuer
die Trennung von Frontmatter und Body), Wiki-Link-Syntax (siehe `wiki_links.py`), fachlichen
Titel-Fallback-Ketten (kc_verweis/node_id o. ae.), UB-spezifischer Reflexions-/Listen-Semantik,
oder Sequenzplan-Schreib-/Splice-Logik. Liefert ausschliesslich generische strukturelle
Textoperationen -- alles Fachliche bleibt beim jeweiligen Aufrufer.

`_HEADING_RE` ist bewusst Implementierungsdetail (fuehrender Unterstrich, nicht exportiert):
andere Module duerfen ausschliesslich die vier oeffentlichen Funktionen unten nutzen, nie die
Regex direkt, damit die konkrete Erkennung austauschbar bleibt.
"""

from __future__ import annotations

import re

_HEADING_RE = re.compile(r"^\s*(#{1,6})\s*(.+?)\s*$")


def derive_first_heading_title(text: str) -> str | None:
    """Text der ersten nicht-leeren Ueberschriftzeile (beliebiger Ebene 1-6) im gesamten `text`.

    `None` ohne jede Ueberschrift. Reine Struktur-Information -- ob/wie daraus ein fachlicher
    "Titel" mit Fallback-Kette (kc_verweis, node_id, ...) wird, entscheidet ausschliesslich der
    Aufrufer. Scannt den GESAMTEN Text (nicht nur die erste Zeile) nach der ersten Ueberschrift,
    exakt wie die bisherigen `_derive_title()`/`_derive_bereich_title()`-Implementierungen.
    """
    for line in text.splitlines():
        match = _HEADING_RE.match(line)
        if match and match.group(2).strip():
            return match.group(2).strip()
    return None


def find_heading_line_index(
    lines: list[str],
    heading_text: str | None,
    *,
    case_sensitive: bool = False,
    target_level: int | None = None,
    start: int = 0,
) -> int:
    """Zeilenindex der ersten passenden Ueberschrift ab `start`, oder -1 wenn keine passt.

    `heading_text`: der gesuchte Ueberschriftstext. `None` bedeutet "beliebiger Text" -- dann
    matcht JEDE Ueberschrift, die `target_level` erfuellt (wird von `extract_section()` intern
    genutzt, um "die naechste Ueberschrift gleich welchen Inhalts" zu finden, z. B. um den
    Rest-Text nach einem extrahierten Abschnitt zu bestimmen).

    `target_level`: `None` (Default) -- die gesuchte Ueberschrift darf jede Ebene 1-6 haben.
    `int N` -- die gesuchte Ueberschrift muss GENAU Ebene N haben; eine gleichlautende
    Ueberschrift anderer Ebene zaehlt dann nicht als Treffer.

    Fuer Aufrufer, die zeilenbasiert weiterarbeiten (Einfuegen/Ersetzen), nicht nur lesen --
    siehe `extract_section()` fuer den reinen Lesefall.
    """
    normalized_heading = None
    if heading_text is not None:
        normalized_heading = heading_text.strip() if case_sensitive else heading_text.strip().lower()
    for index in range(start, len(lines)):
        match = _HEADING_RE.match(lines[index])
        if not match:
            continue
        if target_level is not None and len(match.group(1)) != target_level:
            continue
        candidate = match.group(2).strip()
        if not candidate:
            continue
        if normalized_heading is None:
            return index
        comparable = candidate if case_sensitive else candidate.lower()
        if comparable == normalized_heading:
            return index
    return -1


def extract_section(
    text: str,
    heading_text: str,
    *,
    case_sensitive: bool = False,
    target_level: int | None = None,
    stop_at_level: int | None = None,
) -> str | None:
    """Text zwischen einer Ueberschrift mit Text `heading_text` und der naechsten Ueberschrift/EOF.

    `None`, wenn `heading_text` nicht gefunden wurde -- Aufrufer entscheiden selbst ueber den
    Fallback (`[]`, `""`, ganzer Resttext, ...). Das Ergebnis ist `.strip()`-t (fuehrende/
    abschliessende Leerzeilen entfernt).

    `target_level`: siehe `find_heading_line_index()` -- dieselbe Semantik fuer die GESUCHTE
    Ueberschrift.

    `stop_at_level`: `None` (Default) -- der Abschnitt endet an JEDER nachfolgenden Ueberschrift
    beliebiger Ebene. `int N` -- der Abschnitt endet NUR an einer nachfolgenden Ueberschrift GENAU
    der Ebene N; Ueberschriften anderer Ebenen (auch tiefere Unterueberschriften) zaehlen dann als
    gewoehnlicher Text und bleiben TEIL des Abschnitts.

    Bewusst klein und stabil gehalten: keine weiteren Schalter (trim/include_heading/allow_nested/
    stop_mode/...) ohne einen real existierenden Aufrufer, der sie braucht.
    """
    lines = text.splitlines()
    start_index = find_heading_line_index(
        lines, heading_text, case_sensitive=case_sensitive, target_level=target_level
    )
    if start_index == -1:
        return None

    start = start_index + 1
    end = len(lines)
    for index in range(start, len(lines)):
        match = _HEADING_RE.match(lines[index])
        if not match:
            continue
        if stop_at_level is not None and len(match.group(1)) != stop_at_level:
            continue
        end = index
        break

    return "\n".join(lines[start:end]).strip()


def extract_bullet_items(section_text: str) -> list[str]:
    """Zeilen von `section_text`, die (nach Trim) mit '-' beginnen, ohne das '-' selbst."""
    items: list[str] = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        item = stripped[1:].strip()
        if item:
            items.append(item)
    return items
