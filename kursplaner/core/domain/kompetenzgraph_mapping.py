from __future__ import annotations

from dataclasses import dataclass

from kursplaner.core.domain.kompetenzgraph_diagnostics import KompetenzFieldIssue
from kursplaner.core.domain.kompetenzgraph_kc_zuordnung_mapping import parse_kc_zuordnung_list
from kursplaner.core.domain.kompetenzgraph_node import KompetenzNode
from kursplaner.core.domain.kompetenzgraph_types import STATUS_ENTWURF, STATUS_VALUES, SourceRef
from kursplaner.core.domain.markdown_sections import derive_first_heading_title, extract_section, find_heading_line_index
from kursplaner.core.domain.wiki_links import extract_wiki_link_target


@dataclass(frozen=True)
class BodySections:
    """Ergebnis der Zerlegung eines Kompetenz-Bodys für die Volltextsuche.

    Ausschließlich von `split_kompetenz_body_sections()` erzeugt -- siehe
    dort für die genaue Zerlegungsregel. Kein Bestandteil von `KompetenzNode`
    (Lazy Body bleibt unangetastet, siehe dessen Docstring); wird nur bei
    Bedarf über `KompetenzTextSearchIndex` (core/usecases) abgeleitet.

    Attributes:
        beispiel_text: Freitext unter der `## Beispiel`-Überschrift (bis zur
            nächsten Überschrift/EOF), oder leerer String ohne eine solche
            Überschrift.
        rest_text: Aller übrige Body-Text nach der Titelzeile, der NICHT zu
            `beispiel_text` gehört (Text vor einer etwaigen Beispiel-
            Überschrift, plus alles danach, falls weitere Abschnitte folgen).
    """

    beispiel_text: str
    rest_text: str


def split_kompetenz_body_sections(body_text: str) -> BodySections:
    """Zerlegt den rohen Markdown-Body in einen Beispiel- und einen Rest-Abschnitt.

    Arbeitet auf demselben unveränderten, bereits von `body_after_frontmatter()`
    gelieferten Rohtext wie `_derive_title()`. Nutzt ausschließlich die geteilten
    Primitiven aus `core/domain/markdown_sections.py` -- der einzigen Stelle im
    Projekt, die Markdown-Überschriften/-Abschnitte generisch erkennt. "Rest des
    Dokuments" bleibt dabei roher Markdown-Text, keine gerenderte/entmarkerte
    Darstellung.

    Regel: die erste Zeile wird übersprungen, falls sie eine Überschrift ist
    (Titelzeile). Danach wird die erste Überschrift beliebiger Ebene gesucht,
    deren Text case-insensitiv exakt ``"Beispiel"`` ergibt; der Text bis zur
    nächsten Überschrift beliebiger Ebene (oder EOF) wird `beispiel_text`.
    Alles andere -- Text vor der Beispiel-Überschrift (ohne die übersprungene
    Titelzeile) sowie alles nach dem Beispiel-Abschnitt -- wird zu `rest_text`
    zusammengefügt. Fehlt eine Beispiel-Überschrift ganz, ist `beispiel_text`
    leer und `rest_text` enthält den kompletten Text nach der Titelzeile.
    """
    lines = body_text.splitlines()
    start = 1 if lines and derive_first_heading_title(lines[0]) else 0
    remaining_lines = lines[start:]
    remaining_text = "\n".join(remaining_lines)

    beispiel_text = extract_section(remaining_text, "Beispiel", target_level=None, stop_at_level=None)
    if beispiel_text is None:
        return BodySections(beispiel_text="", rest_text=remaining_text.strip())

    beispiel_heading_index = find_heading_line_index(remaining_lines, "Beispiel", target_level=None)
    end_index = find_heading_line_index(remaining_lines, None, target_level=None, start=beispiel_heading_index + 1)
    if end_index == -1:
        end_index = len(remaining_lines)

    rest_lines = remaining_lines[:beispiel_heading_index] + remaining_lines[end_index:]
    return BodySections(beispiel_text=beispiel_text, rest_text="\n".join(rest_lines).strip())


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
        return None, KompetenzFieldIssue(field=field, message=f"Kein gültiger Wikilink: {text!r}.", severity="error")
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
    Dateien): erste `#`-Überschriftzeile des Body (via `markdown_sections.py::
    derive_first_heading_title`, rein strukturell) → erstes nicht-leeres
    `kc_verweis` aus `kc_zuordnung` → die ID selbst. Die Fallback-Kette selbst
    bleibt fachliche, Kompetenz-spezifische Logik hier vor Ort. So hat jeder
    Knoten garantiert einen nicht-leeren Titel für Graph-Label/Liste/Tooltip,
    unabhängig davon, wie unvollständig die Quelldatei ist.
    """
    title = derive_first_heading_title(body_text)
    if title:
        return title
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
    title_override: str | None = None,
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
            Titel-Ableitung, sofern `title_override` nicht gesetzt ist;
            wird NICHT im zurückgegebenen `KompetenzNode` gespeichert,
            siehe dessen Docstring zu Lazy Body).
        node_id: Kompetenz-ID (Dateiname ohne `.md`).
        source: Physische Herkunft dieser Datei.
        title_override: Bereits bekannter Titel (z. B. aus einem
            Cache-Treffer, bei dem der Body gar nicht erst gelesen wurde)
            -- wenn gesetzt, wird `body_text` für die Titel-Ableitung
            ignoriert (die übrigen Felder werden trotzdem regulär aus
            `frontmatter_raw` gemappt, unabhängig von `body_text`).

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

    oberkompetenzen_ids, ober_issues = _extract_wikilink_list(frontmatter_raw.get("oberkompetenzen"), "oberkompetenzen")
    issues.extend(ober_issues)

    voraussetzungen_ids, voraus_issues = _extract_wikilink_list(
        frontmatter_raw.get("voraussetzungen"), "voraussetzungen"
    )
    issues.extend(voraus_issues)

    offene_voraussetzungen = _extract_freetext_list(frontmatter_raw.get("offene_voraussetzungen"))

    status, status_issue = _resolve_status(frontmatter_raw.get("status"))
    if status_issue is not None:
        issues.append(status_issue)

    if title_override is not None:
        title = title_override
    else:
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
