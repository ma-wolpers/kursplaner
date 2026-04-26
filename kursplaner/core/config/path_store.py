import json
from dataclasses import dataclass
from os.path import relpath
from pathlib import Path

from .settings import (
    DEFAULT_BAUKASTEN_DIR,
    DEFAULT_CALENDAR_DIR,
    DEFAULT_FACHDIDAKTIK_DIR,
    DEFAULT_FACHINHALTE_DIR,
    DEFAULT_KOMPETENZ_MANIFEST_PATH,
    DEFAULT_MATERIALIEN_DIR,
    DEFAULT_UNTERRICHT_DIR,
    SCRIPT_DIR,
    WORKSPACE_ROOT,
)

UNTERRICHT_DIR_KEY = "unterricht_dir"
CALENDAR_DIR_KEY = "calendar_dir"
BAUKASTEN_DIR_KEY = "baukasten_dir"
FACHINHALTE_DIR_KEY = "fachinhalte_dir"
FACHDIDAKTIK_DIR_KEY = "fachdidaktik_dir"
MATERIALIEN_DIR_KEY = "materialien_dir"
KOMPETENZ_MANIFEST_PATH_KEY = "kompetenz_manifest_path"


@dataclass(frozen=True)
class PathFieldDefinition:
    """Beschreibt ein konfigurierbares Pfadfeld der Anwendung."""

    key: str
    label: str
    pick_title: str
    kind: str
    requires_markdown: bool = False
    help_text: str = ""


def _resolve_workspace_path(raw: str | Path) -> Path:
    raw_text = str(raw).strip()
    if raw_text.startswith("__abs__/"):
        parts = [part for part in raw_text.split("/") if part]
        if len(parts) >= 2:
            drive = parts[1]
            tail_parts = parts[2:]
            if len(drive) == 1 and drive.isalpha():
                if tail_parts:
                    return Path(f"{drive.upper()}:/", *tail_parts).expanduser().resolve()
                return Path(f"{drive.upper()}:/").expanduser().resolve()

    path = Path(raw_text).expanduser()
    if not path.is_absolute():
        path = WORKSPACE_ROOT / path
    return path.resolve()


def _to_workspace_relative(path: Path) -> str:
    try:
        relative = Path(relpath(path, WORKSPACE_ROOT))
        return relative.as_posix()
    except ValueError:
        drive = path.drive.rstrip(":").lower()
        tail_parts = list(path.parts)
        if path.drive:
            tail_parts = tail_parts[1:]
        if tail_parts and tail_parts[0] in {"\\", "/"}:
            tail_parts = tail_parts[1:]
        if len(drive) == 1 and drive.isalpha():
            if tail_parts:
                return f"__abs__/{drive}/" + "/".join(tail_parts)
            return f"__abs__/{drive}"
        return path.as_posix().lstrip("/")


