from __future__ import annotations

import re
from pathlib import Path

from kursplaner.core.domain.plan_table import PlanTableData, sanitize_hour_title
from kursplaner.core.domain.wiki_links import build_wiki_link, strip_wiki_link

SEQUENCE_DIR_NAME = "Sequenzen"
SEQUENCE_YAML_COURSE_PLAN_KEY = "Kursplan"

_HALFYEAR_RE = re.compile(r"\b(\d{2}-[12])\b")


def normalize_halfyear_token(value: str) -> str:
    """Validate and normalize halfyear tokens like ``26-2``."""
    token = str(value or "").strip()
    match = _HALFYEAR_RE.fullmatch(token)
    if match is None:
        raise RuntimeError("Halbjahr muss als Token im Format '26-1' oder '26-2' vorliegen.")
    return match.group(1)


def extract_halfyear_token_from_table(table: PlanTableData) -> str:
    """Resolve the halfyear token from plan directory or plan file name."""
    candidates = (table.markdown_path.parent.name, table.markdown_path.stem)
    for candidate in candidates:
        match = _HALFYEAR_RE.search(str(candidate))
        if match is not None:
            return match.group(1)
    raise RuntimeError("Halbjahr konnte aus dem Kursnamen nicht bestimmt werden (erwartet z. B. '26-2').")


def build_sequence_stem(*, sequence_name: str, group_name: str, halfyear_token: str) -> str:
    """Baut den kanonischen Stem einer Sequenz-Markdown-Datei.

    Das Format ist ``<Gruppe> <Sequenzname>`` – ohne Halbjahr, damit dieselbe
    thematische Sequenz kursübergreifend auf dieselbe Brainstorming-Datei zeigt.
    Der Parameter ``halfyear_token`` wird formal behalten, damit bestehende
    Aufrufer nicht geändert werden müssen, hat aber keinen Einfluss auf das
    Ergebnis.

    Args:
        sequence_name: Fachlicher Name der Sequenz (z. B. ``"Kodierung"``).
        group_name: Lerngruppen-Bezeichnung; darf als Wiki-Link vorliegen
            (z. B. ``"[[li2]]"``), wird automatisch bereinigt.
        halfyear_token: Wird ignoriert; nur aus Kompatibilitätsgründen vorhanden.

    Returns:
        Stem-String der Form ``"li2 Kodierung"``.

    Example::

        build_sequence_stem(sequence_name="Kodierung",
                            group_name="[[li2]]",
                            halfyear_token="26-2")
        # → "li2 Kodierung"
    """
    sequence_part = sanitize_hour_title(str(sequence_name or "").strip()) or "Sequenz"
    group_plain = strip_wiki_link(str(group_name or "").strip())
    group_part = sanitize_hour_title(group_plain) or "Lerngruppe"
    return f"{group_part} {sequence_part}".strip()


def sequence_directory_for_plan(table: PlanTableData) -> Path:
    """Return the sequence directory for one course plan."""
    return table.markdown_path.parent / SEQUENCE_DIR_NAME


def course_plan_wiki_link(table: PlanTableData) -> str:
    """Build the ``Kursplan`` wiki-link value for sequence frontmatter."""
    return build_wiki_link(table.markdown_path.stem)
