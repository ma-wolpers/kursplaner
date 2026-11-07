from __future__ import annotations

from pathlib import Path

from bw_libs.app_paths import atomic_write_text
from kursplaner.core.domain.unterrichtsbesuch_policy import (
    UB_OVERVIEW_FILE_NAME,
    UB_ROOT_RELATIVE_PARTS,
    UB_YAML_KEY_BEOBACHTUNG,
    UB_YAML_KEY_BEREICH,
    UB_YAML_KEY_EINHEIT,
    UB_YAML_KEY_LANGENTWURF,
)
from kursplaner.core.domain.yaml_registry import (
    YamlSchema,
    body_after_frontmatter,
    parse_yaml_frontmatter,
    render_yaml_frontmatter,
)

_UB_SCHEMA = YamlSchema(
    label="UB-Datei",
    required_keys=(UB_YAML_KEY_BEREICH, UB_YAML_KEY_LANGENTWURF, UB_YAML_KEY_BEOBACHTUNG, UB_YAML_KEY_EINHEIT),
    non_empty_keys=(UB_YAML_KEY_EINHEIT,),
)
"""Kein geschlossenes Schluesselset: Altdateien mit einem inzwischen entfernten
`Jahrgangsstufe`-Feld (vor der Umstellung auf die Kurs-`Stufe` als Single
Source of Truth) laden weiterhin fehlerfrei, da nur `required_keys`/
`non_empty_keys` geprueft werden; das obsolete Feld faellt beim naechsten
Speichern automatisch weg (siehe `_UB_ORDERED_KEYS`)."""
_UB_ORDERED_KEYS = (
    UB_YAML_KEY_BEREICH,
    UB_YAML_KEY_LANGENTWURF,
    UB_YAML_KEY_BEOBACHTUNG,
    UB_YAML_KEY_EINHEIT,
)


class FileSystemUbRepository:
    """Dateisystem-Repository fuer UB-Markdowns und die UB-Uebersicht."""

    @staticmethod
    def _ub_root(workspace_root: Path) -> Path:
        root = workspace_root.expanduser().resolve()
        return root.joinpath(*UB_ROOT_RELATIVE_PARTS)

    def ensure_ub_root(self, workspace_root: Path) -> Path:
        """Stellt den zentralen UB-Ordner sicher und liefert ihn zurueck."""
        root = self._ub_root(workspace_root)
        root.mkdir(parents=True, exist_ok=True)
        return root

    def ub_overview_path(self, workspace_root: Path) -> Path:
        """Liefert den Zielpfad der UB-Uebersichtsdatei."""
        return self.ensure_ub_root(workspace_root) / UB_OVERVIEW_FILE_NAME

    def ub_markdown_path(self, workspace_root: Path, stem: str) -> Path:
        """Pfad der UB-Datei zu einem Dateistamm – einzige Stelle der Namensregel (``<UB-Ordner>/<stem>.md``)."""
        return self.ensure_ub_root(workspace_root) / f"{str(stem).strip()}.md"

    def unique_ub_markdown_path(self, workspace_root: Path, stem: str) -> Path:
        """Ermittelt einen kollisionsfreien UB-Dateipfad mit .md-Endung."""
        cleaned = str(stem or "").strip() or "ub 00-00-00"
        base = self.ub_markdown_path(workspace_root, cleaned)
        if not base.exists():
            return base

        suffix = 2
        while True:
            candidate = self.ub_markdown_path(workspace_root, f"{cleaned} {suffix}")
            if not candidate.exists():
                return candidate
            suffix += 1

    @staticmethod
    def _render_yaml_frontmatter(yaml_data: dict[str, object]) -> str:
        """Rendert die UB-Frontmatter über die zentrale `yaml_registry.render_yaml_frontmatter`.

        UB-Dateien tragen immer alle fünf Schlüssel (auch leer), anders als
        Lesson-Dateien, die fehlende Schlüssel überspringen — daher wird
        `values` hier vorab mit `.get(key, "")` für jeden Key befüllt, statt
        `yaml_data` direkt durchzureichen.
        """
        values = {key: yaml_data.get(key, "") for key in _UB_ORDERED_KEYS}
        return render_yaml_frontmatter(_UB_ORDERED_KEYS, values)

    def save_ub_markdown(self, ub_path: Path, yaml_data: dict[str, object], body: str) -> None:
        """Schreibt UB-Frontmatter plus *body* wörtlich (Struktur des Bodys: `ub_markdown_sections`).

        Das Repository rendert den Body nicht selbst: Use Cases reichen den
        bestehenden Body durch und ändern nur die Abschnitte, die sie betreffen,
        damit zusätzlicher Text der Nutzerin nie verloren geht.
        """
        ub_path.parent.mkdir(parents=True, exist_ok=True)
        text = str(body or "").lstrip("\n")
        if text and not text.endswith("\n"):
            text += "\n"
        atomic_write_text(ub_path, self._render_yaml_frontmatter(yaml_data) + text, encoding="utf-8")

    def load_ub_markdown(self, ub_path: Path) -> tuple[dict[str, object], str]:
        """Liest UB-Frontmatter plus restlichen Markdown-Body."""
        text = ub_path.read_text(encoding="utf-8")
        yaml_data, raw_text = parse_yaml_frontmatter(text, _UB_SCHEMA, source_label=str(ub_path))
        return yaml_data, body_after_frontmatter(raw_text)

    def list_ub_markdown_files(self, workspace_root: Path) -> list[Path]:
        """Listet UB-Markdowns sortiert nach Dateiname."""
        root = self.ensure_ub_root(workspace_root)
        return sorted(
            [path for path in root.glob("*.md") if path.name != UB_OVERVIEW_FILE_NAME],
            key=lambda item: item.name.lower(),
        )

    def save_ub_overview(self, workspace_root: Path, markdown: str) -> Path:
        """Speichert die Uebersichts-Markdown und liefert den Zielpfad zurueck."""
        path = self.ub_overview_path(workspace_root)
        text = str(markdown or "")
        if text and not text.endswith("\n"):
            text += "\n"
        atomic_write_text(path, text, encoding="utf-8")
        return path

    def load_ub_overview(self, workspace_root: Path) -> str:
        """Liest die Uebersichts-Markdown oder liefert leer bei Nichtvorhandensein."""
        path = self.ub_overview_path(workspace_root)
        if not path.exists() or not path.is_file():
            return ""
        return path.read_text(encoding="utf-8")

    def rename_ub_markdown(self, source: Path, target: Path) -> Path:
        """Benennt eine UB-Datei um und gibt den Zielpfad zurück."""
        source_resolved = source.expanduser().resolve()
        target_resolved = target.expanduser().resolve()
        target_resolved.parent.mkdir(parents=True, exist_ok=True)
        if source_resolved == target_resolved:
            return target_resolved
        return source_resolved.rename(target_resolved)

    def delete_ub_markdown(self, path: Path) -> None:
        """Löscht eine UB-Datei, falls sie vorhanden ist."""
        target = path.expanduser().resolve()
        if target.exists() and target.is_file():
            target.unlink()
