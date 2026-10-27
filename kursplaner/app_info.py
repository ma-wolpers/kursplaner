from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppInfo:
    """Canonical identity metadata for the application."""

    name: str
    version: str
    appdata_folder: str

    @property
    def window_title(self) -> str:
        """Return the main window title, derived from ``name``.

        The title is not stored separately so it can never drift from the
        application name again (it once still read "Kurs-Manager" after the
        rename). Any future decoration (e.g. a version suffix) belongs here.
        """
        return self.name


APP_INFO = AppInfo(
    name="Kursplaner",
    version="0.1.2",
    appdata_folder="kursplaner",
)
