"""Gemeinsame Tastatur- und Klick-Verdrahtung der Unterrichts-Dialoge (bw-gui-Contract).

Die drei Dialoge in ``lesson_builder_dialog.py`` (Einheit planen, Kompetenzen wählen,
Stundenziel wählen) teilen dieselbe Bedienung: Textfelder mit Auswahl-Overlay
(↑/↓ bewegen, Enter übernimmt, Klick/Fokus öffnet), eigene Tab-Reihenfolge über die
Textfelder, Strg+Enter übernimmt den Dialog und ein Klick bzw. Fokuswechsel außerhalb
schließt das Overlay. Früher stand diese Verdrahtung als rohe Tk-Bindings dreifach in
der Datei; :class:`LessonDialogKeysMixin` bündelt sie über die bw-gui-Binder.

Bindtag-Ebenen (``KEYBINDING_CONTRACT.md``):

* **Textfeld** -- ``WidgetShortcutBinder`` (vor der ``Text``-Klasse): ↑/↓, Enter,
  Strg+Enter, Tab/Shift+Tab. Muss vor der Klasse liegen, weil ``Text`` sonst Enter
  bzw. Tab als Zeichen einfügt (auch bei Strg+Enter, Tks ``<Return>`` passt dort mit).
* **Dialog** -- ``WindowShortcutBinder`` (Toplevel-Tag): Strg+Enter, Tab/Shift+Tab für
  Fokus außerhalb der Textfelder (z. B. auf den Schaltflächen).
* **Filter-Refresh** -- ``on_key(phase="after")``: läuft, nachdem die Klasse das Zeichen
  eingefügt bzw. gelöscht hat.

Migration der früheren Tk-Sequenzen (exakte Modifier, ``local_keys``): ↑/↓ und Enter
tolerieren Shift wie früher; Strg+↑/↓ geht jetzt an die native Textbewegung statt an
das Overlay. Tab und Shift+Tab sind exakt (eigene Shift-Variante; ``ISO_Left_Tab``
klassifiziert bw-gui als Shift+Tab), Strg+Tab geht an das native Verhalten.
Ziffernblock-Enter wirkt wie Enter. Der Filter-Refresh lief früher bei *jedem*
Loslassen einer Taste und setzte die Overlay-Auswahl dabei auf Zeile 0 zurück -- auch
nach ↓, womit die Pfeil-Navigation in den Filterfeldern ins Leere lief. Die
Nach-Phase sieht nur Tasten, die kein Kürzel verbraucht hat, und reine Modifier-Tasten
(``Key.OTHER``) werden übergangen.
"""

from __future__ import annotations

from typing import Any

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.contracts import EventResult, Key, KeySpec  # noqa: E402
from bw_gui.runtime import (  # noqa: E402
    WidgetShortcutBinder,
    WindowShortcutBinder,
    bind_click,
    on_focus_change,
    on_global_click,
    on_key,
)

from kursplaner.adapters.gui.local_keys import CTRL_ENTER, DOWN, ENTER, UP, bind_keys  # noqa: E402

TAB = KeySpec.parse("Tab")
SHIFT_TAB = KeySpec.parse("Shift+Tab")
_PREFIX = "lesson_dialog"


