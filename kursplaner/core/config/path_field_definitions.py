"""Datentabelle der verwaltbaren Pfadfelder (Keys, Labels, Hilfetexte).

Reine Datenhaltung — kein Datei-I/O, keine Auflösungs-/Validierungslogik (siehe
`path_store.py` dafür). Ausgelagert aus `path_store.py`, damit die dort
verbleibende echte Logik (Laden/Speichern/Normalisieren/Validieren) nicht durch
diese große, aber inhaltlich flache Datenstruktur aufgebläht wird.
"""

from dataclasses import dataclass

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
