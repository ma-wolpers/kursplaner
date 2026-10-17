"""Maus- und Fokusverhalten der Grid-Zellen über bw-gui ``PointerGroup``s (ein Binding je Geste statt je Zelle).

Das Planraster baut bei jedem Zoom bzw. Neuaufbau hunderte bis tausende Zellen neu.
Früher hatte jede Zelle eigene ``widget.bind("<Button-1>", lambda ...)``- und
``<MouseWheel>``-Bindungen. Jetzt gehört jede Zelle über ihren Bindtag zu einer
``PointerGroup`` je Geste; welche Zelle geklickt wurde, ergibt ``event.widget`` und die
hier geführte Zuordnung Widget-Pfad -> Zellkoordinaten.

Gesten (alle primäre Maustaste, beim Drücken; das Intent-Ergebnis entscheidet wie
früher, ob der native Klick -- z. B. die Cursor-Positionierung im Text -- noch läuft):

* editierbare Tageszelle -> ``GRID_CELL_CLICK(field_key, day_index)``
* nicht editierbare Datumszelle -> ``GRID_DATE_CELL_CLICK(day_index)``
* Spaltenkopf -> ``GRID_COLUMN_CLICK(day_index)``
* einklappbare Zeilenbeschriftung -> ``GRID_TOGGLE_ROW_EXPAND(field_key)``
* Sequenzfeld-Zelle -> ``GRID_SEQUENCE_FIELD_CLICK(sequence_field_key, sequence_row_index)``
* Mausrad über jeder Zelle -> ``app._on_grid_mousewheel(WheelEvent)``
* Fokus editierbarer Tages- und Sequenzfeld-Zellen -> beim Betreten ``GRID_EDITOR_FOCUS_IN``
  bzw. ``GRID_SEQUENCE_FIELD_FOCUS_IN``; beim Verlassen erst der Commit
  (``GRID_COMMIT_CELL``/``GRID_COMMIT_SEQUENCE_FIELD``), dann ``GRID_EDITOR_FOCUS_OUT``/
  ``GRID_SEQUENCE_FIELD_FOCUS_OUT`` -- dieselbe Reihenfolge wie die früheren zwei
  ``<FocusOut>``-Bindungen je Zelle.

Die Zuordnungen werden beim Neuaufbau einfach überschrieben (gleicher Tk-Pfad ->
neuer Eintrag); Einträge zerstörter Zellen sind harmlos, weil ohne Widget kein Ereignis
mehr kommt.
"""

from __future__ import annotations

from typing import Any

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import PointerGroup  # noqa: E402

from kursplaner.adapters.gui.ui_intents import UiIntent  # noqa: E402

_CLICK_GROUPS = ("cell", "date_cell", "header", "row_label", "sequence_cell")


