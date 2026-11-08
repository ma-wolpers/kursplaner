from __future__ import annotations

from pathlib import Path

from bw_libs.app_paths import atomic_write_text
from bw_libs.safe_read import read_or_default
from kursplaner.core.domain.lesson_directory import (
    LESSON_DIR_ARCHIVE,
    managed_lesson_dir_names,
    resolve_lesson_dir,
)
from kursplaner.core.domain.lesson_files import BLATTWERK_MARKER_KEY, lesson_stems, resolve_lesson_file
from kursplaner.core.domain.lesson_naming import generate_random_lesson_stem
from kursplaner.core.domain.lesson_yaml_policy import (
    allowed_keys_for_type,
    canonicalize_lesson_yaml,
    infer_stundentyp,
)
from kursplaner.core.domain.oberthema_values import (
    OBERTHEMA_KEY,
    ensure_oberthema_write_allowed,
    read_oberthema_state,
)
from kursplaner.core.domain.plan_table import (
    COLUMN_INHALT,
    COLUMN_THEMA_AUSFALL,
    LessonYamlData,
    PlanTableData,
)
from kursplaner.core.domain.wiki_links import build_dataview_lesson_link, first_wiki_link, strip_wiki_link
from kursplaner.core.domain.yaml_registry import (
    LESSON_SCHEMA,
    body_after_frontmatter,
    parse_yaml_frontmatter,
    render_yaml_frontmatter,
)
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
    "load_raw_linked_lesson_frontmatter",
    "create_linked_lesson_file",
    "new_lesson_path",
    "sync_thema_ausfall_to_plan_row",
    "get_row_link_path",
    "validate_managed_markdown_yaml",
]


def _resolve_hours_link(plan_path: Path, content: str) -> Path | None:
    link = first_wiki_link(content)
    target = link[0] if link is not None else ""
    if not target:
        return None

    # Ziel ohne Endung: `.md`, dann `.ebw` (Blattwerk-Kurzentwurf), siehe `lesson_files`.
    candidate = resolve_lesson_file(plan_path.parent, target)
    if candidate is not None:
        return candidate

    target_lower = target.lower()
    managed_prefixes = tuple(f"{name.lower()}/" for name in managed_lesson_dir_names())
    if not target_lower.startswith(managed_prefixes):
        for dir_name in managed_lesson_dir_names():
            alt = resolve_lesson_file(plan_path.parent / dir_name, target)
            if alt is not None:
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
        idx_inhalt = table.column_index_optional(COLUMN_INHALT)
        if idx_inhalt is None:
            continue

        checked_links: set[Path] = set()
        for row in table.rows:
            if idx_inhalt >= len(row):
                continue
            content = row[idx_inhalt].strip()
            if first_wiki_link(content) is None:
                continue
            link_path = _resolve_hours_link(plan_md, content)
            if not isinstance(link_path, Path):
                continue
            resolved = link_path.resolve()
            if resolved in checked_links:
                continue
            checked_links.add(resolved)
            _parse_yaml_frontmatter(link_path)


def _render_yaml_frontmatter(data: dict[str, object], *, blattwerk_marker: object = None) -> str:
    """Rendert die Lesson-Frontmatter mit Stundentyp-abhängiger Schlüsselauswahl.

    Dünner Wrapper um die zentrale `yaml_registry.render_yaml_frontmatter` —
    nur die Lesson-spezifische Policy (welche Keys, in welcher Reihenfolge)
    lebt hier, die Rendering-Mechanik selbst ist zentralisiert.

    Args:
        data: Lesson-YAML (wird kanonisiert).
        blattwerk_marker: Wert von ``document_type`` aus der Datei auf der
            Platte. Ist er ein nicht-leerer String, wird er als letzte Zeile
            unverändert durchgereicht, damit Blattwerk-Kurzentwürfe (``.ebw``)
            ihren Pflicht-Marker beim Speichern im Kursplaner behalten.
    """
    canonical = canonicalize_lesson_yaml(data)
    ordered_keys = list(allowed_keys_for_type(infer_stundentyp(canonical)))
    if isinstance(blattwerk_marker, str) and blattwerk_marker.strip():
        canonical[BLATTWERK_MARKER_KEY] = blattwerk_marker.strip()
        ordered_keys.append(BLATTWERK_MARKER_KEY)
    return render_yaml_frontmatter(ordered_keys, canonical)


def get_row_link_path(table: PlanTableData, row_index: int) -> Path | None:
    if row_index < 0 or row_index >= len(table.rows):
        return None

    idx_inhalt = table.column_index_optional(COLUMN_INHALT)
    if idx_inhalt is None:
        return None

    return _resolve_hours_link(table.markdown_path, table.rows[row_index][idx_inhalt])


def load_linked_lesson_yaml(path: Path) -> LessonYamlData:
    data, _ = _parse_yaml_frontmatter(path)
    normalized = canonicalize_lesson_yaml(data, source_label=str(path))
    return LessonYamlData(lesson_path=path, data=normalized)


def load_raw_linked_lesson_frontmatter(path: Path) -> dict[str, object]:
    """Liefert das geparste, aber nicht kanonisierte Frontmatter einer Stunden-Datei."""
    data, _ = _parse_yaml_frontmatter(path)
    return data


