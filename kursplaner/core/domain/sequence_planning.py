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
    """Build the canonical sequence file stem ``<Sequenz> <Gruppe> <26-2>``."""
    normalized_halfyear = normalize_halfyear_token(halfyear_token)
    sequence_part = sanitize_hour_title(str(sequence_name or "").strip()) or "Sequenz"
    group_plain = strip_wiki_link(str(group_name or "").strip())
    group_part = sanitize_hour_title(group_plain) or "Lerngruppe"
    return f"{sequence_part} {group_part} {normalized_halfyear}".strip()


def sequence_directory_for_plan(table: PlanTableData) -> Path:
    """Return the sequence directory for one course plan."""
    return table.markdown_path.parent / SEQUENCE_DIR_NAME


def course_plan_wiki_link(table: PlanTableData) -> str:
    """Build the ``Kursplan`` wiki-link value for sequence frontmatter."""
    return build_wiki_link(table.markdown_path.stem)
