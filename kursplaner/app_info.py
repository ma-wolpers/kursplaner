from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppInfo:
    """Canonical identity metadata for the application."""

    name: str
    version: str
    appdata_folder: str
    window_title: str


APP_INFO = AppInfo(
    name="Kursplaner",
    version="0.1.2",
    appdata_folder="kursplaner",
    window_title="Kurs-Manager",
)
