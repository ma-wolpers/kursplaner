"""Zentrales Wertemodell des YAML-Felds ``Oberthema`` einer Stunden-Datei.

Kanonische Form hängt vom Stundentyp ab:

* **LZK** (einziger Typ mit mehreren Themen): YAML-Liste aus Wiki-Links
  ``[[gruppe thema]]`` in chronologischer Reihenfolge.
* **Unterricht/Hospitation**: ein einzelner Wert, gespeichert wie eingegeben
  (Klartext oder Wiki-Link) — keine Listenform.

Invarianten der entschlüsselten Themenliste:

* kein Thema doppelt (Vergleich nach Entschlüsselung + Whitespace-Normalisierung,
  erstes Vorkommen gewinnt),
* keine leeren Einträge,
* das erste Element ist das *Haupt-Oberthema*, auf dem alle einwertigen
  Lesepfade (Grid-Vergleich, Plantabelle, Themenfolgen, Tageslog) arbeiten.

Die Verantwortlichkeiten sind bewusst getrennt:

* `parse_oberthema_field` prüft nur den **Typ** und wirft bei nicht
  unterstützten Werten `UnsupportedOberthemaValue` — es deutet nie um.
* `normalize_oberthemen` arbeitet nur auf Strings (Invarianten durchsetzen).
* `encode_oberthemen` erzeugt die kanonische LZK-Schreibform.
* `read_oberthema_state` ist der zentrale Lesepfad und hält "leer" und
  "ungültig" getrennt fest.
* `ensure_oberthema_write_allowed` ist die Schreib-Invariante: ein ungültiger
  Plattenwert wird nie still überschrieben.

Das Lesen ist für alle Typen tolerant (Skalar oder Liste); bei einer LZK wird
ein Legacy-Skalar nur noch als *Eingabe* akzeptiert und beim Kursladen migriert.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from kursplaner.core.domain.wiki_links import strip_group_prefixed_link, strip_wiki_link

OBERTHEMA_KEY = "Oberthema"
OBERTHEMA_DISPLAY_SEPARATOR = " | "
"""Trenner mehrerer Oberthemen in der Grid-Anzeige (vom Listen-Parser verstanden)."""
OBERTHEMA_INVALID_MARKER = "⚠ ungültiges Oberthema"
"""Grid-Anzeige für einen nicht unterstützten gespeicherten Oberthema-Wert."""

_FLOW_MAPPING_RE = re.compile(r"^\s*\{.*\}\s*$", re.DOTALL)
_FLOW_SEQUENCE_RE = re.compile(r"^\s*\[(?!\[).*\]\s*$", re.DOTALL)


class UnsupportedOberthemaValue(ValueError):
    """Der gespeicherte ``Oberthema``-Wert hat einen nicht unterstützten Typ.

    Beispiele: ein eingerückter Mapping-Block (`RawYamlBlock`), ein Flow-Mapping
    ``{a: b}``, eine Flow-Liste ``[a, b]`` oder ein Nicht-String-Listeneintrag.
    """


class OberthemaRepairRequired(RuntimeError):
    """Ein normaler Schreibvorgang würde ein ungültiges ``Oberthema`` überschreiben.

    Wird von der Schreibgrenze (`LessonRepository.save_lesson_yaml`) ausgelöst,
    damit eine problematische Datei bis zur ausdrücklichen Korrektur als solche
    erkennbar bleibt.
    """


@dataclass(frozen=True)
class OberthemaState:
    """Gelesener Zustand eines ``Oberthema``-Felds.

    Args:
        topics: Entschlüsselte, normalisierte Themenliste (leer bei "kein
            Oberthema" *und* bei ungültigem Wert).
        invalid_raw: Der unveränderte Rohwert, wenn er nicht unterstützt wird,
            sonst ``None``. Nur so lassen sich "leer" (``topics == ()`` und
            ``invalid_raw is None``) und "ungültig" unterscheiden.
    """

    topics: tuple[str, ...]
    invalid_raw: object | None = None

    @property
    def is_invalid(self) -> bool:
        """``True``, wenn der gespeicherte Wert einen nicht unterstützten Typ hat."""
        return self.invalid_raw is not None

    @property
    def primary(self) -> str:
        """Das Haupt-Oberthema (erstes Element) oder ``""``."""
        return self.topics[0] if self.topics else ""


def is_unsupported_oberthema_value(raw: object) -> bool:
    """Prüft nur den Typ eines Rohwerts, ohne zu werfen (siehe `parse_oberthema_field`)."""
    try:
        parse_oberthema_field(raw)
    except UnsupportedOberthemaValue:
        return True
    return False


def parse_oberthema_field(raw: object) -> list[str]:
    """Prüft den Typ eines rohen ``Oberthema``-Werts und liefert dessen String-Einträge.

    Unterstützt werden ``None``/``""`` (kein Thema), ein String (Legacy-Skalar)
    und eine Liste aus Strings. Alles andere wird **nicht** umgedeutet, sondern
    mit `UnsupportedOberthemaValue` abgelehnt.

    Args:
        raw: Rohwert aus dem geparsten Frontmatter oder aus einem YAML-Dict.

    Returns:
        Die rohen String-Einträge (noch nicht entschlüsselt/normalisiert).

    Raises:
        UnsupportedOberthemaValue: Bei `RawYamlBlock`, Flow-Mapping/-Liste,
            Nicht-String-Listeneinträgen oder anderen Python-Typen.

    Example::

        parse_oberthema_field("[[11.1 Potenzen]]")    # -> ["[[11.1 Potenzen]]"]
        parse_oberthema_field(["A", "B"])             # -> ["A", "B"]
        parse_oberthema_field(RawYamlBlock(("  a: b",)))  # raises (yaml_registry)
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        if _FLOW_MAPPING_RE.match(raw) or _FLOW_SEQUENCE_RE.match(raw):
            raise UnsupportedOberthemaValue(f"Nicht unterstützter Oberthema-Wert: {raw!r}")
        return [raw] if raw.strip() else []
    if isinstance(raw, list):
        if not all(isinstance(item, str) for item in raw):
            raise UnsupportedOberthemaValue(f"Oberthema-Liste mit Nicht-Text-Einträgen: {raw!r}")
        return list(raw)
    raise UnsupportedOberthemaValue(f"Nicht unterstützter Oberthema-Typ: {type(raw).__name__}")


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def normalize_oberthemen(entries: Iterable[str], group_name: str) -> list[str]:
    """Setzt die Invarianten auf einer String-Liste durch.

    Entschlüsselt Wiki-Links (inkl. Lerngruppen-Präfix, siehe
    `strip_group_prefixed_link`), normalisiert Whitespace und entfernt leere
    Einträge sowie Duplikate (erstes Vorkommen gewinnt).

    Args:
        entries: Rohe oder bereits entschlüsselte Einträge.
        group_name: Lerngruppen-Bezeichnung des Kurses (darf ein Wiki-Link sein).

    Returns:
        Die entschlüsselte, duplikatfreie Themenliste in Eingabereihenfolge.

    Example::

        normalize_oberthemen(["[[11.1 A]]", " A ", "", "B"], "11.1")
        # -> ["A", "B"]
    """
    result: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        topic = _normalize_whitespace(strip_group_prefixed_link(str(entry or ""), group_name))
        if not topic or topic in seen:
            continue
        seen.add(topic)
        result.append(topic)
    return result


def encode_oberthemen(topics: Iterable[str], group_name: str) -> list[str]:
    """Erzeugt die kanonische LZK-Schreibform ``[[gruppe thema]]`` je Thema.

    Normalisiert die Eingabe vorher (`normalize_oberthemen`), sodass auch
    bereits kodierte oder doppelte Einträge sicher verarbeitet werden.

    Example::

        encode_oberthemen(["Potenzen"], "[[11.1]]")  # -> ["[[11.1 Potenzen]]"]
    """
    group_plain = strip_wiki_link(str(group_name or "").strip())
    encoded: list[str] = []
    for topic in normalize_oberthemen(topics, group_name):
        stem = f"{group_plain} {topic}".strip() if group_plain else topic
        encoded.append(f"[[{stem}]]")
    return encoded


def canonical_oberthema_value(raw: object, group_name: str) -> list[str]:
    """Kanonische LZK-Schreibform eines Rohwerts: ``encode(normalize(parse(raw)))``.

    Raises:
        UnsupportedOberthemaValue: Bei nicht unterstütztem Typ (wird nie umgedeutet).
    """
    return encode_oberthemen(parse_oberthema_field(raw), group_name)


def distinct_raw_entries(raw: object) -> list[str]:
    """Rohe, getrimmte Einträge ohne Leer-/Doppeleinträge (ohne Entschlüsselung).

    Für Einzelwert-Stundentypen (Unterricht/Hospitation), deren ``Oberthema``
    so gespeichert bleibt, wie es eingegeben wurde.

    Raises:
        UnsupportedOberthemaValue: Bei nicht unterstütztem Typ.
    """
    result: list[str] = []
    seen: set[str] = set()
    for entry in parse_oberthema_field(raw):
        text = _normalize_whitespace(entry)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def read_oberthema_state(yaml_data: dict[str, object], group_name: str) -> OberthemaState:
    """Zentraler Lesepfad: Themenliste plus getrennt festgehaltener Fehlerzustand.

    Schreibt nichts und deutet nichts um. Aufrufer, die "leer" und "ungültig"
    unterscheiden müssen (Grid, Sequenz-Sync, LZK-Export, Migration), prüfen
    `OberthemaState.is_invalid`.

    Args:
        yaml_data: YAML-Dict einer Stunden-Datei.
        group_name: Lerngruppen-Bezeichnung des Kurses.
    """
    raw = yaml_data.get(OBERTHEMA_KEY) if isinstance(yaml_data, dict) else None
    try:
        entries = parse_oberthema_field(raw)
    except UnsupportedOberthemaValue:
        return OberthemaState(topics=(), invalid_raw=raw)
    return OberthemaState(topics=tuple(normalize_oberthemen(entries, group_name)))


def read_yaml_oberthemen(yaml_data: dict[str, object], group_name: str) -> list[str]:
    """Nur die gültigen Themen (``read_oberthema_state(...).topics``) als Liste."""
    return list(read_oberthema_state(yaml_data, group_name).topics)


def ensure_oberthema_write_allowed(on_disk_raw: object, new_raw: object, *, repair: bool) -> None:
    """Schreib-Invariante: ein ungültiger Plattenwert wird nie still überschrieben.

    * Plattenwert gültig → keine Einschränkung.
    * Plattenwert ungültig und neuer Wert unverändert → erlaubt (andere Felder
      dürfen sich ändern, das ungültige Oberthema wird durchgereicht).
    * Plattenwert ungültig, neuer Wert anders, ohne ``repair`` →
      `OberthemaRepairRequired`.

    Args:
        on_disk_raw: Aktueller Rohwert in der Datei (nicht kanonisiert).
        new_raw: Wert, der geschrieben würde.
        repair: ``True`` nur bei ausdrücklicher Korrektur (bewusstes Speichern
            der Oberthema-Zelle).

    Raises:
        OberthemaRepairRequired: Wenn die Invariante verletzt würde.
    """
    if repair or not is_unsupported_oberthema_value(on_disk_raw):
        return
    if new_raw == on_disk_raw:
        return
    raise OberthemaRepairRequired(
        "Das Oberthema dieser Einheit hat ein ungültiges Format und wird nicht automatisch "
        "überschrieben. Bitte das Oberthema zuerst korrigieren (Oberthema-Zelle neu setzen)."
    )