class LessonDialogKeysMixin:
    """Tastatur-, Klick- und Fokusverdrahtung für Dialoge mit Overlay-Textfeldern.

    Erwartet von der Dialogklasse: ``self.overlay_controller``
    (``SelectionOverlayController``, darf erst nach dem Binden entstehen -- alle Handler
    lesen ihn erst beim Ereignis) und ``self._accept()``. Die Dialogklasse ruft
    :meth:`_bind_overlay_field` je Overlay-Feld, :meth:`_bind_tab_navigation` einmal mit
    der Tab-Reihenfolge und :meth:`_install_dialog_keys` einmal nach dem Anlegen des
    Overlay-Controllers. Handler, die sich zwischen den Dialogen unterscheiden
    (:meth:`_on_ctrl_enter_accept`, :meth:`_overlay_move_down`), überschreibt die
    Dialogklasse.
    """

    # -- Binder -----------------------------------------------------------------------

    def _window_keys(self) -> WindowShortcutBinder:
        """Gibt den Fenster-Binder des Dialogs zurück (beim ersten Aufruf angelegt).

        Mehrere Binder auf demselben Toplevel teilen sich die Konfliktprüfung (auch mit
        dem Escape-Binder der Popup-Basisklasse); ein Binder je Dialog genügt hier.
        """
        binder = getattr(self, "_lesson_window_binder", None)
        if binder is None:
            binder = self._lesson_window_binder = WindowShortcutBinder(self)
        return binder

    def _field_keys(self, text: Any) -> WidgetShortcutBinder:
        """Gibt den Widget-Binder eines Textfelds zurück (je Textfeld genau einer).

        Overlay- und Tab-Kürzel desselben Felds landen so in einem Binder, dessen
        Konfliktprüfung beide Gruppen sieht.
        """
        binders = getattr(self, "_lesson_field_binders", None)
        if binders is None:
            binders = self._lesson_field_binders = {}
        key = str(text)
        if key not in binders:
            binders[key] = WidgetShortcutBinder(text)
        return binders[key]

    # -- Verdrahtung --------------------------------------------------------------------

    def _bind_overlay_field(self, field_widget: Any, field_name: str, enable_filter_refresh: bool = False) -> None:
        """Verbindet ein ``WrappedTextField`` mit dem Auswahl-Overlay des Dialogs.

        Fokus und Klick öffnen das Overlay für *field_name*; ↑/↓ bewegen die Auswahl,
        Enter übernimmt sie (bei geschlossenem Overlay fügt ``Text`` den Zeilenumbruch
        ein), Strg+Enter übernimmt den Dialog.

        Args:
            field_widget: Feld mit ``.text`` (``tk.Text``).
            field_name: Schlüssel für ``_options_for_field``/``_on_overlay_pick``.
            enable_filter_refresh: Nach jeder Texteingabe die Overlay-Liste neu filtern
                (Felder, deren Inhalt die Suchanfrage ist).
        """
        text = field_widget.text

        def _open(_event: Any = None) -> None:
            self.overlay_controller.open(field_name, text)

        on_focus_change(text, on_gained=_open)
        bind_click(text, _open)
        bind_keys(
            self._field_keys(text),
            (
                (DOWN, f"{field_name}.overlay.down", self._overlay_move_down),
                (UP, f"{field_name}.overlay.up", self._overlay_move_up),
                (ENTER, f"{field_name}.overlay.pick", self._overlay_select_from_field),
                (CTRL_ENTER, f"{field_name}.accept", self._on_ctrl_enter_accept),
            ),
            prefix=_PREFIX,
        )
        if enable_filter_refresh:

            def _refresh_after_key(event: Any) -> None:
                if event.key is not Key.OTHER:
                    self._refresh_open_overlay(field_name)

            on_key(text, _refresh_after_key, phase="after")

    def _bind_tab_navigation(self, fields: list[Any]) -> None:
        """Legt die Tab-Reihenfolge über die Textfelder fest (ohne Umlauf am Ende).

        Tab/Shift+Tab im Textfeld springen zum nächsten/vorigen Feld statt ein
        Tabulatorzeichen einzufügen; mit Fokus außerhalb der Felder (Dialog-Binder)
        springen sie zum ersten bzw. letzten Feld.
        """
        self._tab_order = [field.text for field in fields]
        rows = ((TAB, "tab.next", self._on_tab_next), (SHIFT_TAB, "tab.previous", self._on_tab_prev))
        bind_keys(self._window_keys(), rows, prefix=f"{_PREFIX}.window")
        for text in self._tab_order:
            bind_keys(self._field_keys(text), rows, prefix=f"{_PREFIX}.field")

    def _install_dialog_keys(self) -> None:
        """Bindet Strg+Enter am Dialog und das Schließen des Overlays bei Klick/Fokus außerhalb.

        Der Klick-Beobachter (``on_global_click``) endet mit dem Dialog (``owner``) und
        wertet wie das frühere Toplevel-Binding nur Klicks in diesem Dialogfenster aus.
        """
        bind_keys(self._window_keys(), ((CTRL_ENTER, "accept", self._on_ctrl_enter_accept),), prefix=f"{_PREFIX}.window")
        self._overlay_click_subscription = on_global_click(self, self._on_global_click, owner=self)
        # within=True: wie frueher am Toplevel-Tag -- jeder Fokuswechsel im Dialog zaehlt.
        on_focus_change(self, on_gained=self._on_global_focus_change, within=True)

    # -- Handler ------------------------------------------------------------------------

    def _on_ctrl_enter_accept(self, _event: Any = None) -> EventResult:
        """Schließt das Overlay und übernimmt den Dialog (Strg+Enter)."""
        self.overlay_controller.close()
        self._accept()
        return EventResult.HANDLED

    def _on_tab_next(self, event: Any) -> EventResult:
        """Tab: Fokus auf das nächste Textfeld."""
        return self._move_tab_focus(getattr(event, "widget", None), +1)

    def _on_tab_prev(self, event: Any) -> EventResult:
        """Shift+Tab: Fokus auf das vorige Textfeld."""
        return self._move_tab_focus(getattr(event, "widget", None), -1)

    def _move_tab_focus(self, current_widget: Any, direction: int) -> EventResult:
        """Bewegt den Fokus in ``_tab_order`` um *direction*; verbraucht die Taste immer.

        Am Anfang/Ende bleibt der Fokus stehen (kein Umlauf). Liegt *current_widget*
        außerhalb der Reihenfolge, geht der Fokus aufs erste (vorwärts) bzw. letzte
        Feld (rückwärts).
        """
        if not getattr(self, "_tab_order", None):
            return EventResult.HANDLED
        try:
            current_index = self._tab_order.index(current_widget)
        except ValueError:
            target_index = 0 if direction > 0 else len(self._tab_order) - 1
            self._tab_order[target_index].focus_set()
            return EventResult.HANDLED
        target_index = current_index + direction
        if 0 <= target_index < len(self._tab_order):
            self._tab_order[target_index].focus_set()
        return EventResult.HANDLED

    def _refresh_open_overlay(self, expected_field: str) -> None:
        """Filtert die Overlay-Liste neu, wenn sie gerade für *expected_field* offen ist."""
        if self.overlay_controller.active_field == expected_field:
            self.overlay_controller.refresh()

    def _overlay_move_down(self, _event: Any) -> EventResult:
        """↓: Overlay-Auswahl eine Zeile nach unten."""
        self.overlay_controller.move(+1)
        return EventResult.HANDLED

    def _overlay_move_up(self, _event: Any) -> EventResult:
        """↑: Overlay-Auswahl eine Zeile nach oben."""
        self.overlay_controller.move(-1)
        return EventResult.HANDLED

    def _overlay_select_from_field(self, _event: Any) -> EventResult | None:
        """Enter: übernimmt die Overlay-Auswahl; bei geschlossenem Overlay läuft Enter weiter."""
        if self.overlay_controller.is_open:
            self.overlay_controller.select_current()
            return EventResult.HANDLED
        return None

    def _on_global_click(self, event: Any) -> None:
        """Schließt das Overlay bei einem Klick in diesem Dialog außerhalb von Overlay und Feld."""
        if not self.overlay_controller.is_open:
            return
        widget = getattr(event, "widget", None)
        if not self._is_in_dialog_window(widget):
            return
        if self.overlay_controller.should_keep_open_for_widget(widget):
            return
        self.overlay_controller.close()

    def _is_in_dialog_window(self, widget: Any) -> bool:
        """True, wenn *widget* im Toplevel dieses Dialogs liegt (nicht im Overlay-Fenster)."""
        try:
            return str(widget.winfo_toplevel()) == str(self)
        except Exception:
            return False

    def _on_global_focus_change(self, _event: Any) -> None:
        """Schließt das Overlay, wenn der Fokus auf ein Widget außerhalb von Overlay und Feld wechselt."""
        if not self.overlay_controller.is_open:
            return
        focused = self.focus_get()
        if self.overlay_controller.should_keep_open_for_widget(focused):
            return
        self.overlay_controller.close()
