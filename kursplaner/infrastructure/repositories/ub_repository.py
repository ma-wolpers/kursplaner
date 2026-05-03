from __future__ import annotations

import re
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
from kursplaner.core.domain.yaml_registry import YamlSchema, parse_yaml_frontmatter

_UB_SCHEMA = YamlSchema(
    label="UB-Datei",
    required_keys=(UB_YAML_KEY_BEREICH, UB_YAML_KEY_LANGENTWURF, UB_YAML_KEY_BEOBACHTUNG, UB_YAML_KEY_EINHEIT),
    non_empty_keys=(UB_YAML_KEY_EINHEIT,),
)
WIKI_LINK_VALUE_RE = re.compile(r"^\s*\[\[[^\]]+\]\]\s*$")
MARKDOWN_LINK_VALUE_RE = re.compile(r"^\s*\[[^\]]+\]\([^\)]+\.md\)\s*$", re.IGNORECASE)


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

    def unique_ub_markdown_path(self, workspace_root: Path, stem: str) -> Path:
        """Ermittelt einen kollisionsfreien UB-Dateipfad mit .md-Endung."""
        root = self.ensure_ub_root(workspace_root)
        cleaned = str(stem or "").strip() or "UB 00-00-00 Einheit"
        base = root / f"{cleaned}.md"
        if not base.exists():
            return base

        suffix = 2
        while True:
            candidate = root / f"{cleaned} {suffix}.md"
            if not candidate.exists():
                return candidate
            suffix += 1

    @staticmethod
    def _to_yaml_scalar(value: object) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value or "")

    @staticmethod
    def _render_yaml_frontmatter(yaml_data: dict[str, object]) -> str:
        ordered_keys = (
            UB_YAML_KEY_BEREICH,
            UB_YAML_KEY_LANGENTWURF,
            UB_YAML_KEY_BEOBACHTUNG,
            UB_YAML_KEY_EINHEIT,
        )
        lines = ["---"]
        for key in ordered_keys:
            value = yaml_data.get(key, "")
            if isinstance(value, list):
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f'  - "{str(item)}"')
            else:
                scalar = FileSystemUbRepository._to_yaml_scalar(value)
                if WIKI_LINK_VALUE_RE.fullmatch(scalar) or MARKDOWN_LINK_VALUE_RE.fullmatch(scalar):
                    escaped = scalar.replace('"', '\\"')
                    lines.append(f'{key}: "{escaped}"')
                else:
                    lines.append(f"{key}: {scalar}")
        lines.append("---")
        return "\n".join(lines) + "\n\n"

    @staticmethod
    def _render_list_section(title: str, entries: list[str]) -> str:
        lines = [f"## {title}", ""]
        if entries:
            lines.extend(f"- {item.strip()}" for item in entries if item and item.strip())
        else:
            lines.append("- ")
        return "\n".join(lines)

    def save_ub_markdown(
        self,
        ub_path: Path,
        yaml_data: dict[str, object],
        reflection_text: str,
        professional_steps: list[str],
        usable_resources: list[str],
    ) -> None:
        """Schreibt UB-Frontmatter plus Standardstruktur fuer Reflexion/Entwicklung."""
        ub_path.parent.mkdir(parents=True, exist_ok=True)

        reflection = str(reflection_text or "").strip()
        body_sections = ["# Reflexion", "", reflection]
        body_sections.append("")
        body_sections.append(self._render_list_section("Professionalisierungsschritte", professional_steps))
        body_sections.append("")
        body_sections.append(self._render_list_section("Nutzbare Ressourcen", usable_resources))

        frontmatter = self._render_yaml_frontmatter(yaml_data)
        body = "\n".join(body_sections).strip() + "\n"
        atomic_write_text(ub_path, frontmatter + body, encoding="utf-8")

    def load_ub_markdown(self, ub_path: Path) -> tuple[dict[str, object], str]:
        """Liest UB-Frontmatter plus restlichen Markdown-Body."""
        text = ub_path.read_text(encoding="utf-8")
        yaml_data, _ = parse_yaml_frontmatter(text, _UB_SCHEMA, source_label=str(ub_path))

        body = text
        if body.startswith("---\n"):
            end = body.find("\n---", 4)
            if end != -1:
                body = body[end + 4 :]
                if body.startswith("\n"):
                    body = body[1:]
        return yaml_data, body

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
