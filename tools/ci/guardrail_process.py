"""Kursplaner-Guardrails: Prozess-Checks (relevante Staged-Dateien, DEVELOPMENT_LOG/CHANGELOG, Hinweise)."""

from __future__ import annotations

from pathlib import Path

from guardrail_config import (  # noqa: E402
    CHANGELOG_CODEV_RELEVANT_PATHS,
    CHANGELOG_RELEVANT_PREFIXES,
    GUARDRAIL_RELEVANT_PATHS,
    PROCESS_GUIDANCE_RULES,
    ROOT,
    SHORTCUT_COVERAGE_SOFT_CHECKS,
)
from guardrail_support import (  # noqa: E402
    _is_future_gui_entry_path,
    _is_repo_gui_python_path,
    _read,
)


def _has_relevant_staged_changes(staged: set[str], repo_root: Path) -> bool:
    """Prüft robust, ob staged Änderungen guardrail-relevante Pfade betreffen."""
    try:
        root_rel_to_repo = str(ROOT.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        root_rel_to_repo = ""

    normalized_relevant: set[str] = set()
    for rel in GUARDRAIL_RELEVANT_PATHS:
        rel_norm = rel.replace("\\", "/")
        normalized_relevant.add(rel_norm)
        if root_rel_to_repo not in {"", "."}:
            normalized_relevant.add(f"{root_rel_to_repo}/{rel_norm}")

    for staged_path in staged:
        norm = staged_path.replace("\\", "/")
        if norm in normalized_relevant or _is_future_gui_entry_path(norm) or _is_repo_gui_python_path(norm):
            return True
    return False


def _check_development_log_updated(staged: set[str], errors: list[str]) -> None:
    """Erzwingt Log-Update bei relevanten Feature-/Architektur-Aenderungen."""
    normalized = {path.replace("\\", "/") for path in staged}
    if not normalized:
        return

    log_touched = "docs/DEVELOPMENT_LOG.md" in normalized

    requires_log = any(
        path.startswith("kursplaner/core/")
        or path.startswith("kursplaner/adapters/")
        or path.startswith("kursplaner/infrastructure/")
        or path.startswith("bw_libs/")
        or path == "docs/ARCHITEKTUR_KERN.md"
        for path in normalized
    )

    if requires_log and not log_touched:
        errors.append(
            "docs/DEVELOPMENT_LOG.md missing update: relevant feature/architecture changes require a same-cycle log entry"
        )


def _check_changelog_updated(staged: set[str], errors: list[str]) -> None:
    """Require changelog updates for user- or co-developer-relevant changes."""
    normalized = {path.replace("\\", "/") for path in staged}
    if not normalized:
        return

    if "CHANGELOG.md" in normalized:
        return

    requires_changelog = any(
        path.startswith(prefix) for path in normalized for prefix in CHANGELOG_RELEVANT_PREFIXES
    ) or any(path in CHANGELOG_CODEV_RELEVANT_PATHS for path in normalized)

    if requires_changelog:
        errors.append(
            "CHANGELOG.md missing update: user- or co-developer-relevant changes require a changelog entry"
        )


def _collect_process_guidance_warnings() -> list[str]:
    """Collect non-blocking warnings for commit/push process guidance drift."""
    warnings: list[str] = []
    sources = {
        "AGENTS.md": _read("AGENTS.md"),
        ".github/copilot-instructions.md": _read(".github/copilot-instructions.md"),
        ".github/pull_request_template.md": _read(".github/pull_request_template.md"),
    }

    for label, needle in PROCESS_GUIDANCE_RULES.items():
        if not any(needle in text for text in sources.values()):
            warnings.append(
                f"process-guidance ({label}) not found in governance docs/templates"
            )
    return warnings


def _has_any_marker(rel_paths: tuple[str, ...], markers: tuple[str, ...]) -> bool:
    """Return whether any marker appears in at least one existing source file."""

    for rel_path in rel_paths:
        path = ROOT / rel_path
        if not path.exists():
            continue
        text = _read(rel_path)
        if any(marker in text for marker in markers):
            return True
    return False


def _collect_shortcut_coverage_warnings() -> list[str]:
    """Collect non-blocking warnings when key intents miss keyboard shortcut markers."""

    warnings: list[str] = []
    for check in SHORTCUT_COVERAGE_SOFT_CHECKS:
        intent_paths = tuple(check["intent_paths"])
        intent_markers = tuple(check["intent_markers"])
        shortcut_paths = tuple(check["shortcut_paths"])
        shortcut_markers = tuple(check["shortcut_markers"])
        if not _has_any_marker(intent_paths, intent_markers):
            continue
        if _has_any_marker(shortcut_paths, shortcut_markers):
            continue
        warnings.append(
            f"shortcut-coverage ({check['label']}): intent marker found without configured keyboard binding marker"
        )
    return warnings
