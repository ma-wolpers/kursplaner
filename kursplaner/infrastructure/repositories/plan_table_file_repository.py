from __future__ import annotations

import re
from pathlib import Path

from bw_libs.app_paths import atomic_write_text
from bw_libs.safe_read import read_or_default
from kursplaner.core.domain.lesson_directory import (
    LESSON_DIR_ARCHIVE,
    managed_lesson_dir_names,
    resolve_lesson_dir,
)
from kursplaner.core.domain.lesson_naming import generate_random_lesson_stem
from kursplaner.core.domain.lesson_yaml_policy import (
    allowed_keys_for_type,
    canonicalize_lesson_yaml,
    infer_stundentyp,
)
from kursplaner.core.domain.plan_table import LessonYamlData, PlanTableData, sanitize_hour_title
from kursplaner.core.domain.wiki_links import build_wiki_link, strip_wiki_link
from kursplaner.core.domain.yaml_registry import LESSON_SCHEMA, parse_yaml_frontmatter
from kursplaner.infrastructure.repositories.plan_table_markdown_io import (
    PLAN_DATE_RE,
    _parse_plan_metadata,
    load_last_plan_table,
    save_plan_table,
)

__all__ = [
    "PLAN_DATE_RE",
    "load_last_plan_table",
    "save_plan_table",
    "load_linked_lesson_yaml",
    "save_linked_lesson_yaml",
    "create_linked_lesson_file",
    "sync_thema_ausfall_to_plan_row",
    "set_lesson_markdown_sections",
    "get_row_link_path",
    "validate_managed_markdown_yaml",
]

LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
WIKI_LINK_VALUE_RE = re.compile(r"^\s*\[\[[^\]]+\]\]\s*$")
MARKDOWN_LINK_VALUE_RE = re.compile(r"^\s*\[[^\]]+\]\([^\)]+\.md\)\s*$", re.IGNORECASE)


def _resolve_hours_link(plan_path: Path, content: str) -> Path | None:
    match = LINK_RE.search(content)
    if not match:
        return None

    target = match.group(1).split("|", 1)[0].strip()
    if not target:
        return None

    if not target.endswith(".md"):
        target += ".md"

    candidate = (plan_path.parent / target).resolve()
    if candidate.exists() and candidate.is_file():
        return candidate

    target_lower = target.lower()
    managed_prefixes = tuple(f"{name.lower()}/" for name in managed_lesson_dir_names())
    if not target_lower.startswith(managed_prefixes):
        for dir_name in managed_lesson_dir_names():
            alt = (plan_path.parent / dir_name / target).resolve()
            if alt.exists() and alt.is_file():
                return alt

    return None


def _parse_yaml_frontmatter(path: Path) -> tuple[dict[str, object], str]:
    text = path.read_text(encoding="utf-8")
    return parse_yaml_frontmatter(text, LESSON_SCHEMA, source_label=str(path))


def validate_managed_markdown_yaml(base_dir: Path):
    if not base_dir.exists() or not base_dir.is_dir():
        raise RuntimeError(f"Unterrichtsordner fehlt oder ist ungültig: {base_dir}")

    for child in sorted(base_dir.iterdir(), key=lambda item: item.name.lower()):
        if not child.is_dir():
            continue

        plan_md = child / f"{child.name}.md"
        if not plan_md.exists() or not plan_md.is_file():
            raise RuntimeError(f"Fehlende Plan-Datei im Unterrichtsordner: {child}\nErwartet: {plan_md.name}")

        _parse_plan_metadata(plan_md)
        table = load_last_plan_table(plan_md)
        header_map = {name.lower(): idx for idx, name in enumerate(table.headers)}
        idx_inhalt = header_map.get("inhalt")
        if idx_inhalt is None:
            continue

        checked_links: set[Path] = set()
        for row in table.rows:
            if idx_inhalt >= len(row):
                continue
            content = row[idx_inhalt].strip()
            if not LINK_RE.search(content):
                continue
            link_path = _resolve_hours_link(plan_md, content)
            if not isinstance(link_path, Path):
                continue
            resolved = link_path.resolve()
            if resolved in checked_links:
                continue
            checked_links.add(resolved)
            _parse_yaml_frontmatter(link_path)