def save_linked_lesson_yaml(lesson: LessonYamlData, *, repair_oberthema: bool = False):
    """Schreibt das kanonisierte Frontmatter einer Stunden-Datei und erhält den Body.

    Setzt vor dem Schreiben die Oberthema-Schreib-Invariante durch
    (`ensure_oberthema_write_allowed`): ein ungültiger Plattenwert wird ohne
    ``repair_oberthema=True`` nie überschrieben.

    Raises:
        OberthemaRepairRequired: Wenn ein ungültiges Oberthema still ersetzt würde.
    """
    body = ""
    on_disk_data: dict[str, object] = {}
    if lesson.lesson_path.exists():
        raw = lesson.lesson_path.read_text(encoding="utf-8")
        body = raw
        parsed = read_or_default(lambda: _parse_yaml_frontmatter(lesson.lesson_path), default=None)
        if parsed is not None:
            on_disk_data, parsed_raw = parsed
            body = body_after_frontmatter(parsed_raw)

    normalized = canonicalize_lesson_yaml(lesson.data)
    ensure_oberthema_write_allowed(
        on_disk_data.get(OBERTHEMA_KEY),
        normalized.get(OBERTHEMA_KEY),
        repair=repair_oberthema,
    )
    frontmatter = _render_yaml_frontmatter(normalized, blattwerk_marker=on_disk_data.get(BLATTWERK_MARKER_KEY))
    atomic_write_text(lesson.lesson_path, frontmatter + body, encoding="utf-8")


def new_lesson_path(plan_dir: Path, suffix: str = ".md") -> Path:
    """Pfad für eine neue Einheit – **einzige** Stelle, die neue Einheiten-Dateinamen vergibt.

    Der Stem ist ein 6-stelliger Zufallscode aus ``[a-z0-9]`` (z. B. ``md38md``),
    eindeutig über beide Einheitenordner (``Einheiten/`` und ``Alteinheiten/``)
    und über beide Endungen (``.md``/``.ebw``: gleicher Stem = gleicher Link).
    Anlegen (`create_linked_lesson_file`) und Einfügen einer kopierten Einheit
    nutzen beide diese Funktion. Die Datei selbst wird nicht angelegt, nur das
    Einheitenverzeichnis.

    Args:
        plan_dir: Ordner der Plan-Datei.
        suffix: Endung der neuen Datei (``.md`` oder ``.ebw`` einer eingefügten Kopie).

    Returns:
        Kollisionsfreier Pfad im Einheitenverzeichnis.
    """
    stunden_dir = resolve_lesson_dir(plan_dir, create_if_missing=True)
    existing_stems = lesson_stems(stunden_dir) | lesson_stems(plan_dir / LESSON_DIR_ARCHIVE)
    return stunden_dir / f"{generate_random_lesson_stem(existing_stems)}{suffix}"


def create_linked_lesson_file(
    plan_table: PlanTableData,
    row_index: int,
    lesson_topic: str,
    default_hours: int,
    lesson_path: Path | None = None,
) -> Path:
    """Legt eine neue Stundendatei mit Zufallsstem an und verknüpft sie in der Plantabelle.

    Der Dateiname kommt aus `new_lesson_path` – oder ist *lesson_path*, wenn der
    Aufrufer ihn vorher dort geholt hat (damit Undo die neue Datei erfassen kann).

    Args:
        plan_table: Planungstabelle, in die der Link eingetragen wird.
        row_index: Index der Tabellenzeile, die den Link erhalten soll.
        lesson_topic: Fachlicher Stundenthemen-Titel (wird unverändert ins YAML
            geschrieben; leer bleibt leer, es gibt keinen Platzhalter).
        default_hours: Stundenzahl als Standardwert im YAML-Feld ``Dauer``.
        lesson_path: Vorab vergebener Pfad aus `new_lesson_path`; ``None`` vergibt einen.

    Returns:
        Pfad der neu angelegten Stundendatei.
    """
    candidate = lesson_path if lesson_path is not None else new_lesson_path(plan_table.markdown_path.parent)

    initial: dict[str, object] = {
        "Stundentyp": "Unterricht",
        "Dauer": str(default_hours),
        "Stundenthema": str(lesson_topic or "").strip(),
        "Oberthema": "",
        "Stundenziel": "",
        "Teilziele": [],
        "Kompetenzen": [],
        "Material": [],
    }
    lesson = LessonYamlData(lesson_path=candidate, data=initial)
    save_linked_lesson_yaml(lesson)

    idx_inhalt = plan_table.column_index_optional(COLUMN_INHALT)
    idx_thema_ausfall = plan_table.column_index_optional(COLUMN_THEMA_AUSFALL)
    if idx_inhalt is not None and 0 <= row_index < len(plan_table.rows):
        link_text = build_dataview_lesson_link(candidate.stem)
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
    idx_thema_ausfall = table.column_index_optional(COLUMN_THEMA_AUSFALL)
    if idx_thema_ausfall is None:
        return
    row = table.rows[row_index]
    if idx_thema_ausfall >= len(row):
        return

    stundentyp = str(yaml_data.get("Stundentyp", "Unterricht")).strip()
    oberthema_state = read_oberthema_state(yaml_data, group_name)
    oberthema = oberthema_state.primary
    group_plain = strip_wiki_link(str(group_name or "").strip())

    if stundentyp == "Ausfall":
        return
    if oberthema_state.is_invalid:
        # Ungültiges Oberthema: Planzelle nicht still leeren (Schreib-Invariante).
        return

    if not oberthema:
        row[idx_thema_ausfall] = ""
        return

    seq_stem = f"{group_plain} {oberthema}"
    if stundentyp == "LZK":
        row[idx_thema_ausfall] = f"LZK [[{seq_stem}]]"
    else:
        row[idx_thema_ausfall] = f"[[{seq_stem}]]"
