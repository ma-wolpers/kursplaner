from __future__ import annotations

from kursplaner.core.domain.kompetenzgraph_diagnostics import KompetenzFieldIssue
from kursplaner.core.domain.kompetenzgraph_types import ANFORDERUNG_VALUES, KcZuordnungEintrag

_KC_ZUORDNUNG_FIELD = "kc_zuordnung"


def _clean_optional_str(value: object) -> str | None:
    """Normalisiert einen optionalen Freitextwert (`bundesland`/`schulform`/`niveau`).

    Leere Strings und `None` werden vereinheitlicht zu `None` -- laut
    Schema ist insbesondere `niveau` in den meisten Dateien legitim leer
    (undifferenziert), das ist kein Fehler.
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_jahrgang(value: object) -> int | None:
    """Parst `kc_zuordnung[].jahrgang` robust zu `int` oder `None`.

    PyYAML liefert für ein YAML-`8` bereits einen `int` -- diese Funktion
    fängt trotzdem defensiv String-Werte (z. B. `"8"`) und ungültige Werte
    ab, damit ein unerwartet formatierter Rohwert nicht mit einer
    unbehandelten Exception den gesamten Ladevorgang abbricht.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None


def _parse_single_kc_zuordnung_entry(
    raw_entry: object,
) -> tuple[KcZuordnungEintrag | None, KompetenzFieldIssue | None]:
    """Parst einen einzelnen rohen `kc_zuordnung`-Listeneintrag.

    Gibt bei einem strukturell ungültigen Eintrag (kein Dict, ungültige
    `anforderung`) `(None, issue)` zurück -- ein weicher Fehler, der laut
    Fehlerklassifizierung nur diesen einen Eintrag verwirft, nicht die
    gesamte Datei.
    """
    if not isinstance(raw_entry, dict):
        return None, KompetenzFieldIssue(
            field=_KC_ZUORDNUNG_FIELD,
            message="Eintrag ist kein Objekt (Bundesland/Schulform/... Zuordnung erwartet).",
            severity="warning",
        )

    anforderung = str(raw_entry.get("anforderung", "")).strip()
    if anforderung not in ANFORDERUNG_VALUES:
        return None, KompetenzFieldIssue(
            field=_KC_ZUORDNUNG_FIELD,
            message=f"Ungültige 'anforderung': {anforderung!r}.",
            severity="warning",
        )

    entry = KcZuordnungEintrag(
        bundesland=_clean_optional_str(raw_entry.get("bundesland")),
        schulform=_clean_optional_str(raw_entry.get("schulform")),
        niveau=_clean_optional_str(raw_entry.get("niveau")),
        jahrgang=_parse_jahrgang(raw_entry.get("jahrgang")),
        anforderung=anforderung,
        kc_verweis=str(raw_entry.get("kc_verweis", "") or "").strip(),
    )
    return entry, None


def _entry_identity_key(entry: KcZuordnungEintrag) -> tuple[str | None, str | None, str | None, int | None]:
    """Bildet den Kombinationsschlüssel, der laut Schema pro Datei nur einmal vorkommen darf."""
    return (entry.bundesland, entry.schulform, entry.niveau, entry.jahrgang)


def parse_kc_zuordnung_list(raw_value: object) -> tuple[tuple[KcZuordnungEintrag, ...], list[KompetenzFieldIssue]]:
    """Parst das komplette `kc_zuordnung`-Feld einer Kompetenz-Datei.

    Erwartet laut Schema mindestens einen gültigen Eintrag -- ob dieses
    Minimum erreicht wurde, prüft der Aufrufer (`kompetenzgraph_mapping.py`)
    anhand der zurückgegebenen (ggf. leeren) Tupel-Länge, da ein leeres
    Ergebnis hier je nach Kontext ein harter Fehler ("Datei verwerfen")
    ist.

    Args:
        raw_value: Der rohe, von PyYAML geparste Wert des Frontmatter-Felds
            `kc_zuordnung` (erwartet: Liste von Dicts).

    Returns:
        Ein Tupel aus (a) den erfolgreich geparsten, um Duplikate
        bereinigten Einträgen (Reihenfolge wie im Rohdokument, erster
        Treffer pro Kombination gewinnt) und (b) allen dabei aufgetretenen
        weichen Feldproblemen.
    """
    if not isinstance(raw_value, list):
        return (), [
            KompetenzFieldIssue(
                field=_KC_ZUORDNUNG_FIELD,
                message="Feld fehlt oder ist keine Liste.",
                severity="error",
            )
        ]

    issues: list[KompetenzFieldIssue] = []
    seen_keys: set[tuple[str | None, str | None, str | None, int | None]] = set()
    entries: list[KcZuordnungEintrag] = []

    for raw_entry in raw_value:
        entry, issue = _parse_single_kc_zuordnung_entry(raw_entry)
        if issue is not None:
            issues.append(issue)
            continue
        assert entry is not None
        key = _entry_identity_key(entry)
        if key in seen_keys:
            issues.append(
                KompetenzFieldIssue(
                    field=_KC_ZUORDNUNG_FIELD,
                    message=f"Kombination Bundesland/Schulform/Niveau/Jahrgang mehrfach vorhanden: {key!r}.",
                    severity="warning",
                )
            )
            continue
        seen_keys.add(key)
        entries.append(entry)

    return tuple(entries), issues
