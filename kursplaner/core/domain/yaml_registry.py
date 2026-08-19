from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Sequence

from kursplaner.core.domain.course_rhythm import is_valid_rhythm_value
from kursplaner.core.domain.course_subject import normalize_course_subject
from kursplaner.core.domain.sequence_planning import SEQUENCE_YAML_COURSE_PLAN_KEY

WIKI_LINK_VALUE_RE = re.compile(r"^\s*\[\[[^\]]+\]\]\s*$")
MARKDOWN_LINK_VALUE_RE = re.compile(r"^\s*\[[^\]]+\]\([^\)]+\.md\)\s*$", re.IGNORECASE)
"""Erkennen YAML-Skalarwerte, die selbst ein Wiki-/Markdown-Link sind.

Zentrale Ablösung der zuvor wortwörtlich duplizierten Definitionen in
`plan_table_file_repository.py` und `ub_repository.py` — genutzt von
`render_yaml_frontmatter()`, um solche Werte beim Rendern in Anführungszeichen
zu setzen (sonst würde YAML die eckigen Klammern als Flow-Sequence lesen).
"""


@dataclass(frozen=True)
class YamlSchema:
    """Beschreibt die Pflichtstruktur eines akzeptierten YAML-Frontmatters."""

    label: str
    required_keys: tuple[str, ...]
    non_empty_keys: tuple[str, ...] = ()
    value_validators: dict[str, Callable[[object], bool]] | None = None


def _is_valid_lerngruppe(value: object) -> bool:
    text = str(value or "").strip()
    return bool(re.fullmatch(r"\[\[[^\[\]\|]+\]\]", text))


def _is_valid_stufe(value: object) -> bool:
    text = str(value or "").strip()
    if not text.isdigit():
        return False
    number = int(text)
    return 1 <= number <= 13


def _is_valid_kursfach(value: object) -> bool:
    try:
        normalize_course_subject(str(value or ""))
        return True
    except ValueError:
        return False


def _is_valid_stundentyp(value: object) -> bool:
    return str(value or "").strip() in {"Unterricht", "LZK", "Hospitation", "Ausfall"}


def _is_valid_dauer(value: object) -> bool:
    text = str(value or "").strip()
    return text.isdigit() and int(text) > 0


PLAN_METADATA_SCHEMA = YamlSchema(
    label="Plan-Datei",
    required_keys=("Lerngruppe", "Kursfach", "Stufe", "Rhythmus"),
    non_empty_keys=("Lerngruppe", "Kursfach", "Stufe", "Rhythmus"),
    value_validators={
        "Lerngruppe": _is_valid_lerngruppe,
        "Kursfach": _is_valid_kursfach,
        "Stufe": _is_valid_stufe,
        "Rhythmus": is_valid_rhythm_value,
    },
)
"""Schema fuer die Plan-Datei-Frontmatter.

``Rhythmus`` traegt den wochentagsbezogenen Startzeit-/Stundenrhythmus des
Kurses als Liste von Zeilen im Format
``["ab" DD-MM-YY] Wochentag HH:MM Stunden`` (siehe
:mod:`kursplaner.core.domain.course_rhythm`), z. B.::

    Rhythmus:
      - "Mo 12:15 2"
      - "Mi 08:00 1"
      - "ab 20-04-26 Mo 14:00 1"

Er ist seit der Entfernung der ``Stunden``-Spalte aus der Plantabelle die
einzige Quelle fuer die Stundenzahl/Startzeit eines Kalendertags. Dateien im
alten Format ohne dieses Feld muessen mit
``tools/migrate_plan_table_schema.py`` migriert werden, bevor sie wieder
ladbar sind.
"""

LESSON_SCHEMA = YamlSchema(
    label="Stunden-Datei",
    required_keys=("Stundentyp", "Dauer", "Stundenthema"),
    non_empty_keys=("Stundentyp", "Dauer", "Stundenthema"),
    value_validators={
        "Stundentyp": _is_valid_stundentyp,
        "Dauer": _is_valid_dauer,
    },
)

