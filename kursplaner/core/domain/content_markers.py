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


FERIEN_MARKER_TOKEN = "X"


def is_ausfall_marker(text: str) -> bool:
    """Erkennt Ausfall-Zeilen (neu: X..., kompatibel: Ausfall...).

    Erkennt sowohl normalen Ausfall (`X <Grund>`) als auch Ferien
    (`X <Grund> X`, siehe :func:`is_ferien_marker`) - Ferien sind eine
    Teilmenge von Ausfall.
    """
    lowered = _norm_prefix(text)
    return lowered == "x" or lowered.startswith("x ") or lowered.startswith("ausfall")


def is_ferien_marker(text: str) -> bool:
    """Erkennt Ferien-/Feiertagszeilen am abschliessenden ``X``-Token.

    Ferien tragen zusaetzlich zum fuehrenden ``X`` (das sie als Ausfall
    kennzeichnet) ein abschliessendes ``X``-Token, um sie von einem
    manuellen Ausfall (z. B. Krankheit) textuell unterscheidbar zu machen -
    das ersetzt den fruehreren impliziten ``Stunden == 0``-Sentinel.

    Um Zufallstreffer zu vermeiden (z. B. ein Grund, der zufaellig auf ein
    X-Wort endet), zaehlt nur ein **eigenstaendiges** letztes Token ``X``.

    Example::

        is_ferien_marker("X Sommerferien X")
        # -> True
        is_ferien_marker("X XLAB")
        # -> False (letztes Token ist "XLAB", nicht "X")
        is_ferien_marker("X X")
        # -> True (Ferien ohne Grundangabe)
    """
    if not is_ausfall_marker(text):
        return False
    tokens = normalize_marker_text(text).split(" ")
    return bool(tokens) and tokens[-1] == FERIEN_MARKER_TOKEN


def marker_reason_text(text: str) -> str:
    """Extrahiert den reinen Grundtext aus einem Ausfall-/Ferien-/Legacy-Marker.

    Entfernt ein fuehrendes ``X``, ein ggf. vorhandenes abschliessendes
    ``X`` (Ferien-Markierung) sowie den alten ``Ausfall``-Praefix.

    Example::

        marker_reason_text("X Sommerferien X")
        # -> "Sommerferien"
        marker_reason_text("X Lehrer krank")
        # -> "Lehrer krank"
    """
    normalized = normalize_marker_text(text)
    if not normalized:
        return ""

    lowered = normalized.lower()
    if lowered == "x":
        return ""
    if lowered.startswith("x "):
        remainder = normalized[2:].strip()
    elif lowered.startswith("ausfall"):
        remainder = normalized[len("ausfall") :].strip(" :–—-")
    else:
        return normalized

    tokens = remainder.split(" ")
    if tokens and tokens[-1] == FERIEN_MARKER_TOKEN:
        remainder = " ".join(tokens[:-1]).strip()
    return remainder


def resolve_row_cancel_state(headers: list[str], row: list[str]) -> bool:
    """Ermittelt robust, ob eine Plantabellenzeile (anhand ihres Textmarkers) Ausfall ist.

    Zentraler, "sturdy" Einstiegspunkt fuer die textbasierte Ausfall-Erkennung.
    Prueft ausschliesslich die `Thema/Ausfall`-Spalte (seit Entfernung der
    `Stunden`-Spalte die einzige Marker-Quelle; jede migrierte Tabelle hat
    diese Spalte). Fuer den vollstaendigen Ausfall-Status inkl. YAML-Override
    (`Stundentyp: Ausfall` ohne Textmarker) siehe :func:`resolve_cancel_state`.

    Args:
        headers: Spaltenüberschriften der Planungstabelle (Groß-/Kleinschreibung
            beliebig, wird intern normalisiert).
        row: Zellwerte einer einzelnen Tabellenzeile, passend zu `headers`.

    Returns:
        `True`, wenn die Zeile als Ausfall gilt.

    Example::

        resolve_row_cancel_state(
            ["Datum", "Inhalt", "Thema/Ausfall"],
            ["27-02-26", "", "X XLAB"],
        )
        # -> True
    """
    header_map = {str(name).strip().lower(): idx for idx, name in enumerate(headers)}

    idx_thema_ausfall = header_map.get("thema/ausfall")
    if idx_thema_ausfall is None:
        return False
    cell = row[idx_thema_ausfall] if idx_thema_ausfall < len(row) else ""
    return is_ausfall_marker(cell)


