from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ShortcutGuideEntry:
    """Beschreibt einen Shortcut inkl. Intent und Merkhilfen fuer die GUI."""

    key_sequence: str
    display_shortcut: str
    action_label: str
    intent: str
    mnemonic: str
    didactic_hint: str
    from_shortcut: bool = False
    payload: dict[str, object] = field(default_factory=dict)

    @property
    def is_ctrl_shortcut(self) -> bool:
        """Kennzeichnet Eintraege, die in die Strg-Uebersicht gehoeren."""
        return self.display_shortcut.startswith("Strg+")


def shortcut_guide_path() -> Path:
    """Liefert den kanonischen Pfad der Shortcut-Guide-JSON."""
    return Path(__file__).resolve().parents[2] / "resources" / "shortcuts" / "shortcut_guide.json"


def load_shortcut_guide_entries() -> tuple[ShortcutGuideEntry, ...]:
    """Laedt und validiert die Shortcut-Definitionen aus der JSON-Ressource."""
    path = shortcut_guide_path()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Shortcut-Guide muss eine Liste sein: {path}")

    entries: list[ShortcutGuideEntry] = []
    required_fields = (
        "key_sequence",
        "display_shortcut",
        "action_label",
        "intent",
        "mnemonic",
        "didactic_hint",
    )

    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Shortcut-Guide-Eintrag {index} ist kein Objekt.")

        missing = [field_name for field_name in required_fields if not str(item.get(field_name, "")).strip()]
        if missing:
            missing_text = ", ".join(missing)
            raise ValueError(f"Shortcut-Guide-Eintrag {index} ohne Pflichtfelder: {missing_text}")

        payload_data = item.get("payload", {})
        if not isinstance(payload_data, dict):
            raise ValueError(f"Shortcut-Guide-Eintrag {index} hat ungültiges payload-Feld.")

        entries.append(
            ShortcutGuideEntry(
                key_sequence=str(item["key_sequence"]),
                display_shortcut=str(item["display_shortcut"]),
                action_label=str(item["action_label"]),
                intent=str(item["intent"]),
                mnemonic=str(item["mnemonic"]),
                didactic_hint=str(item["didactic_hint"]),
                from_shortcut=bool(item.get("from_shortcut", False)),
                payload=dict(payload_data),
            )
        )

    return tuple(entries)
