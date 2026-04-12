from __future__ import annotations

import json
from pathlib import Path

from kursplaner.core.config.path_store import KOMPETENZ_MANIFEST_PATH_KEY, load_path_values, resolve_path_value
from kursplaner.core.domain.kompetenzkatalog import (
    Kompetenzkatalog,
    KompetenzkatalogManifestEntry,
    KompetenzkatalogParseError,
    parse_kompetenzkatalog,
)


class FileSystemKompetenzkatalogRepository:
    """Laedt Kompetenzkataloge und Manifest aus Ressourcen-JSON-Dateien."""

    _RESOURCE_DIR = Path(__file__).resolve().parents[2] / "resources" / "kompetenzkataloge"
    _MANIFEST_NAME = "catalog_manifest.json"

    def _manifest_path(self) -> Path:
        values = load_path_values()
        configured = values.get(KOMPETENZ_MANIFEST_PATH_KEY, "")
        if configured:
            return resolve_path_value(configured)
        return self._RESOURCE_DIR / self._MANIFEST_NAME

    def default_manifest_path(self) -> Path:
        """Liefert den Standardpfad der Manifestdatei."""
        return self._manifest_path()

    def load_manifest_entries_from(self, manifest_path: Path) -> tuple[KompetenzkatalogManifestEntry, ...]:
        """Liest und validiert alle Eintraege aus einer Manifestdatei."""
        if not manifest_path.exists() or not manifest_path.is_file():
            raise FileNotFoundError(f"Kompetenz-Manifest nicht gefunden: {manifest_path}")

        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise KompetenzkatalogParseError(f"Manifest ist kein JSON-Objekt: {manifest_path}")

        entries_raw = raw.get("entries")
        if not isinstance(entries_raw, list):
            raise KompetenzkatalogParseError(f"Manifest-Feld 'entries' fehlt/ungueltig: {manifest_path}")

        entries: list[KompetenzkatalogManifestEntry] = []
        for item in entries_raw:
            if not isinstance(item, dict):
                raise KompetenzkatalogParseError(f"Ungueltiger Manifest-Eintrag in {manifest_path}")

            profile_id = str(item.get("profile_id", "")).strip()
            profile_label = str(item.get("profile_label", "")).strip()
            subject_code = str(item.get("subject_code", "")).strip().upper()
            file_name = str(item.get("file", "")).strip()
            grade_min = item.get("grade_min")
            grade_max = item.get("grade_max")

            if not profile_id or not profile_label or not subject_code or not file_name:
                raise KompetenzkatalogParseError(f"Unvollstaendiger Manifest-Eintrag in {manifest_path}")
            if not isinstance(grade_min, int) or not isinstance(grade_max, int):
                raise KompetenzkatalogParseError(f"Ungueltige Stufenwerte in Manifest-Eintrag {profile_id}")

            resource_dir = manifest_path.parent
            entries.append(
                KompetenzkatalogManifestEntry(
                    profile_id=profile_id,
                    profile_label=profile_label,
                    subject_code=subject_code,
                    grade_min=grade_min,
                    grade_max=grade_max,
                    file_path=resource_dir / file_name,
                )
            )

        return tuple(entries)

    def list_manifest_entries(self) -> tuple[KompetenzkatalogManifestEntry, ...]:
        """Liest und validiert alle Eintraege des Standard-Manifests."""
        return self.load_manifest_entries_from(self._manifest_path())

    def load_catalog_file(self, path: Path, profile_id: str) -> Kompetenzkatalog:
        """Liest und parst einen Kompetenzkatalog fuer ein Profil aus einer JSON-Datei."""
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Kompetenzkatalog-Datei nicht gefunden: {path}")

        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise KompetenzkatalogParseError(f"Katalog ist kein JSON-Objekt: {path}")

        profiles = raw.get("profiles")
        if isinstance(profiles, list):
            for item in profiles:
                if not isinstance(item, dict):
                    continue
                if str(item.get("profile_id", "")).strip() == profile_id:
                    return parse_kompetenzkatalog(item, str(path))
            raise KompetenzkatalogParseError(f"Profil '{profile_id}' nicht gefunden in {path}")

        # Fallback fuer Einzelprofil-Dateien
        return parse_kompetenzkatalog(raw, str(path))