def resolve_row_ferien_state(headers: list[str], row: list[str]) -> bool:
    """Ermittelt, ob eine Plantabellenzeile als Ferien/Feiertag markiert ist.

    Spiegelbild zu :func:`resolve_row_cancel_state`, aber fuer die engere
    Ferien-Teilmenge (abschliessendes ``X``-Token, siehe :func:`is_ferien_marker`).
    """
    header_map = {str(name).strip().lower(): idx for idx, name in enumerate(headers)}
    idx_thema_ausfall = header_map.get("thema/ausfall")
    if idx_thema_ausfall is None:
        return False
    cell = row[idx_thema_ausfall] if idx_thema_ausfall < len(row) else ""
    return is_ferien_marker(cell)


def classify_row_marker(headers: list[str], row: list[str]) -> str:
    """Klassifiziert den Marker einer Planzeile als ``"ferien"``, ``"ausfall"`` oder ``"none"``.

    Bequemlichkeitsfunktion, die :func:`resolve_row_ferien_state` und
    :func:`resolve_row_cancel_state` zu einer einzigen Drei-Werte-Klassifikation
    zusammenfasst.
    """
    if resolve_row_ferien_state(headers, row):
        return "ferien"
    if resolve_row_cancel_state(headers, row):
        return "ausfall"
    return "none"


def resolve_cancel_state(
    headers: list[str], row: list[str], lesson_yaml: dict[str, object] | None = None
) -> bool:
    """Ermittelt den vollstaendigen Ausfall-Status inkl. YAML-Override.

    Einzige Wahrheit fuer "ist diese Zeile Ausfall" ueber die reine
    Textmarker-Pruefung (:func:`resolve_row_cancel_state`) hinaus: eine Zeile
    gilt auch dann als Ausfall, wenn ihre verlinkte Stunden-Datei
    ``Stundentyp: Ausfall`` traegt, selbst ohne Textmarker in der
    `Thema/Ausfall`-Spalte. Konsolidiert zwei zuvor unabhaengige, teils
    widerspruechliche Implementierungen (Detailansicht mit YAML-Override,
    Kursuebersicht ohne).

    Args:
        headers: Spaltenüberschriften der Planungstabelle.
        row: Zellwerte einer einzelnen Tabellenzeile.
        lesson_yaml: Normalisiertes YAML-Dictionary der verlinkten
            Stunden-Datei, falls vorhanden (sonst ``None``).

    Returns:
        `True`, wenn die Zeile als Ausfall gilt (Textmarker oder YAML-Typ).
    """
    if resolve_row_cancel_state(headers, row):
        return True
    if lesson_yaml is None:
        return False
    return str(lesson_yaml.get("Stundentyp", "")).strip() == "Ausfall"


def build_ausfall_marker(reason_text: str) -> str:
    """Baut die kanonische Ausfall-Markierung als `X <Grund>`.

    Entfernt ein ggf. vorhandenes abschliessendes ``X`` (Ferien-Markierung),
    damit eine zuvor als Ferien markierte Zeile beim erneuten Markieren als
    normaler Ausfall nicht versehentlich `X ... X` behaelt.
    """
    reason = marker_reason_text(reason_text) or normalize_marker_text(reason_text)
    if not reason or reason.lower() == "x":
        return "X Ohne Angabe"
    return f"X {reason}".strip()


def build_ferien_marker(reason_text: str) -> str:
    """Baut die kanonische Ferien-Markierung als `X <Grund> X`.

    Das abschliessende ``X`` unterscheidet Ferien/Feiertage textuell von
    einem normalen manuellen Ausfall (siehe :func:`is_ferien_marker`).

    Example::

        build_ferien_marker("Sommerferien")
        # -> "X Sommerferien X"
        build_ferien_marker("")
        # -> "X Ohne Angabe X"
    """
    reason = marker_reason_text(reason_text) or normalize_marker_text(reason_text)
    if not reason or reason.lower() == "x":
        return "X Ohne Angabe X"
    return f"X {reason} X".strip()


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
