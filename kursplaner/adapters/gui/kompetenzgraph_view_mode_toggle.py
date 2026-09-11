from __future__ import annotations

from collections.abc import Callable, Mapping

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import widgets

from kursplaner.adapters.gui.hover_tooltip import HoverTooltip
from kursplaner.core.domain.kompetenzgraph_view_mode import MODE_ABHAENGIGKEITEN, MODE_FORT_VORAUS, MODE_OBER_TEIL

_VIEW_MODE_LABELS: tuple[tuple[str, str], ...] = (
    (MODE_OBER_TEIL, "Ober-/Teilkompetenzen"),
    (MODE_FORT_VORAUS, "Fort-/Voraussetzung"),
    (MODE_ABHAENGIGKEITEN, "Abhängigkeiten"),
)


class KompetenzGraphViewModeToggle:
    """Segmented-Control (`Segmented.TButton`/`SegmentedActive.TButton`) zur Umschaltung des View-Modes.

    Eigene kleine Widget-Kapselung, ausgelagert aus `kompetenzgraph_dialog.py`,
    um dessen 300-Zeilen-Budget einzuhalten -- rein UI-seitige Verantwortung
    (Button-Erzeugung + Styling des aktiven Buttons), kennt weder
    Sichtbarkeits- noch Layout-Logik. Nutzt dieselben, auch von Blattwerk
    verwendeten `bw_gui`-Styles.
    """

    def __init__(
        self,
        parent,
        *,
        initial_mode: str,
        on_mode_selected: Callable[[str], None],
        mode_help_text: Mapping[str, str] | None = None,
    ):
        """Baut die Segmented-Control auf und zeigt `initial_mode` als aktiv.

        Args:
            parent: Übergeordnetes Widget (z. B. eine Toolbar-Frame).
            initial_mode: Der beim Aufbau aktive View-Mode.
            on_mode_selected: Wird mit dem Modus-Schlüssel aufgerufen,
                sobald ein Button angeklickt wird -- der Aufrufer
                entscheidet, ob/wie der Modus tatsächlich übernommen wird
                und ruft danach `refresh()` mit dem neuen aktiven Modus.
            mode_help_text: Optionale Erklärtexte je Modus-Schlüssel. Ist
                für einen Modus ein Eintrag vorhanden, wird ein
                `HoverTooltip` auf dessen Button gebunden -- aktuell nur
                für `MODE_ABHAENGIGKEITEN` befüllt, da "Teilkompetenz" und
                "Voraussetzung" dort gemeinsam auftreten und ihr
                Bedeutungsunterschied nicht allein aus dem Button-Label
                hervorgeht (siehe `help_catalog.py::KOMPETENZGRAPH_HELP`).
                Die anderen Modi sind über ihr Label bereits
                selbsterklärend und bekommen bewusst keinen Tooltip.
        """
        self._on_mode_selected = on_mode_selected
        self._current_mode = initial_mode
        segment_group = widgets.Frame(parent)
        segment_group.pack(anchor="w")
        self._buttons: dict[str, widgets.Button] = {}
        self._tooltips: list[HoverTooltip] = []
        for mode_key, label in _VIEW_MODE_LABELS:
            button = widgets.Button(
                segment_group,
                text=label,
                style="Segmented.TButton",
                command=lambda selected_mode=mode_key: self._on_mode_selected(selected_mode),
            )
            button.pack(side="left", padx=(0, 4))
            self._buttons[mode_key] = button
            help_text = mode_help_text.get(mode_key) if mode_help_text is not None else None
            if help_text:
                self._tooltips.append(HoverTooltip(button, help_text))
        self.refresh(initial_mode)

    def refresh(self, active_mode: str) -> None:
        """Aktualisiert das Button-Styling auf den aktuell aktiven Modus."""
        self._current_mode = active_mode
        for mode_key, button in self._buttons.items():
            button.configure(style="SegmentedActive.TButton" if mode_key == active_mode else "Segmented.TButton")

    def next_mode(self) -> str:
        """Liefert den zyklisch nächsten Modus (mit Wraparound) -- genutzt vom Strg+Tab-Kurzbefehl.

        Ersetzt das frühere binäre `other_mode()`: mit drei (statt zwei)
        Ansichten schaltet Strg+Tab nun reihum durch `_VIEW_MODE_LABELS`
        in Deklarationsreihenfolge, nach dem letzten Eintrag wieder zurück
        zum ersten.
        """
        mode_keys = [mode_key for mode_key, _label in _VIEW_MODE_LABELS]
        current_index = mode_keys.index(self._current_mode)
        return mode_keys[(current_index + 1) % len(mode_keys)]
