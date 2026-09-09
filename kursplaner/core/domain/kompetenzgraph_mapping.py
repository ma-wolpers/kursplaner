from __future__ import annotations

import re

from kursplaner.core.domain.kompetenzgraph_diagnostics import KompetenzFieldIssue
from kursplaner.core.domain.kompetenzgraph_kc_zuordnung_mapping import parse_kc_zuordnung_list
from kursplaner.core.domain.kompetenzgraph_node import KompetenzNode
from kursplaner.core.domain.kompetenzgraph_types import STATUS_ENTWURF, STATUS_VALUES, SourceRef
from kursplaner.core.domain.wiki_links import extract_wiki_link_target

_HEADING_RE = re.compile(r"^\s*#{1,6}\s*(.+?)\s*$")


def _extract_single_wikilink(raw_value: object, field: str) -> tuple[str | None, KompetenzFieldIssue | None]:
    """Löst ein Pflichtfeld auf, das genau einen Wikilink enthalten muss (`primarer_bereich`).

    Nutzt ausschließlich `wiki_links.py::extract_wiki_link_target` zur
    Dekodierung -- keine eigene Regex, wie im Implementierungsplan als
    zentraler Wiederverwendungs-Anker festgelegt.
    """
    text = str(raw_value or "").strip()
    if not text:
        return None, KompetenzFieldIssue(field=field, message="Pflichtfeld fehlt oder ist leer.", severity="error")
    target = extract_wiki_link_target(text)
    if not target:
        return None, KompetenzFieldIssue(
            field=field, message=f"Kein gültiger Wikilink: {text!r}.", severity="error"
        )
    return target, None


def _extract_wikilink_list(raw_value: object, field: str) -> tuple[tuple[str, ...], list[KompetenzFieldIssue]]:
    """Löst ein optionales Listenfeld aus Wikilinks auf (`oberkompetenzen`/`voraussetzungen`/`prozessbereiche`).

    Ein einzelner nicht auflösbarer Eintrag ist ein weicher Fehler: nur
    diese eine Kante wird verworfen, die übrigen Einträge bleiben
    erhalten (siehe Fehlerklassifizierungs-Tabelle im Implementierungsplan).
    """
    if raw_value is None:
        return (), []
    if not isinstance(raw_value, list):
        return (), [KompetenzFieldIssue(field=field, message="Feld ist keine Liste.", severity="warning")]

    issues: list[KompetenzFieldIssue] = []
    targets: list[str] = []
    for raw_item in raw_value:
        text = str(raw_item or "").strip()
        target = extract_wiki_link_target(text)
        if not target:
            issues.append(
                KompetenzFieldIssue(field=field, message=f"Kein gültiger Wikilink: {text!r}.", severity="warning")
            )
            continue
        targets.append(target)
    return tuple(targets), issues


def _extract_freetext_list(raw_value: object) -> tuple[str, ...]:
    """Liest `offene_voraussetzungen` als reine Freitext-Liste.

    Ausdrücklich KEINE Wikilink-Auflösung -- laut Schema (Invariante 14)
    ist dieses Feld nie eine Graph-Kante, auch wenn ein Eintrag zufällig
    wie ein Link aussehen sollte.
    """
    if not isinstance(raw_value, list):
        return ()
    return tuple(str(item).strip() for item in raw_value if str(item or "").strip())


def _resolve_status(raw_value: object) -> tuple[str, KompetenzFieldIssue | None]:
    """Validiert `status` gegen `STATUS_VALUES`, mit weichem Fallback auf `STATUS_ENTWURF`."""
    text = str(raw_value or "").strip()
    if text in STATUS_VALUES:
        return text, None
    return STATUS_ENTWURF, KompetenzFieldIssue(
        field="status", message=f"Ungültiger Status {text!r}, Fallback auf '{STATUS_ENTWURF}'.", severity="warning"
    )


def _derive_title(body_text: str, kc_verweise: tuple[str, ...], node_id: str) -> str:
    """Leitet den Anzeigetitel einer Kompetenz aus der ersten Überschriftzeile ihres Body ab.

    Fallback-Kette (mehrlagige Absicherung gegen unvollständige/untypische
    Dateien): erste `#`-Überschriftzeile des Body → erstes nicht-leeres
    `kc_verweis` aus `kc_zuordnung` → die ID selbst. So hat jeder Knoten
    garantiert einen nicht-leeren Titel für Graph-Label/Liste/Tooltip,
    unabhängig davon, wie unvollständig die Quelldatei ist.
    """
    for line in body_text.splitlines():
        match = _HEADING_RE.match(line)
        if match and match.group(1).strip():
            return match.group(1).strip()
    for kc_verweis in kc_verweise:
        if kc_verweis.strip():
            return kc_verweis.strip()
    return node_id