def _render_yaml_frontmatter(data: dict[str, object]) -> str:
    canonical = canonicalize_lesson_yaml(data)
    ordered_keys = allowed_keys_for_type(infer_stundentyp(canonical))

    lines = ["---"]
    for key in ordered_keys:
        if key not in canonical:
            continue

        value = canonical[key]
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f'  - "{str(item)}"')
        else:
            value_text = str(value)
            if WIKI_LINK_VALUE_RE.fullmatch(value_text) or MARKDOWN_LINK_VALUE_RE.fullmatch(value_text):
                escaped = value_text.replace('"', '\\"')
                lines.append(f'{key}: "{escaped}"')
            else:
                lines.append(f"{key}: {value_text}")

    lines.append("---")
    return "\n".join(lines) + "\n\n"


def get_row_link_path(table: PlanTableData, row_index: int) -> Path | None:
    if row_index < 0 or row_index >= len(table.rows):
        return None

    header_map = {name.lower(): idx for idx, name in enumerate(table.headers)}
    idx_inhalt = header_map.get("inhalt")
    if idx_inhalt is None:
        return None

    return _resolve_hours_link(table.markdown_path, table.rows[row_index][idx_inhalt])


def load_linked_lesson_yaml(path: Path) -> LessonYamlData:
    data, _ = _parse_yaml_frontmatter(path)
    normalized = canonicalize_lesson_yaml(data, topic_hint=path.stem)
    return LessonYamlData(lesson_path=path, data=normalized)


def save_linked_lesson_yaml(lesson: LessonYamlData):
    body = ""
    if lesson.lesson_path.exists():
        raw = lesson.lesson_path.read_text(encoding="utf-8")
        body = raw
        parsed_raw = read_or_default(lambda: _parse_yaml_frontmatter(lesson.lesson_path)[1], default=None)
        if parsed_raw is not None:
            body = parsed_raw
            if parsed_raw.startswith("---\n"):
                end = parsed_raw.find("\n---", 4)
                if end != -1:
                    body = parsed_raw[end + 4 :]
                    body = body.lstrip("\n")

    normalized = canonicalize_lesson_yaml(lesson.data, topic_hint=lesson.lesson_path.stem)
    frontmatter = _render_yaml_frontmatter(normalized)
    atomic_write_text(lesson.lesson_path, frontmatter + body, encoding="utf-8")


def create_linked_lesson_file(
    plan_table: PlanTableData,
    row_index: int,
    lesson_topic: str,
    default_hours: int,
) -> Path:
    """Legt eine neue Stundendatei mit Zufallsstem an und verknüpft sie in der Plantabelle.

    Der Dateiname besteht aus einem eindeutigen 6-stelligen Zufallscode aus
    ``[a-z0-9]`` (z. B. ``md38md.md``), der global über beide Einheitenordner
    (``Einheiten/`` und ``Alteinheiten/``) eindeutig ist.

    Args:
        plan_table: Planungstabelle, in die der Link eingetragen wird.
        row_index: Index der Tabellenzeile, die den Link erhalten soll.
        lesson_topic: Fachlicher Stundenthemen-Titel (wird ins YAML geschrieben).
        default_hours: Stundenzahl als Standardwert im YAML-Feld ``Dauer``.

    Returns:
        Pfad der neu angelegten Stundendatei.
    """
    plan_dir = plan_table.markdown_path.parent
    stunden_dir = resolve_lesson_dir(plan_dir, create_if_missing=True)

    existing_stems = {p.stem for p in stunden_dir.glob("*.md")}
    archive_dir = plan_dir / LESSON_DIR_ARCHIVE
    if archive_dir.exists():
        existing_stems |= {p.stem for p in archive_dir.glob("*.md")}

    new_stem = generate_random_lesson_stem(existing_stems)
    candidate = stunden_dir / f"{new_stem}.md"
    title = sanitize_hour_title(lesson_topic) or "einheit"

    initial: dict[str, object] = {
        "Stundentyp": "Unterricht",
        "Dauer": str(default_hours),
        "Stundenthema": title,
        "Oberthema": "",
        "Stundenziel": "",
        "Teilziele": [],
        "Kompetenzen": [],
        "Material": [],
    }
    lesson = LessonYamlData(lesson_path=candidate, data=initial)
    save_linked_lesson_yaml(lesson)

    header_map = {name.lower(): idx for idx, name in enumerate(plan_table.headers)}
    idx_inhalt = header_map.get("inhalt")
    idx_thema_ausfall = header_map.get("thema/ausfall")
    if idx_inhalt is not None and 0 <= row_index < len(plan_table.rows):
        link_text = build_wiki_link(candidate.stem)
        if link_text:
            plan_table.rows[row_index][idx_inhalt] = link_text
    if idx_thema_ausfall is not None and 0 <= row_index < len(plan_table.rows):
        row = plan_table.rows[row_index]
        if idx_thema_ausfall < len(row):
            row[idx_thema_ausfall] = ""

    return candidate


