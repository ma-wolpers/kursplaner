from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]

DEFAULT_UNTERRICHT_DIR = WORKSPACE_ROOT / "7thVault" / "🏫 Pädagogik" / "1 Unterricht"
DEFAULT_CALENDAR_DIR = WORKSPACE_ROOT / "Code" / "schulhelfer" / "jahresplan" / "data"
DEFAULT_BAUKASTEN_DIR = WORKSPACE_ROOT / "7thVault" / "🏫 Pädagogik" / "30 Baukasten"
DEFAULT_FACHINHALTE_DIR = DEFAULT_BAUKASTEN_DIR / "34 Fachinhalte"
DEFAULT_FACHDIDAKTIK_DIR = DEFAULT_BAUKASTEN_DIR / "33 Fachdidaktik"
DEFAULT_MATERIALIEN_DIR = DEFAULT_BAUKASTEN_DIR / "32 Materialien"
DEFAULT_KOMPETENZ_MANIFEST_PATH = (
    SCRIPT_DIR / "kursplaner" / "resources" / "kompetenzkataloge" / "catalog_manifest.json"
)

WEEKDAY_MAP = {
    "montag": 0,
    "dienstag": 1,
    "mittwoch": 2,
    "donnerstag": 3,
    "freitag": 4,
    "samstag": 5,
    "sonntag": 6,
}

WEEKDAY_ORDER = [
    "Montag",
    "Dienstag",
    "Mittwoch",
    "Donnerstag",
    "Freitag",
    "Samstag",
    "Sonntag",
]

WEEKDAY_SHORT_OPTIONS = [
    ("Mo", 0),
    ("Di", 1),
    ("Mi", 2),
    ("Do", 3),
    ("Fr", 4),
]
