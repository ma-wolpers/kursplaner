from __future__ import annotations

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.dialogs import ScrollablePopupWindow as SharedScrollablePopupWindow
from bw_gui.runtime import ui


from kursplaner.adapters.gui.dialog_services import messagebox
from kursplaner.adapters.gui.ui_theme import apply_window_theme, configure_ttk_theme


class ScrollablePopupWindow(SharedScrollablePopupWindow):
    """Basisklasse fuer Popup-Fenster mit automatisch scrollbarem Inhaltsbereich."""

    def __str__(self) -> str:
        """Expose Tk widget path for Tk calls that stringify popup owners."""
        return str(self._popup_window)

    def __init__(
        self,
        master,
        *,
        title: str,
        geometry: str,
        minsize: tuple[int, int],
        theme_key: str | None = None,
    ):
        super().__init__(
            master,
            title=title,
            geometry=geometry,
            minsize=minsize,
            theme_key=theme_key,
            apply_window_theme=apply_window_theme,
            configure_ttk_theme=configure_ttk_theme,
            request_close_confirmation=self._confirm_close_if_needed,
        )

    def _requires_close_confirmation(self) -> bool:
        return False

    def _close_confirmation_title(self) -> str:
        return "Eingaben verwerfen?"

    def _close_confirmation_message(self) -> str:
        return "Ungespeicherte Eingaben gehen verloren. Wirklich schließen?"

    def _confirm_close_if_needed(self) -> bool:
        if not self._requires_close_confirmation():
            return True
        return bool(
            messagebox.askyesno(
                self._close_confirmation_title(),
                self._close_confirmation_message(),
                parent=self,
                default="no",
                icon="warning",
            )
        )

    def _activate_modal_focus(self) -> None:
        """Keep class-hook resolution on the local wrapper for test/runtime parity."""
        if not self.winfo_exists():
            return
        if ScrollablePopupWindow.active_popup() is not self:
            return
        try:
            self.lift()
            focused = self.focus_get()
            if not self._is_descendant_of_popup(focused):
                self.focus_force()
        except ui.TclError:
            return
        try:
            if self.grab_current() is None:
                self.grab_set()
        except ui.TclError:
            return

    def _handle_escape_request(self) -> str:
        """Keep class-hook resolution on the local wrapper for test/runtime parity."""
        focused = self.focus_get()
        if self._is_descendant_of_popup(focused) and ScrollablePopupWindow._is_editable_widget(focused):
            try:
                self.focus_force()
            except ui.TclError:
                return "break"
            return "break"
        return self._request_close()