def parse_kompetenz_node_from_raw(
    frontmatter_raw: dict[str, object],
    body_text: str,
    *,
    node_id: str,
    source: SourceRef,
) -> tuple[KompetenzNode | None, tuple[KompetenzFieldIssue, ...]]:
    """Mappt bereits per PyYAML geparstes Frontmatter + Body auf ein `KompetenzNode`-Domain-Objekt.

    Reine Funktion ohne I/O -- `frontmatter_raw` muss bereits das Ergebnis
    von `yaml.safe_load()` auf den extrahierten Frontmatter-Block sein
    (siehe `kompetenzgraph_repository.py`, dem einzigen Ort mit
    `import yaml`). Wendet die mehrlagige Fehlerklassifizierung aus dem
    Implementierungsplan an: harte Fehler (fehlendes `primarer_bereich`,
    kein einziger gültiger `kc_zuordnung`-Eintrag) führen zum Verwerfen
    der gesamten Datei (`None`-Rückgabe), weiche Fehler (ungültiger
    einzelner `kc_zuordnung`-Eintrag, nicht auflösbarer Wikilink,
    ungültiger `status`) verwerfen nur den betroffenen Teil.

    Args:
        frontmatter_raw: Rohes Frontmatter-Dict dieser Datei.
        body_text: Markdown-Body nach dem Frontmatter-Block (für die
            Titel-Ableitung; wird NICHT im zurückgegebenen `KompetenzNode`
            gespeichert, siehe dessen Docstring zu Lazy Body).
        node_id: Kompetenz-ID (Dateiname ohne `.md`).
        source: Physische Herkunft dieser Datei.

    Returns:
        `(node, issues)` -- `node` ist `None`, wenn ein harter Fehler
        auftrat; `issues` enthält in jedem Fall alle aufgetretenen
        Probleme (auch bei erfolgreichem Mapping, z. B. verworfene
        einzelne `kc_zuordnung`-Einträge).
    """
    issues: list[KompetenzFieldIssue] = []

    primarer_bereich_id, bereich_issue = _extract_single_wikilink(
        frontmatter_raw.get("primarer_bereich"), "primarer_bereich"
    )
    if bereich_issue is not None:
        issues.append(bereich_issue)

    kc_zuordnung, kc_issues = parse_kc_zuordnung_list(frontmatter_raw.get("kc_zuordnung"))
    issues.extend(kc_issues)
    if not kc_zuordnung and not any(issue.severity == "error" for issue in kc_issues):
        # Feld war syntaktisch eine Liste, aber nach Bereinigung blieb kein gueltiger
        # Eintrag uebrig (z. B. eine leere Liste oder ausschliesslich ungueltige
        # Eintraege) -- das ist gemaess Fehlerklassifizierung ein harter Fehler auf
        # Knoten-Ebene, nicht schon von `parse_kc_zuordnung_list` selbst gemeldet.
        issues.append(
            KompetenzFieldIssue(
                field="kc_zuordnung", message="Kein gültiger Eintrag nach Bereinigung übrig.", severity="error"
            )
        )

    if primarer_bereich_id is None or not kc_zuordnung:
        return None, tuple(issues)

    prozessbereich_ids, prozess_issues = _extract_wikilink_list(
        frontmatter_raw.get("prozessbereiche"), "prozessbereiche"
    )
    issues.extend(prozess_issues)

    oberkompetenzen_ids, ober_issues = _extract_wikilink_list(
        frontmatter_raw.get("oberkompetenzen"), "oberkompetenzen"
    )
    issues.extend(ober_issues)

    voraussetzungen_ids, voraus_issues = _extract_wikilink_list(
        frontmatter_raw.get("voraussetzungen"), "voraussetzungen"
    )
    issues.extend(voraus_issues)

    offene_voraussetzungen = _extract_freetext_list(frontmatter_raw.get("offene_voraussetzungen"))

    status, status_issue = _resolve_status(frontmatter_raw.get("status"))
    if status_issue is not None:
        issues.append(status_issue)

    title = _derive_title(body_text, tuple(entry.kc_verweis for entry in kc_zuordnung), node_id)

    node = KompetenzNode(
        id=node_id,
        source=source,
        primarer_bereich_id=primarer_bereich_id,
        prozessbereich_ids=prozessbereich_ids,
        oberkompetenzen_ids=oberkompetenzen_ids,
        voraussetzungen_ids=voraussetzungen_ids,
        offene_voraussetzungen=offene_voraussetzungen,
        kc_zuordnung=kc_zuordnung,
        status=status,
        title=title,
    )
    return node, tuple(issues)
