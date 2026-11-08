"""Warnzeile über einem Inhalt – einzige Banner-Komponente des Kursplaners.

Kompetenznetz (Diagnosen) und Sequenzleiter (Doppelungen, Schreibschutz) zeigen
ihre Hinweise damit gleich: jede Meldung mit „⚠“ auf ``warning_soft``, ohne Meldung
verborgen. Die Farben kommen aus Theme-Tokens und folgen jedem Theme-Wechsel über
einen bw-gui-Theme-Listener (``theme_label_token`` allein färbt nur einmal).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from bw_gui.runtime import ui
from bw_gui.theming import ThemeChange, register_theme_listener, theme_label_token

from kursplaner.core.domain.warning_marker import warning_text


class WarningBanner:
    """Ein- und ausblendbare Warnzeile.

    Args:
        parent: Container, in den das Banner gepackt wird.
        wraplength: Umbruchbreite in Pixeln.
        pack_options: Zusätzliche ``pack``-Optionen beim Einblenden (z. B. ``before``, ``pady``).
    """

    def __init__(self, parent: Any, *, wraplength: int = 900, **pack_options: Any) -> None:
        """Baut das (zunächst verborgene) Banner."""
        self.label = ui.Label(parent, justify="left", anchor="w", wraplength=wraplength, padx=10, pady=6)
        self._pack_options = {"fill": "x", "side": "top", **pack_options}
        self._apply_theme()
        register_theme_listener(self._on_theme, owner=self, widget=self.label)

    def show(self, messages: Sequence[str] | str | None) -> None:
        """Zeigt die Meldungen (je Zeile ein „⚠“) oder verbirgt das Banner, wenn keine da sind."""
        lines = [messages] if isinstance(messages, str) else list(messages or ())
        lines = [line for line in lines if line]
        if not lines:
            self.label.pack_forget()
            return
        self.label.configure(text="\n".join(warning_text(line) for line in lines))
        self.label.pack(**self._pack_options)

    def _apply_theme(self) -> None:
        theme_label_token(self.label, bg_token="warning_soft", fg_token="fg_primary")

    def _on_theme(self, _change: ThemeChange) -> None:
        self._apply_theme()
