from __future__ import annotations

from typing import Callable

from bw_libs.shared_gui_core import ensure_bw_gui_on_path

ensure_bw_gui_on_path()
from bw_gui.runtime import ui, widgets

from kursplaner.core.domain.grade_groups import GRADE_GROUPS, expand_grade_selection


class GradeGroupSelector:
    """Jahrgangsstufen-Auswahl, gruppiert nach GS/Sek I/Sek II, je Gruppe ausklappbar.

    Reine UI-Komponente: kennt keine Fachlogik ausser der Gruppierung selbst
    (`core.domain.grade_groups`) und liefert nach aussen nur `frozenset[int]`.

    Komponiert einen `widgets.Frame` statt ihn zu erben (wie `WeekdayRhythmPicker`)
    und delegiert unbekannte Attribute (`pack`/`grid`/…) an den Container -
    vermeidet eine neue lokale UI-Basisklasse.
    """

    def __getattr__(self, name: str):
        """Delegiert unbekannte Widget-Attribute an den zusammengesetzten Container."""
        return getattr(self._container, name)

    def __init__(self, master, *, on_change: Callable[[], None] | None = None, **kwargs) -> None:
        """Baut die Gruppen-Sektionen auf; `on_change` wird bei jeder Auswahlaenderung aufgerufen."""
        self._container = widgets.Frame(master, **kwargs)
        self._on_change = on_change
        self._expanded: dict[str, bool] = {group.key: False for group in GRADE_GROUPS}
        self._group_vars: dict[str, ui.BooleanVar] = {}
        self._grade_vars: dict[int, ui.BooleanVar] = {}
        self._toggle_labels: dict[str, widgets.Label] = {}
        self._grade_frames: dict[str, widgets.Frame] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        for group in GRADE_GROUPS:
            section = widgets.Frame(self._container, relief="groove", borderwidth=1, padding=6)
            section.pack(fill="x", pady=(0, 6))

            header = widgets.Frame(section)
            header.pack(fill="x")

            toggle_label = widgets.Label(header, text=self._toggle_text(group.key), cursor="hand2")
            toggle_label.pack(side="left")
            toggle_label.bind("<Button-1>", lambda _e, key=group.key: self._toggle_expand(key))
            self._toggle_labels[group.key] = toggle_label

            group_var = ui.BooleanVar(value=False)
            self._group_vars[group.key] = group_var
            widgets.Checkbutton(
                header,
                text="alle",
                variable=group_var,
                command=lambda key=group.key: self._on_group_toggle(key),
            ).pack(side="left", padx=(10, 0))

            grades_frame = widgets.Frame(section)
            self._grade_frames[group.key] = grades_frame
            for grade in range(group.grade_min, group.grade_max + 1):
                grade_var = ui.BooleanVar(value=False)
                self._grade_vars[grade] = grade_var
                widgets.Checkbutton(
                    grades_frame,
                    text=str(grade),
                    variable=grade_var,
                    command=self._on_grade_toggle,
                ).pack(side="left", padx=(0, 8))
            self._apply_expanded_visibility(group.key)

    def _toggle_text(self, key: str) -> str:
        group = next(g for g in GRADE_GROUPS if g.key == key)
        icon = "▾" if self._expanded[key] else "▸"
        return f"{icon} {group.label}"

    def _toggle_expand(self, key: str) -> None:
        self._expanded[key] = not self._expanded[key]
        self._toggle_labels[key].configure(text=self._toggle_text(key))
        self._apply_expanded_visibility(key)

    def _apply_expanded_visibility(self, key: str) -> None:
        frame = self._grade_frames[key]
        if self._expanded[key]:
            frame.pack(fill="x", padx=(18, 0), pady=(4, 0))
        else:
            frame.pack_forget()

    def _on_group_toggle(self, key: str) -> None:
        group = next(g for g in GRADE_GROUPS if g.key == key)
        checked = bool(self._group_vars[key].get())
        for grade in range(group.grade_min, group.grade_max + 1):
            self._grade_vars[grade].set(checked)
        self._notify_change()

    def _on_grade_toggle(self) -> None:
        self._sync_group_masters()
        self._notify_change()

    def _sync_group_masters(self) -> None:
        for group in GRADE_GROUPS:
            grades = range(group.grade_min, group.grade_max + 1)
            self._group_vars[group.key].set(all(self._grade_vars[g].get() for g in grades))

    def _notify_change(self) -> None:
        if self._on_change is not None:
            self._on_change()

    def get_selected_grades(self) -> frozenset[int]:
        """Liefert die aktuell ausgewaehlten Jahrgangsstufen als flache Menge."""
        fully_selected = frozenset(key for key, var in self._group_vars.items() if var.get())
        individually = frozenset(grade for grade, var in self._grade_vars.items() if var.get())
        return expand_grade_selection(fully_selected_group_keys=fully_selected, individually_selected_grades=individually)

    def set_selected_grades(self, grades: frozenset[int]) -> None:
        """Setzt die Auswahl (z. B. beim Laden eines bestehenden Eintrags zum Bearbeiten)."""
        for grade, var in self._grade_vars.items():
            var.set(grade in grades)
        self._sync_group_masters()
        for group in GRADE_GROUPS:
            has_selection = any(self._grade_vars[g].get() for g in range(group.grade_min, group.grade_max + 1))
            if has_selection and not self._expanded[group.key]:
                self._expanded[group.key] = True
                self._toggle_labels[group.key].configure(text=self._toggle_text(group.key))
                self._apply_expanded_visibility(group.key)
