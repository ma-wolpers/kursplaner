from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from kursplaner.core.domain.course_subject import normalize_course_subject


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
    required_keys=("Lerngruppe", "Kursfach", "Stufe"),
    non_empty_keys=("Lerngruppe", "Kursfach", "Stufe"),
    value_validators={
        "Lerngruppe": _is_valid_lerngruppe,
        "Kursfach": _is_valid_kursfach,
        "Stufe": _is_valid_stufe,
    },
)

LESSON_SCHEMA = YamlSchema(
    label="Stunden-Datei",
    required_keys=("Stundentyp", "Dauer", "Stundenthema"),
    non_empty_keys=("Stundentyp", "Dauer", "Stundenthema"),
    value_validators={
        "Stundentyp": _is_valid_stundentyp,
        "Dauer": _is_valid_dauer,
    },
)


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
        raise RuntimeError(f"Fehlende YAML-Felder in {schema.label}: {source_label}\nFehlend: {', '.join(missing)}")

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
