from __future__ import annotations

import re

WIKI_LINK_WITH_ALIAS_RE = re.compile(r"\[\[([^\]|]+)\|([^\]]+)\]\]")
WIKI_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
WHITESPACE_RE = re.compile(r"\s+")


def normalize_marker_text(text: str) -> str:
    """Normalisiert Tabelleninhalt für Marker-Interpretation (Wiki-Klammern ignoriert)."""
    raw = str(text or "").strip()
    if not raw:
        return ""

    unwrapped = WIKI_LINK_WITH_ALIAS_RE.sub(lambda match: match.group(2).strip() or match.group(1).strip(), raw)
    unwrapped = WIKI_LINK_RE.sub(lambda match: match.group(1).strip(), unwrapped)
    return WHITESPACE_RE.sub(" ", unwrapped).strip()


def _norm_prefix(text: str) -> str:
    """Normalisiert Markertext und liefert ihn in Kleinbuchstaben."""
    return normalize_marker_text(text).lower()


def is_ausfall_marker(text: str) -> bool:
    """Erkennt Ausfall-Zeilen (neu: X..., kompatibel: Ausfall...)."""
    lowered = _norm_prefix(text)
    return lowered == "x" or lowered.startswith("x ") or lowered.startswith("ausfall")


def resolve_row_cancel_state(headers: list[str], row: list[str]) -> bool:
    """Ermittelt robust und schema-übergreifend, ob eine Plantabellenzeile Ausfall ist.

    Zentraler, "sturdy" Einstiegspunkt fuer die Ausfall-Erkennung, damit nicht
    jede Aufrufstelle einzeln zwischen dem aktuellen 4-Spalten-Schema und alten
    3-Spalten-Tabellen unterscheiden muss (genau das ist bei der Migration auf
    die eigene `Thema/Ausfall`-Spalte an mehreren Stellen im Code auseinander-
    gedriftet). Bevorzugt die `Thema/Ausfall`-Spalte; nur wenn diese in `headers`
    komplett fehlt, wird ersatzweise der `Inhalt`-Zellwert auf einen eingebetteten
    Legacy-Marker geprüft. Neue Aufrufstellen, die aus einer Planzeile einen
    Ausfall-Status ableiten müssen, sollen diese Funktion nutzen statt eine eigene
    spaltenspezifische Prüfung zu schreiben.

    Args:
        headers: Spaltenüberschriften der Planungstabelle (Groß-/Kleinschreibung
            beliebig, wird intern normalisiert).
        row: Zellwerte einer einzelnen Tabellenzeile, passend zu `headers`.

    Returns:
        `True`, wenn die Zeile als Ausfall gilt.

    Example::

        resolve_row_cancel_state(
            ["Datum", "Stunden", "Inhalt", "Thema/Ausfall"],
            ["27-02-26", "2", "", "X XLAB"],
        )
        # -> True
    """
    header_map = {str(name).strip().lower(): idx for idx, name in enumerate(headers)}

    idx_thema_ausfall = header_map.get("thema/ausfall")
    if idx_thema_ausfall is not None:
        cell = row[idx_thema_ausfall] if idx_thema_ausfall < len(row) else ""
        return is_ausfall_marker(cell)

    idx_inhalt = header_map.get("inhalt")
    if idx_inhalt is None:
        return False
    cell = row[idx_inhalt] if idx_inhalt < len(row) else ""
    return is_ausfall_marker(normalize_marker_text(cell))


def build_ausfall_marker(reason_text: str) -> str:
    """Baut die kanonische Ausfall-Markierung als `X <Grund>`."""
    reason = normalize_marker_text(reason_text)
    if not reason:
        return "X Ohne Angabe"

    lowered = reason.lower()
    if lowered == "x":
        return "X Ohne Angabe"
    if lowered.startswith("x "):
        return f"X {reason[2:].strip()}".strip()
    if lowered.startswith("ausfall"):
        rest = reason[len("ausfall") :].strip(" :–—-")
        return f"X {rest}".strip() if rest else "X Ausfall"
    return f"X {reason}".strip()


def upgrade_legacy_ausfall_marker(text: str) -> str | None:
    """Konvertiert alte `Ausfall...`-Marker zu `X ...`; liefert `None` falls unverändert."""
    normalized = normalize_marker_text(text)
    if not normalized:
        return None

    lowered = normalized.lower()
    if lowered == "x" or lowered.startswith("x "):
        return None
    if lowered.startswith("ausfall"):
        return build_ausfall_marker(normalized)
    return None


def is_hospitation_marker(text: str, group_name: str) -> bool:
    """Erkennt Hospitationsmarker für eine Lerngruppe.

    Erwartet Marker im Stil ``HO <gruppe> ...``.
    """
    lowered = _norm_prefix(text)
    group = normalize_marker_text(group_name).lower()
    if not lowered.startswith("ho"):
        return False
    if not group:
        return lowered.startswith("ho ")
    return lowered.startswith(f"ho {group}")


def build_hospitation_marker(group_name: str, note_text: str = "") -> str:
    """Baut die kanonische Hospitations-Markierung als `HO <Gruppe> <Hinweis>`."""
    group = normalize_marker_text(group_name)
    note = normalize_marker_text(note_text)
    if not group:
        group = "Gruppe"
    if note:
        return f"HO {group} {note}".strip()
    return f"HO {group}".strip()


def is_unterricht_marker(text: str, group_name: str) -> bool:
    """Erkennt reguläre Unterrichtsmarker anhand des Gruppentokens."""
    lowered = _norm_prefix(text)
    group = normalize_marker_text(group_name).lower()
    if not group:
        return False
    return lowered.startswith(group)
