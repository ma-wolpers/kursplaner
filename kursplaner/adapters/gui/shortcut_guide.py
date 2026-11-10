from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from bw_gui.contracts import KeySpec, Mod
from bw_gui.shortcuts import humanize_shortcut


@dataclass(frozen=True)
class ShortcutGuideEntry:
    """Beschreibt einen Shortcut inkl. Intent und Merkhilfen fuer die GUI.

    ``key`` ist die Taste als bw-gui-``KeySpec`` (in der JSON kanonische Notation,
    z. B. ``"Ctrl+Shift+E"``); der deutsche Anzeigetext ``display_shortcut`` wird daraus
    abgeleitet (bw-gui `humanize_shortcut`), nicht gespeichert.

    ``allow_when_text_input`` (optional, Standard ``false``) lässt die Taste auch
    in einer bearbeiteten Grid-Zelle wirken – nötig, wenn Tk dieselbe Taste im
    ``Text`` sonst still anders belegt (Strg+D löscht dort ein Zeichen).
    """

    key: KeySpec
    action_label: str
    intent: str
    mnemonic: str
    didactic_hint: str
    from_shortcut: bool = False
    payload: dict[str, object] = field(default_factory=dict)
    allow_when_text_input: bool = False

    @property
    def display_shortcut(self) -> str:
        """Anzeigetext der Taste (deutsch, z. B. ``"Strg+Shift+L"``)."""
        return humanize_shortcut(self.key)

    @property
    def is_ctrl_shortcut(self) -> bool:
        """Kennzeichnet Eintraege, die in die Strg-Uebersicht gehoeren."""
        return Mod.CTRL in self.key.modifiers


def binding_metadata(payload: Mapping[str, object]) -> dict[str, str]:
    """Bindungs-Metadaten aus einer Intent-Payload – einzige Übersetzung.

    Guide-Bindungen tragen ihre Payload so als Metadaten; Tooltips und Menüs finden
    mit derselben Payload die passende Taste (z. B. Spalte nach rechts: ``direction``).
    """
    return {str(key): str(value) for key, value in payload.items()}


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
        "key",
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
                key=_parse_key(item["key"], index),
                action_label=str(item["action_label"]),
                intent=str(item["intent"]),
                mnemonic=str(item["mnemonic"]),
                didactic_hint=str(item["didactic_hint"]),
                from_shortcut=bool(item.get("from_shortcut", False)),
                payload=dict(payload_data),
                allow_when_text_input=bool(item.get("allow_when_text_input", False)),
            )
        )

    return tuple(entries)


def _parse_key(raw: object, index: int) -> KeySpec:
    """Parst das ``key``-Feld (``KeySpec``-Notation); Tk-Syntax oder Tippfehler -> ``ValueError``."""
    try:
        return KeySpec.parse(str(raw))
    except ValueError as error:
        raise ValueError(f"Shortcut-Guide-Eintrag {index}: ungültige Taste {raw!r} ({error})") from error
