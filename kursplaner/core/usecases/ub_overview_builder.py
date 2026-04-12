from __future__ import annotations

from pathlib import Path

from kursplaner.core.domain.unterrichtsbesuch_policy import (
    UB_YAML_KEY_BEREICH,
    UB_YAML_KEY_LANGENTWURF,
)
from kursplaner.core.ports.repositories import UbRepository


def _to_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    return [text] if text else []


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"true", "1", "ja", "yes"}


def build_ub_overview_markdown(ub_repo: UbRepository, workspace_root: Path) -> str:
    """Erstellt die vollständige UB-Übersicht aus den vorhandenen UB-Dateien."""
    entries: list[tuple[str, str, str]] = []
    for ub_path in ub_repo.list_ub_markdown_files(workspace_root):
        try:
            yaml_data, _ = ub_repo.load_ub_markdown(ub_path)
        except Exception:
            continue

        bereich_items = _to_list(yaml_data.get(UB_YAML_KEY_BEREICH, []))
        bereich_text = " + ".join(bereich_items) if bereich_items else "-"
        lang_marker = "Ja" if _to_bool(yaml_data.get(UB_YAML_KEY_LANGENTWURF, False)) else "Nein"
        entries.append((ub_path.stem, bereich_text, lang_marker))

    entries.sort(key=lambda item: item[0].lower())
    lines = [
        "# UB Übersicht",
        "",
        "| UB | Bereich | Langentwurf |",
        "| --- | --- | --- |",
    ]
    for stem, bereich_text, lang_marker in entries:
        lines.append(f"| [[{stem}]] | {bereich_text} | {lang_marker} |")
    return "\n".join(lines) + "\n"