SEQUENCE_PLAN_SCHEMA = YamlSchema(
    label="Sequenz-Datei",
    required_keys=(SEQUENCE_YAML_COURSE_PLAN_KEY, "Sequenzname", "Lerngruppe", "Halbjahr"),
)
"""Schema für die persistente Sequenz-Markdown-Datei (`Sequenzen/*.md`).

`Sequenzziel` und `Leitkompetenz` sind bewusst nicht in `required_keys`
aufgeführt: sie werden bei Neuanlage der Datei leer angelegt und erst später
vom Nutzer befüllt (siehe `FileSystemSequencePlanRepository`).
"""


def _is_empty_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, list):
        return len(value) == 0
    return not str(value).strip()


def parse_yaml_frontmatter(
    text: str, schema: YamlSchema, source_label: str = "<unbekannt>"
) -> tuple[dict[str, object], str]:
    """Parst und validiert YAML-Frontmatter gegen ein Schema.

    Invariante: Alle ``required_keys`` sind vorhanden; ``non_empty_keys`` sind nicht leer.
    Bei Verstoß wird ein ``RuntimeError`` mit Quellenhinweis ausgelöst.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise RuntimeError(
            f"Fehlendes YAML-Frontmatter in {schema.label}: {source_label}\n"
            "Erwartet wird ein YAML-Block am Dateianfang (--- ... ---)."
        )

    data: dict[str, object] = {}
    idx = 1
    key: str | None = None
    has_closing = False

    while idx < len(lines):
        line = lines[idx]
        if line.strip() == "---":
            has_closing = True
            break

        if re.match(r"^[A-Za-zÄÖÜäöüß].*:\s*", line):
            left, right = line.split(":", 1)
            key = left.strip()
            value = right.strip().strip('"')
            if value:
                data[key] = value
                key = None
            else:
                data[key] = []
        elif key and line.strip().startswith("-"):
            item = line.strip()[1:].strip().strip('"')
            if not isinstance(data.get(key), list):
                data[key] = []
            current_list = data[key]
            if not isinstance(current_list, list):
                current_list = []
                data[key] = current_list
            if item:
                current_list.append(item)

        idx += 1

    if not has_closing:
        raise RuntimeError(f"YAML-Frontmatter nicht geschlossen in Datei: {source_label}")

    missing = [yaml_key for yaml_key in schema.required_keys if yaml_key not in data]
    if missing:
        hint = (
            "\nBitte 'python tools/migrate_plan_table_schema.py' ausführen, um alte Plan-Dateien zu migrieren."
            if "Rhythmus" in missing
            else ""
        )
        raise RuntimeError(
            f"Fehlende YAML-Felder in {schema.label}: {source_label}\nFehlend: {', '.join(missing)}{hint}"
        )

    empty_required = [yaml_key for yaml_key in schema.non_empty_keys if _is_empty_value(data.get(yaml_key, ""))]
    if empty_required:
        raise RuntimeError(
            f"Leere YAML-Pflichtfelder in {schema.label}: {source_label}\nLeer: {', '.join(empty_required)}"
        )

    validators = schema.value_validators or {}
    invalid_values: list[str] = []
    for yaml_key, validator in validators.items():
        if yaml_key not in data:
            continue
        if not bool(validator(data[yaml_key])):
            invalid_values.append(yaml_key)
    if invalid_values:
        raise RuntimeError(
            f"Ungueltige YAML-Werte in {schema.label}: {source_label}\nFelder: {', '.join(invalid_values)}"
        )

    return data, text


def body_after_frontmatter(raw_text: str) -> str:
    """Liefert den Markdown-Body nach dem YAML-Frontmatter (ohne `---`-Block).

    Zentrale Ablösung der zuvor 3x unabhängig duplizierten Hand-Roll-Logik
    (`plan_table_file_repository.py::save_linked_lesson_yaml`/
    `.set_lesson_markdown_sections`, `ub_repository.py::load_ub_markdown`).
    Reine Funktion auf bereits eingelesenem Text — komponierbar mit
    `parse_yaml_frontmatter`s vorhandenem `(data, text)`-Rückgabewert
    (`body_after_frontmatter(parse_yaml_frontmatter(...)[1])`) oder direkt auf
    frisch gelesenem Rohtext, ohne `parse_yaml_frontmatter`s bestehende
    Signatur/Vertrag zu verändern. Kein Validator: liefert bei fehlendem oder
    unterminiertem Frontmatter einfach den Text unverändert zurück, statt zu
    werfen — Validierung ist Aufgabe von `parse_yaml_frontmatter`.

    Args:
        raw_text: Vollständiger Dateiinhalt inkl. Frontmatter, oder Text ohne
            Frontmatter (wird dann unverändert zurückgegeben).

    Returns:
        Der Body-Text ohne führende Leerzeilen.

    Example::

        body_after_frontmatter("---\\nStundenthema: X\\n---\\n\\nBody")
        # -> "Body"
    """
    if not raw_text.startswith("---\n"):
        return raw_text
    end = raw_text.find("\n---", 4)
    if end == -1:
        return raw_text
    return raw_text[end + 4 :].lstrip("\n")


def _yaml_scalar_line(key: str, value: object) -> str:
    """Rendert eine einzelne skalare YAML-Zeile, mit Link-Escaping bei Bedarf."""
    text = "true" if value is True else "false" if value is False else str(value or "")
    if WIKI_LINK_VALUE_RE.fullmatch(text) or MARKDOWN_LINK_VALUE_RE.fullmatch(text):
        escaped = text.replace('"', '\\"')
        return f'{key}: "{escaped}"'
    return f"{key}: {text}"


def render_yaml_frontmatter(ordered_keys: Sequence[str], values: dict[str, object]) -> str:
    """Rendert einen YAML-Frontmatter-Block aus geordneten Schlüsseln + Werten.

    Zentrale Ablösung der zuvor 2x unabhängig duplizierten Renderer
    (`plan_table_file_repository.py::_render_yaml_frontmatter`,
    `ub_repository.py::FileSystemUbRepository._render_yaml_frontmatter`)
    inklusive der dort ebenfalls doppelt definierten
    `WIKI_LINK_VALUE_RE`/`MARKDOWN_LINK_VALUE_RE`. Übernimmt nur die reine
    Rendering-Mechanik (Listenwerte als ``key:\\n  - "x"``, Skalare als
    ``key: value``/``key: "escaped"``); welche Keys in welcher Reihenfolge
    gerendert werden, bleibt bewusst Aufrufer-Entscheidung (Lesson-Seite:
    `canonicalize_lesson_yaml`+`allowed_keys_for_type`, Stundentyp-abhängig;
    UB-Seite: feste 4-Key-Tuple) — diese Policy wird hier nicht dupliziert,
    nur die gemeinsame Zeilen-Komposition.

    Args:
        ordered_keys: Zu rendernde Keys, in Ausgabereihenfolge.
        values: Dict mit den Werten; fehlende Keys werden übersprungen. Ein
            Aufrufer, der jeden Key immer rendern will (unabhängig davon, ob
            er im Quelldict vorkommt), muss `values` vorab entsprechend
            vorbefüllen (z. B. per `{k: data.get(k, "") for k in keys}`).

    Returns:
        Frontmatter-Block inkl. öffnendem/schließendem `---` und
        abschließender Leerzeile, bereit zur Konkatenation mit dem Body.

    Example::

        render_yaml_frontmatter(["Stundentyp", "Kompetenzen"], {"Stundentyp": "LZK", "Kompetenzen": ["PK1"]})
        # -> '---\\nStundentyp: LZK\\nKompetenzen:\\n  - "PK1"\\n---\\n\\n'
    """
    lines = ["---"]
    for key in ordered_keys:
        if key not in values:
            continue
        value = values[key]
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines.extend(f'  - "{item}"' for item in value)
        else:
            lines.append(_yaml_scalar_line(key, value))
    lines.append("---")
    return "\n".join(lines) + "\n\n"