class GridPointerGroups:
    """Die Pointer-Gruppen eines Planrasters (lazy beim ersten Widget angelegt)."""

    def __init__(self, app: Any) -> None:
        """Speichert die App (Intent-Ziel) und legt die Gruppen erst beim ersten Mitglied an.

        Args:
            app: Hauptfenster mit ``_handle_ui_intent`` und ``_on_grid_mousewheel``.
        """
        self.app = app
        self._groups: dict[str, PointerGroup] = {}
        self._payloads: dict[str, dict[str, dict[str, object]]] = {name: {} for name in _CLICK_GROUPS}
        # Fokus: Tk-Pfad -> (Intents beim Betreten, Intents beim Verlassen), je mit Payload.
        self._focus_payloads: dict[str, tuple[tuple, tuple]] = {}

    def _group(self, name: str, anchor: Any) -> PointerGroup:
        group = self._groups.get(name)
        if group is None:
            group = self._groups[name] = PointerGroup(anchor, f"kursplaner-grid-{name}")
            if name == "wheel":
                group.on_wheel(lambda event: self.app._on_grid_mousewheel(event))
            elif name == "focus":
                group.on_focus_change(
                    on_gained=lambda change: self._on_focus(change, gained=True),
                    on_lost=lambda change: self._on_focus(change, gained=False),
                )
            else:
                group.on_click(lambda event, n=name: self._on_click(n, event))
        return group

    def _on_click(self, name: str, event: Any) -> object:
        payload = self._payloads[name].get(str(event.widget))
        if payload is None:
            return None
        intent = payload["intent"]
        kwargs = {key: value for key, value in payload.items() if key != "intent"}
        return self.app._handle_ui_intent(intent, **kwargs)

    def _on_focus(self, change: Any, *, gained: bool) -> None:
        entry = self._focus_payloads.get(str(change.widget))
        if entry is None:
            return
        for intent, kwargs in entry[0] if gained else entry[1]:
            self.app._handle_ui_intent(intent, **kwargs)

    def _register_focus(self, widget: Any, on_in: tuple, on_out: tuple) -> None:
        self._focus_payloads[str(widget)] = (on_in, on_out)
        self._group("focus", widget).add(widget)

    def _register(self, name: str, widget: Any, intent: str, **payload: object) -> None:
        self._payloads[name][str(widget)] = {"intent": intent, **payload}
        self._group(name, widget).add(widget)

    # -- public membership ----------------------------------------------------------------

    def wheel(self, widget: Any) -> None:
        """Mausrad über *widget* scrollt bzw. zoomt das Raster."""
        self._group("wheel", widget).add(widget)

    def cell(self, widget: Any, *, field_key: str, day_index: int, editable: bool) -> None:
        """Tageszelle: editierbar -> Zellklick, sonst Datumszellen-Klick."""
        if editable:
            self._register("cell", widget, UiIntent.GRID_CELL_CLICK, field_key=field_key, day_index=day_index)
        else:
            self._register("date_cell", widget, UiIntent.GRID_DATE_CELL_CLICK, day_index=day_index)

    def header(self, widget: Any, *, day_index: int) -> None:
        """Spaltenkopf: Klick wählt die Spalte."""
        self._register("header", widget, UiIntent.GRID_COLUMN_CLICK, day_index=day_index)

    def row_label(self, widget: Any, *, field_key: str, collapsible: bool) -> None:
        """Zeilenbeschriftung: nur einklappbare Zeilen reagieren auf Klick (sonst Mitgliedschaft entfernen)."""
        if collapsible:
            self._register("row_label", widget, UiIntent.GRID_TOGGLE_ROW_EXPAND, field_key=field_key)
            return
        self._payloads["row_label"].pop(str(widget), None)
        group = self._groups.get("row_label")
        if group is not None:
            group.discard(widget)

    def focus_cell(self, widget: Any, *, field_key: str, day_index: int) -> None:
        """Editierbare Tageszelle: Fokus betreten/verlassen meldet Editor-Fokus und Commit."""
        payload = {"field_key": field_key, "day_index": day_index}
        self._register_focus(
            widget,
            ((UiIntent.GRID_EDITOR_FOCUS_IN, payload),),
            ((UiIntent.GRID_COMMIT_CELL, payload), (UiIntent.GRID_EDITOR_FOCUS_OUT, payload)),
        )

    def focus_sequence_cell(self, widget: Any, *, field_key: str, row_index: int) -> None:
        """Sequenzfeld-Zelle: Fokus betreten/verlassen meldet Sequenzfeld-Fokus und Commit."""
        payload = {"sequence_field_key": field_key, "sequence_row_index": row_index}
        self._register_focus(
            widget,
            ((UiIntent.GRID_SEQUENCE_FIELD_FOCUS_IN, payload),),
            ((UiIntent.GRID_COMMIT_SEQUENCE_FIELD, payload), (UiIntent.GRID_SEQUENCE_FIELD_FOCUS_OUT, payload)),
        )

    def sequence_cell(self, widget: Any, *, field_key: str, row_index: int) -> None:
        """Sequenzfeld-Zelle (über mehrere Tage gespannt): Klick wählt das Sequenzfeld."""
        self._register(
            "sequence_cell",
            widget,
            UiIntent.GRID_SEQUENCE_FIELD_CLICK,
            sequence_field_key=field_key,
            sequence_row_index=row_index,
        )
