from dataclasses import dataclass
from os.path import relpath
from pathlib import Path

from bw_libs.app_paths import atomic_write_json
from bw_libs.safe_read import read_json_or_default

from .path_field_definitions import (
    BAUKASTEN_DIR_KEY as BAUKASTEN_DIR_KEY,
)
from .path_field_definitions import (
    CALENDAR_DIR_KEY as CALENDAR_DIR_KEY,
)
from .path_field_definitions import (
    FACHDIDAKTIK_DIR_KEY as FACHDIDAKTIK_DIR_KEY,
)
from .path_field_definitions import (
    FACHINHALTE_DIR_KEY as FACHINHALTE_DIR_KEY,
)
from .path_field_definitions import (
    KOMPETENZ_MANIFEST_PATH_KEY as KOMPETENZ_MANIFEST_PATH_KEY,
)
from .path_field_definitions import (
    MATERIALIEN_DIR_KEY as MATERIALIEN_DIR_KEY,
)
from .path_field_definitions import (
    PATH_FIELD_BY_KEY as PATH_FIELD_BY_KEY,
)
from .path_field_definitions import (
    PATH_FIELD_DEFINITIONS as PATH_FIELD_DEFINITIONS,
)
from .path_field_definitions import (
    UNTERRICHT_DIR_KEY as UNTERRICHT_DIR_KEY,
)
from .path_field_definitions import (
    PathFieldDefinition as PathFieldDefinition,
)
from .settings import (
    DEFAULT_BAUKASTEN_DIR,
    DEFAULT_FACHDIDAKTIK_DIR,
    DEFAULT_FACHINHALTE_DIR,
    DEFAULT_KOMPETENZ_MANIFEST_PATH,
    DEFAULT_MATERIALIEN_DIR,
    DEFAULT_UNTERRICHT_DIR,
    SCRIPT_DIR,
    WORKSPACE_ROOT,
)


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


def infer_workspace_root_from_path(path: Path) -> Path:
    """Infer workspace root from a file or directory path without folder-name coupling."""

    resolved = path.expanduser().resolve()
    start = resolved if resolved.is_dir() else resolved.parent

    for candidate in (start, *start.parents):
        if candidate.name.casefold() == "7thvault":
            return candidate.parent
        vault_dir = candidate / "7thVault"
        if vault_dir.exists() and vault_dir.is_dir():
            return candidate

    if resolved.anchor:
        return Path(resolved.anchor)
    return start


def serialize_workspace_relative_path(path: Path) -> str:
    """Serialisiert Pfade konsistent relativ zum konfigurierten Workspace-Stamm."""
    return _to_workspace_relative(path.expanduser().resolve())


DEFAULT_PATH_VALUES = {
    UNTERRICHT_DIR_KEY: normalize_path_value(str(DEFAULT_UNTERRICHT_DIR)),
    # Kein geratener Default: der Kalenderordner ist rein lokale Konfiguration
    # (siehe validate_paths) und wird beim ersten Start interaktiv erfragt.
    CALENDAR_DIR_KEY: "",
    BAUKASTEN_DIR_KEY: normalize_path_value(str(DEFAULT_BAUKASTEN_DIR)),
    FACHINHALTE_DIR_KEY: normalize_path_value(str(DEFAULT_FACHINHALTE_DIR)),
    FACHDIDAKTIK_DIR_KEY: normalize_path_value(str(DEFAULT_FACHDIDAKTIK_DIR)),
    MATERIALIEN_DIR_KEY: normalize_path_value(str(DEFAULT_MATERIALIEN_DIR)),
    KOMPETENZ_MANIFEST_PATH_KEY: normalize_path_value(str(DEFAULT_KOMPETENZ_MANIFEST_PATH)),
}

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

    payload = read_json_or_default(path, default=None)
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
        atomic_write_json(settings_path, values)

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
    atomic_write_json(path, merged)

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


def validate_paths(paths: ManagedPaths, raw_values: dict[str, str] | None = None) -> list[PathIssue]:
    """Prüft alle verwalteten Pfade auf Existenz, Typ und Inhaltsregeln.

    Args:
        paths: Aufgelöste Pfade (siehe `get_managed_paths`).
        raw_values: Optional die rohen, unaufgelösten Werte (siehe `load_path_values`).
            Ein leerer Rohwert gilt als "nicht konfiguriert" und wird als eigener
            Issue gemeldet, statt über die (dann ggf. zufällig existierende)
            aufgelöste Pfadauflösung stillschweigend als gültig durchzugehen.
    """
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
        if raw_values is not None and not raw_values.get(field.key, "").strip():
            issues.append(
                PathIssue(
                    key=field.key,
                    label=field.label,
                    path=value_by_key[field.key],
                    message=f"{field.label} ist nicht konfiguriert.",
                    pick_title=field.pick_title,
                )
            )
            continue

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