def sync_thema_ausfall_to_plan_row(
    table: PlanTableData,
    row_index: int,
    yaml_data: dict[str, object],
    group_name: str,
) -> None:
    """Aktualisiert die Thema/Ausfall-Spalte einer Planzeile anhand der YAML-Stundendaten.

    Ermittelt aus ``Stundentyp`` und ``Oberthema`` im YAML-Dictionary den
    Inhalt der vierten Planungsspalte und schreibt ihn direkt in die Zeile.
    Die Persistenz liegt beim Aufrufer (dieser ruft anschließend
    :func:`save_plan_table` auf).

    Zuordnungsregeln:
    * Unterricht / Hospitation mit Oberthema → ``[[gruppe oberthema]]``
    * LZK mit Oberthema                      → ``LZK [[gruppe oberthema]]``
    * Ausfall                                → Feld unverändert lassen
    * Kein Oberthema                         → Feld leeren

    Args:
        table: Planungstabelle, deren Zeile aktualisiert wird.
        row_index: Index der zu aktualisierenden Zeile in ``table.rows``.
        yaml_data: Normalisiertes YAML-Dictionary der verlinkten Stundendatei,
            z. B. aus :func:`load_linked_lesson_yaml`.
        group_name: Lerngruppen-Bezeichnung; darf als Wiki-Link vorliegen
            (z. B. ``"[[li2]]"``) und wird automatisch bereinigt.

    Example::

        sync_thema_ausfall_to_plan_row(
            table,
            row_index=2,
            yaml_data={"Stundentyp": "Unterricht", "Oberthema": "Kodierung"},
            group_name="[[li2]]",
        )
        # → table.rows[2][3] == "[[li2 Kodierung]]"
    """
    if row_index < 0 or row_index >= len(table.rows):
        return
    header_map = {name.lower(): idx for idx, name in enumerate(table.headers)}
    idx_thema_ausfall = header_map.get("thema/ausfall")
    if idx_thema_ausfall is None:
        return
    row = table.rows[row_index]
    if idx_thema_ausfall >= len(row):
        return

    stundentyp = str(yaml_data.get("Stundentyp", "Unterricht")).strip()
    oberthema = str(yaml_data.get("Oberthema", "")).strip()
    group_plain = strip_wiki_link(str(group_name or "").strip())

    if stundentyp == "Ausfall":
        return

    if not oberthema:
        row[idx_thema_ausfall] = ""
        return

    seq_stem = f"{group_plain} {oberthema}"
    if stundentyp == "LZK":
        row[idx_thema_ausfall] = f"LZK [[{seq_stem}]]"
    else:
        row[idx_thema_ausfall] = f"[[{seq_stem}]]"


def set_lesson_markdown_sections(
    lesson_path: Path,
    inhalte_refs: list[str],
    methodik_refs: list[str],
):
    text = lesson_path.read_text(encoding="utf-8") if lesson_path.exists() else ""
    body = text

    if body.startswith("---\n"):
        end = body.find("\n---", 4)
        if end != -1:
            body = body[end + 4 :]
            body = body.lstrip("\n")

    cleaned_body = body.strip()
    sections: list[str] = []

    if inhalte_refs:
        lines = ["## Inhalte", ""]
        lines.extend(f"- {build_wiki_link(ref)}" for ref in inhalte_refs)
        sections.append("\n".join(lines))

    if methodik_refs:
        lines = ["## Methodik", ""]
        lines.extend(f"- {build_wiki_link(ref)}" for ref in methodik_refs)
        sections.append("\n".join(lines))

    composed = cleaned_body
    if sections:
        suffix = "\n\n".join(sections)
        composed = f"{cleaned_body}\n\n{suffix}".strip() if cleaned_body else suffix

    frontmatter = _render_yaml_frontmatter(load_linked_lesson_yaml(lesson_path).data)
    output = frontmatter + (composed + "\n" if composed else "")
    atomic_write_text(lesson_path, output, encoding="utf-8")