def normalize_path_value(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""
    return _to_workspace_relative(_resolve_workspace_path(value))


def resolve_path_value(raw: str) -> Path:
    return _resolve_workspace_path(raw)


def serialize_workspace_relative_path(path: Path) -> str:
    """Serialisiert Pfade konsistent relativ zum Workspace-Stamm `7thCloud`."""
    return _to_workspace_relative(path.expanduser().resolve())


DEFAULT_PATH_VALUES = {
    UNTERRICHT_DIR_KEY: normalize_path_value(str(DEFAULT_UNTERRICHT_DIR)),
    CALENDAR_DIR_KEY: normalize_path_value(str(DEFAULT_CALENDAR_DIR)),
    BAUKASTEN_DIR_KEY: normalize_path_value(str(DEFAULT_BAUKASTEN_DIR)),
    FACHINHALTE_DIR_KEY: normalize_path_value(str(DEFAULT_FACHINHALTE_DIR)),
    FACHDIDAKTIK_DIR_KEY: normalize_path_value(str(DEFAULT_FACHDIDAKTIK_DIR)),
    MATERIALIEN_DIR_KEY: normalize_path_value(str(DEFAULT_MATERIALIEN_DIR)),
    KOMPETENZ_MANIFEST_PATH_KEY: normalize_path_value(str(DEFAULT_KOMPETENZ_MANIFEST_PATH)),
}

PATH_FIELD_DEFINITIONS: tuple[PathFieldDefinition, ...] = (
    PathFieldDefinition(
        key=UNTERRICHT_DIR_KEY,
        label="Unterrichtsordner",
        pick_title="Unterrichtsordner auswählen",
        kind="dir",
        requires_markdown=True,
        help_text=(
            "Hier liegt dein eigentlicher Unterrichtsbereich mit Kursplänen und Einheiten.\n"
            "Diesen Ordner nutzt die Übersicht links und fast alle Bearbeitungsfunktionen."
        ),
    ),
    PathFieldDefinition(
        key=CALENDAR_DIR_KEY,
        label="Kalenderordner (.ics)",
        pick_title="Kalenderordner auswählen",
        kind="dir",
        requires_markdown=False,
        help_text=(
            "Ordner mit deinen .ics-Kalenderdateien (z. B. Ferien/Feiertage).\n"
            "Beim Anlegen neuer Unterrichte werden daraus Zeitraum und Halbjahr unterstützt berechnet."
        ),
    ),
    PathFieldDefinition(
        key=BAUKASTEN_DIR_KEY,
        label="Baukastenordner",
        pick_title="Baukastenordner auswählen",
        kind="dir",
        requires_markdown=False,
        help_text=(
            "Überordner für deine Sammlungen (z. B. Fachinhalte und Fachdidaktik).\n"
            "Wenn die speziellen Ordner unten nicht passen, sucht das Programm hier automatisch nach passenden Unterordnern."
        ),
    ),
    PathFieldDefinition(
        key=FACHINHALTE_DIR_KEY,
        label="Fachinhalte-Root",
        pick_title="Fachinhalte-Root auswählen",
        kind="dir",
        requires_markdown=True,
        help_text=(
            "Ordner mit fachlichen Themen- und Inhaltsnotizen je Fach.\n"
            "Diese Einträge erscheinen im Dialog Einheit planen als Inhalts-Vorschläge."
        ),
    ),
    PathFieldDefinition(
        key=FACHDIDAKTIK_DIR_KEY,
        label="Fachdidaktik-Root",
        pick_title="Fachdidaktik-Root auswählen",
        kind="dir",
        requires_markdown=True,
        help_text=(
            "Ordner mit methodischen/didaktischen Notizen je Fach.\n"
            "Diese Einträge erscheinen im Dialog Einheit planen als Methodik-Vorschläge."
        ),
    ),
    PathFieldDefinition(
        key=MATERIALIEN_DIR_KEY,
        label="Materialien-Root",
        pick_title="Materialien-Root auswählen",
        kind="dir",
        requires_markdown=True,
        help_text=(
            "Zentraler Ordner für Materialsammlungen und Materialnotizen.\n"
            "Der Pfad ist bereits hinterlegt, damit Materialfunktionen ihn konsistent verwenden können."
        ),
    ),
    PathFieldDefinition(
        key=KOMPETENZ_MANIFEST_PATH_KEY,
        label="Kompetenz-Manifest (JSON)",
        pick_title="Kompetenz-Manifest auswählen",
        kind="file",
        requires_markdown=False,
        help_text=(
            "JSON-Datei, die festlegt, welche Kompetenzkataloge verfügbar sind.\n"
            "Im Dialog Neuer Unterricht werden daraus KC-Profile und Kompetenzlisten geladen."
        ),
    ),
)

PATH_FIELD_BY_KEY = {item.key: item for item in PATH_FIELD_DEFINITIONS}


@dataclass(frozen=True)
class ManagedPaths:
    """Beschreibt Konfigurationsdaten für Managed Paths.

    Die Klasse bündelt Pfad- und Prüfwerte in einem stabilen Datentyp.
    """

    unterricht_dir: Path
    calendar_dir: Path
    baukasten_dir: Path
    fachinhalte_dir: Path
    fachdidaktik_dir: Path
    materialien_dir: Path
    kompetenz_manifest_path: Path


@dataclass(frozen=True)
class PathIssue:
    """Beschreibt Konfigurationsdaten für Path Issue.

    Die Klasse bündelt Pfad- und Prüfwerte in einem stabilen Datentyp.
    """

    key: str
    label: str
    path: Path
    message: str
    pick_title: str


def _settings_file() -> Path:
    """Liefert den Pfad zur persistenten Pfadkonfiguration."""
    return SCRIPT_DIR / "config" / "paths.json"


def _workspace_settings_file() -> Path:
    """Liefert den Zielpfad für das Schreiben der Pfadkonfiguration."""
    return SCRIPT_DIR / "config" / "paths.json"


def load_path_values() -> dict[str, str]:
    """Lädt Pfadwerte aus `paths.json` mit Fallback auf Defaultwerte."""
    values = DEFAULT_PATH_VALUES.copy()
    path = _settings_file()
    if not path.exists():
        return values

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return values

    if not isinstance(payload, dict):
        return values

    changed = False
    for key in DEFAULT_PATH_VALUES:
        raw = payload.get(key)
        if isinstance(raw, str) and raw.strip():
            normalized = normalize_path_value(raw)
            if normalized:
                values[key] = normalized
                changed = changed or (normalized != raw.strip())

    if changed:
        settings_path = _workspace_settings_file()
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")

    return values


def save_path_values(values: dict[str, str]) -> dict[str, str]:
    """Normalisiert und persistiert Pfadwerte in `paths.json`."""
    merged = DEFAULT_PATH_VALUES.copy()
    for key in DEFAULT_PATH_VALUES:
        raw = values.get(key)
        if isinstance(raw, str) and raw.strip():
            normalized = normalize_path_value(raw)
            if normalized:
                merged[key] = normalized

    path = _workspace_settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

    return merged


def update_path_value(key: str, value: str) -> dict[str, str]:
    """Aktualisiert genau einen Path-Key und speichert die Konfiguration."""
    if key not in DEFAULT_PATH_VALUES:
        raise KeyError(f"Unbekannter Path-Key: {key}")

    values = load_path_values()
    values[key] = value
    return save_path_values(values)


def get_managed_paths(values: dict[str, str] | None = None) -> ManagedPaths:
    """Konvertiert rohe Pfadwerte in ein aufgelöstes `ManagedPaths`-Objekt."""
    current = DEFAULT_PATH_VALUES.copy()
    if values:
        for key in DEFAULT_PATH_VALUES:
            raw = values.get(key)
            if isinstance(raw, str) and raw.strip():
                current[key] = raw.strip()
    return ManagedPaths(
        unterricht_dir=resolve_path_value(current[UNTERRICHT_DIR_KEY]),
        calendar_dir=resolve_path_value(current[CALENDAR_DIR_KEY]),
        baukasten_dir=resolve_path_value(current[BAUKASTEN_DIR_KEY]),
        fachinhalte_dir=resolve_path_value(current[FACHINHALTE_DIR_KEY]),
        fachdidaktik_dir=resolve_path_value(current[FACHDIDAKTIK_DIR_KEY]),
        materialien_dir=resolve_path_value(current[MATERIALIEN_DIR_KEY]),
        kompetenz_manifest_path=resolve_path_value(current[KOMPETENZ_MANIFEST_PATH_KEY]),
    )


def _contains_markdown_files(path: Path) -> bool:
    try:
        next(path.rglob("*.md"))
        return True
    except StopIteration:
        return False
    except Exception:
        return False


def validate_paths(paths: ManagedPaths) -> list[PathIssue]:
    """Prüft alle verwalteten Pfade auf Existenz, Typ und Inhaltsregeln."""
    issues: list[PathIssue] = []

    value_by_key: dict[str, Path] = {
        UNTERRICHT_DIR_KEY: paths.unterricht_dir,
        CALENDAR_DIR_KEY: paths.calendar_dir,
        BAUKASTEN_DIR_KEY: paths.baukasten_dir,
        FACHINHALTE_DIR_KEY: paths.fachinhalte_dir,
        FACHDIDAKTIK_DIR_KEY: paths.fachdidaktik_dir,
        MATERIALIEN_DIR_KEY: paths.materialien_dir,
        KOMPETENZ_MANIFEST_PATH_KEY: paths.kompetenz_manifest_path,
    }

    for field in PATH_FIELD_DEFINITIONS:
        path = value_by_key[field.key]
        if not path.exists():
            issues.append(
                PathIssue(
                    key=field.key,
                    label=field.label,
                    path=path,
                    message=f"{field.label} fehlt:\n{path}",
                    pick_title=field.pick_title,
                )
            )
            continue

        if field.kind == "file":
            if not path.is_file():
                issues.append(
                    PathIssue(
                        key=field.key,
                        label=field.label,
                        path=path,
                        message=f"{field.label} ist keine Datei:\n{path}",
                        pick_title=field.pick_title,
                    )
                )
            continue

        if not path.is_dir():
            issues.append(
                PathIssue(
                    key=field.key,
                    label=field.label,
                    path=path,
                    message=f"{field.label} ist kein Verzeichnis:\n{path}",
                    pick_title=field.pick_title,
                )
            )
            continue

        if field.requires_markdown and not _contains_markdown_files(path):
            issues.append(
                PathIssue(
                    key=field.key,
                    label=field.label,
                    path=path,
                    message=(
                        f"In {field.label} wurden keine Markdown-Dateien gefunden:\n{path}\n\n"
                        "Bitte einen anderen Ort wählen."
                    ),
                    pick_title=field.pick_title,
                )
            )

    return issues
