from __future__ import annotations

import re
from pathlib import Path

from bw_libs.app_paths import atomic_write_text
from bw_libs.safe_read import read_or_default
from kursplaner.core.domain.course_subject import normalize_course_subject
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
from kursplaner.core.domain.yaml_registry import (
    LESSON_SCHEMA,
    PLAN_METADATA_SCHEMA,
    parse_yaml_frontmatter,
)

LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
PLAN_DATE_RE = re.compile(r"\d{2}-\d{2}-\d{2}")
WIKI_LINK_VALUE_RE = re.compile(r"^\s*\[\[[^\]]+\]\]\s*$")
MARKDOWN_LINK_VALUE_RE = re.compile(r"^\s*\[[^\]]+\]\([^\)]+\.md\)\s*$", re.IGNORECASE)



def _split_row(row_line: str) -> list[str]:
    """Teilt eine Markdown-Tabellenzeile in Zellen auf."""
    line = row_line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


def _is_separator_row(row_line: str) -> bool:
    line = row_line.strip()
    if not line.startswith("|"):
        return False
    parts = _split_row(line)
    if not parts:
        return False
    return all(re.fullmatch(r":?-{3,}:?", part or "") for part in parts)


def _extract_table_blocks(lines: list[str]) -> list[tuple[int, int]]:
    blocks: list[tuple[int, int]] = []
    start = None

    for idx, line in enumerate(lines):
        stripped = line.strip()
        is_row = stripped.startswith("|") and "|" in stripped[1:]
        if is_row:
            if start is None:
                start = idx
        else:
            if start is not None:
                if idx - start >= 2:
                    blocks.append((start, idx - 1))
                start = None

    if start is not None and len(lines) - start >= 2:
        blocks.append((start, len(lines) - 1))

    return blocks


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


def _parse_plan_metadata(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    metadata, _ = parse_yaml_frontmatter(text, PLAN_METADATA_SCHEMA, source_label=str(path))
    normalized = {key: str(value) for key, value in metadata.items()}

    kursfach_raw = normalized.get("Kursfach", "").strip()
    try:
        normalized["Kursfach"] = normalize_course_subject(kursfach_raw)
    except ValueError:
        raise RuntimeError(
            "Ungueltiges YAML-Feld 'Kursfach' in Plan-Datei: "
            f"{path}\n"
            f"Gefunden: '{kursfach_raw}'\n"
            "Erlaubt sind nur standardisierte Kursfach-Werte: Informatik, Mathematik, Darstellendes Spiel."
        )

    return normalized


def _validate_plan_rows(rows: list[list[str]], source_label: str) -> None:
    """Validiert zentrale Tabelleninvarianten fuer Datum/Stunden hart."""
    for index, row in enumerate(rows, start=1):
        if len(row) < 4:
            raise RuntimeError(f"Ungueltige Tabellenzeile in {source_label}: Zeile {index} hat weniger als 4 Spalten.")

        date_text = str(row[0]).strip()
        if not PLAN_DATE_RE.fullmatch(date_text):
            raise RuntimeError(
                f"Ungueltiges Datum in {source_label}: Zeile {index} ('{date_text}'). Erwartet DD-MM-YY."
            )

        hours_text = str(row[1]).strip()
        if not hours_text.isdigit():
            raise RuntimeError(
                f"Ungueltige Stundenangabe in {source_label}: Zeile {index} ('{hours_text}'). Erwartet 0-4."
            )

        hours = int(hours_text)
        if hours < 0 or hours > 4:
            raise RuntimeError(f"Ungueltige Stundenanzahl in {source_label}: Zeile {index} ('{hours}'). Erlaubt 0-4.")


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


def load_last_plan_table(markdown_path: Path) -> PlanTableData:
    text = markdown_path.read_text(encoding="utf-8")
    had_trailing_newline = text.endswith("\n")
    lines = text.splitlines()

    metadata = _parse_plan_metadata(markdown_path)

    blocks = _extract_table_blocks(lines)
    if not blocks:
        raise RuntimeError("Keine Markdown-Tabelle in der Datei gefunden.")

    selected = None
    headers: list[str] = []

    for start, end in blocks:
        head = _split_row(lines[start])
        if start + 1 > end or not _is_separator_row(lines[start + 1]):
            continue

        lowered = [cell.lower().strip() for cell in head]
        if lowered == ["datum", "stunden", "inhalt", "thema/ausfall"]:
            selected = (start, end)
            headers = head

    if selected is None:
        raise RuntimeError(
            "Keine gültige Planungstabelle gefunden. "
            "Erwartet wird exakt: Datum | Stunden | Inhalt | Thema/Ausfall"
        )

    start, end = selected
    body_lines = lines[start + 2 : end + 1]
    rows = [_split_row(line) for line in body_lines]

    expected_len = len(headers)
    normalized_rows: list[list[str]] = []
    for row in rows:
        if len(row) < expected_len:
            row = row + [""] * (expected_len - len(row))
        elif len(row) > expected_len:
            row = row[:expected_len]
        normalized_rows.append(row)

    _validate_plan_rows(normalized_rows, str(markdown_path))

    return PlanTableData(
        markdown_path=markdown_path,
        headers=headers,
        rows=normalized_rows,
        start_line=start,
        end_line=end,
        source_lines=lines,
        had_trailing_newline=had_trailing_newline,
        metadata=metadata,
    )


def _render_table(table: PlanTableData) -> list[str]:
    headers = table.headers
    separator = ["---"] * len(headers)

    output = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(separator) + " |",
    ]

    for row in table.rows:
        safe = [cell.replace("\n", " ").strip() for cell in row]
        output.append("| " + " | ".join(safe) + " |")

    return output


def save_plan_table(table: PlanTableData):
    _validate_plan_rows(table.rows, str(table.markdown_path))
    rendered = _render_table(table)
    updated_lines = table.source_lines[: table.start_line] + rendered + table.source_lines[table.end_line + 1 :]
    output = "\n".join(updated_lines)
    if table.had_trailing_newline:
        output += "\n"
    atomic_write_text(table.markdown_path, output, encoding="utf-8")


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
