from __future__ import annotations

from collections.abc import Callable

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import widgets

from kursplaner.core.domain.kompetenzgraph_view_mode import MODE_FORT_VORAUS, MODE_OBER_TEIL

_VIEW_MODE_LABELS: tuple[tuple[str, str], ...] = (
    (MODE_OBER_TEIL, "Ober-/Teilkompetenzen"),
    (MODE_FORT_VORAUS, "Fort-/Voraussetzung"),
)


class KompetenzGraphViewModeToggle:
    """Segmented-Control (`Segmented.TButton`/`SegmentedActive.TButton`) zur Umschaltung des View-Modes.

    Eigene kleine Widget-Kapselung, ausgelagert aus `kompetenzgraph_dialog.py`,
    um dessen 300-Zeilen-Budget einzuhalten -- rein UI-seitige Verantwortung
    (Button-Erzeugung + Styling des aktiven Buttons), kennt weder
    Sichtbarkeits- noch Layout-Logik. Nutzt dieselben, auch von Blattwerk
    verwendeten `bw_gui`-Styles.
    """

    def __init__(self, parent, *, initial_mode: str, on_mode_selected: Callable[[str], None]):
        """Baut die Segmented-Control auf und zeigt `initial_mode` als aktiv.

        Args:
            parent: Übergeordnetes Widget (z. B. eine Toolbar-Frame).
            initial_mode: Der beim Aufbau aktive View-Mode.
            on_mode_selected: Wird mit dem Modus-Schlüssel aufgerufen,
                sobald ein Button angeklickt wird -- der Aufrufer
                entscheidet, ob/wie der Modus tatsächlich übernommen wird
                und ruft danach `refresh()` mit dem neuen aktiven Modus.
        """
        self._on_mode_selected = on_mode_selected
        self._current_mode = initial_mode
        segment_group = widgets.Frame(parent)
        segment_group.pack(anchor="w")
        self._buttons: dict[str, widgets.Button] = {}
        for mode_key, label in _VIEW_MODE_LABELS:
            button = widgets.Button(
                segment_group,
                text=label,
                style="Segmented.TButton",
                command=lambda selected_mode=mode_key: self._on_mode_selected(selected_mode),
            )
            button.pack(side="left", padx=(0, 4))
            self._buttons[mode_key] = button
        self.refresh(initial_mode)

    def refresh(self, active_mode: str) -> None:
        """Aktualisiert das Button-Styling auf den aktuell aktiven Modus."""
        self._current_mode = active_mode
        for mode_key, button in self._buttons.items():
            button.configure(style="SegmentedActive.TButton" if mode_key == active_mode else "Segmented.TButton")

    def other_mode(self) -> str:
        """Liefert den jeweils NICHT aktiven Modus -- genutzt vom Strg+Tab-Umschalt-Kurzbefehl."""
        return MODE_FORT_VORAUS if self._current_mode == MODE_OBER_TEIL else MODE_OBER_TEIL
