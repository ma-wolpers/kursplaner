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
