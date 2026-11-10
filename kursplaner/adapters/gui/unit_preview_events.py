"""Übersetzt eine `UnitPreview` in bw-gui-`DocEvent`s (Tk-frei, rein).

Einzige Stelle, die das Layout der Einheitsvorschau festlegt: oben je
Frontmatter-Feld eine kompakte Zeile „**Feld:** Wert · Wert“, darunter der
Body (HTML über `html_to_events`, ohne Markdown-Renderer als Rohtext).
Platzhalter für „keine Einheit“/„nicht verknüpft“/Lesefehler kommen ebenfalls
von hier, damit der Controller keine Texte kennt.
"""

from __future__ import annotations

from bw_gui.widgets import DocEvent, ListItemEvent, ParagraphEvent, TextRun, html_to_events

from kursplaner.core.usecases.unit_preview_usecase import UnitPreview

PREVIEW_TITLE = "Einheitsvorschau"
NO_UNIT_SELECTED = "Keine Einheit ausgewählt – wähle eine Spalte oder Zelle im Kursgitter."
NO_UNIT_DOCUMENT = "Für diese Spalte ist kein Einheitsdokument verknüpft."
_VALUE_SEPARATOR = " · "


def message_events(message: str) -> list[DocEvent]:
    """Ein einzelner Hinweisabsatz (Platzhalter, Fehler)."""
    return [ParagraphEvent(runs=(TextRun(message, italic=True),))]


def field_events(fields: tuple[tuple[str, tuple[str, ...]], ...]) -> list[DocEvent]:
    """Je Feld eine Listenzeile mit fettem Feldnamen; danach ein Abstand zum Body."""
    if not fields:
        return []
    events: list[DocEvent] = [
        ListItemEvent(runs=(TextRun(f"{key}: ", bold=True), TextRun(_VALUE_SEPARATOR.join(values))), ordered=False)
        for key, values in fields
    ]
    events.append(ParagraphEvent(runs=()))
    return events


def preview_events(preview: UnitPreview) -> list[DocEvent]:
    """Komplette Vorschau: Lesefehler, sonst Felder plus Body (HTML oder Rohtext)."""
    if preview.error is not None:
        return message_events(preview.error)
    events = field_events(preview.fields)
    if preview.body_html is not None:
        events.extend(html_to_events(preview.body_html))
    elif preview.body_text:
        events.append(ParagraphEvent(runs=(TextRun(preview.body_text),)))
    return events
