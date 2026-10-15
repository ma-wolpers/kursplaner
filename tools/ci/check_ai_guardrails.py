#!/usr/bin/env python3
"""Kursplaner-Guardrails: Einstieg fuer lokale Laeufe, Pre-commit und CI (``python tools/ci/check_ai_guardrails.py``).

Konfiguration in ``guardrail_config.py``, Helfer in ``guardrail_support.py``,
Prozess-Checks in ``guardrail_process.py``, Architektur-Checks in ``guardrail_checks.py``,
GUI-Contract-Checks in ``guardrail_gui_checks.py``. Die Module liegen neben diesem Skript
und importieren sich gegenseitig als Top-Level-Module; dieses Skript nimmt seinen Ordner
in ``sys.path`` auf, damit das auch beim Paketimport (``from tools.ci import
check_ai_guardrails`` in Tests) funktioniert.
"""
from __future__ import annotations

import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from guardrail_checks import (  # noqa: E402
    _check_lesson_index_observability,
    _check_main_window_intent_delegation,
    _check_required_docstrings,
    _check_undo_writeflow_guardrails,
)
from guardrail_gui_checks import (  # noqa: E402
    _check_future_gui_entry_contracts,
    _check_gui_migration_backlog,
    _check_laufkern_fallback_sunset,
    _check_repo_wide_gui_contracts,
    _check_runtime_shortcut_integration,
    _check_shared_ui_contract_hardening,
    _check_ui_contract_bridge_decommission,
)
from guardrail_process import (  # noqa: E402
    _check_changelog_updated,
    _check_development_log_updated,
    _collect_process_guidance_warnings,
    _collect_shortcut_coverage_warnings,
    _has_relevant_staged_changes,
)
from guardrail_support import (  # noqa: E402
    _is_ci_environment,
    _read,
    _repo_root,
    _require_substring,
    _staged_files,
)


def main() -> int:
    """Führt robuste Guardrail-Checks aus und gibt einen CI-kompatiblen Exitcode zurück."""
    repo_root = _repo_root()
    staged = _staged_files(repo_root)
    if staged and not _has_relevant_staged_changes(staged, repo_root):
        print("AI guardrail check skipped (no guardrail-relevant staged files).")
        return 0

    errors: list[str] = []

    # Guardrail files must exist.
    _read("AGENTS.md")
    _read(".github/copilot-instructions.md")
    _read(".github/workflows/repo-path-guardrails.yml")
    _read(".github/pull_request_template.md")
    _read("tools/repo_ci/check_no_absolute_paths.py")
    _read("bw_libs/ui_contract/keybinding.py")
    _read("bw_libs/ui_contract/popup.py")
    _read("bw_libs/ui_contract/hsm.py")
    _read("bw_libs/ui_contract/laufkern.py")
    _read("bw_libs/app_paths.py")

    _check_main_window_intent_delegation(errors)
    _check_lesson_index_observability(errors)
    _check_required_docstrings(errors)
    _check_development_log_updated(staged, errors)
    _check_changelog_updated(staged, errors)
    _check_undo_writeflow_guardrails(errors)
    _check_runtime_shortcut_integration(errors)
    _check_shared_ui_contract_hardening(errors)
    _check_laufkern_fallback_sunset(errors)
    _check_ui_contract_bridge_decommission(errors)
    _check_future_gui_entry_contracts(errors)
    _check_repo_wide_gui_contracts(errors)
    _check_gui_migration_backlog(errors)
    warnings = _collect_process_guidance_warnings()
    warnings.extend(_collect_shortcut_coverage_warnings())

    # Doku must keep architecture orientation + open-work-only plan wording.
    arch_core = _read("docs/ARCHITEKTUR_KERN.md")
    _require_substring(
        arch_core,
        "GUI-Infrastruktur-Orientierung",
        "ARCHITEKTUR_KERN.md",
        errors,
    )
    _require_substring(
        arch_core,
        "Persistierte Pfadwerte werden **immer relativ zum konfigurierten Workspace-Stamm** gespeichert.",
        "ARCHITEKTUR_KERN.md",
        errors,
    )

    path_store = _read("kursplaner/core/config/path_store.py")
    _require_substring(
        path_store,
        "def serialize_workspace_relative_path(path: Path) -> str:",
        "path_store.py",
        errors,
    )

    daily_log_uc = _read("kursplaner/core/usecases/daily_course_log_usecase.py")
    _require_substring(
        daily_log_uc,
        "serialize_workspace_relative_path(unterricht_dir)",
        "daily_course_log_usecase.py",
        errors,
    )
    _require_substring(
        daily_log_uc,
        "serialize_workspace_relative_path(link_path)",
        "daily_course_log_usecase.py",
        errors,
    )

    lesson_index_repo = _read("kursplaner/infrastructure/repositories/lesson_index_repository.py")
    _require_substring(
        lesson_index_repo,
        "serialize_workspace_relative_path(unterricht_dir)",
        "lesson_index_repository.py",
        errors,
    )
    _require_substring(
        lesson_index_repo,
        "serialize_workspace_relative_path(entry.path)",
        "lesson_index_repository.py",
        errors,
    )

    plan_doc = _read("docs/ARCHITEKTUR_UMSETZUNGSPLAN.md")
    _require_substring(
        plan_doc,
        "nur offene Punkte",
        "ARCHITEKTUR_UMSETZUNGSPLAN.md",
        errors,
    )

    repo_path_workflow = _read(".github/workflows/repo-path-guardrails.yml")
    _require_substring(
        repo_path_workflow,
        "python tools/repo_ci/check_no_absolute_paths.py",
        "repo-path-guardrails.yml",
        errors,
    )

    if errors:
        print("AI guardrail check failed:")
        for item in errors:
            print(f" - {item}")
        return 2

    if warnings and not _is_ci_environment():
        print("AI guardrail process warnings (non-blocking):")
        for item in warnings:
            print(f" - {item}")

    print("AI guardrail check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
