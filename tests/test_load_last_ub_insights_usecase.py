from datetime import datetime, time
from pathlib import Path
from typing import cast

from kursplaner.core.ports.repositories import UbRepository
from kursplaner.core.usecases.load_last_ub_insights_usecase import LoadLastUbInsightsUseCase


class _FakeUbRepo:
    def __init__(self, ordered_files: list[Path], content_by_file: dict[Path, tuple[dict[str, object], str]]):
        self._ordered_files = ordered_files
        self._content_by_file = content_by_file

    def list_ub_markdown_files(self, _workspace_root: Path) -> list[Path]:
        return list(self._ordered_files)

    def load_ub_markdown(self, path: Path) -> tuple[dict[str, object], str]:
        return self._content_by_file[path]


def _body(step: str, resource: str) -> str:
    return (
        f"# Reflexion\n- kurz\n\n## Professionalisierungsschritte\n- {step}\n\n## Nutzbare Ressourcen\n- {resource}\n"
    )


def test_execute_collects_latest_domain_sections_and_places_paedagogik_last():
    old_math = Path("UB old math.md")
    latest_inf = Path("UB latest inf.md")
    latest_paed = Path("UB latest paed.md")
    ordered = [old_math, latest_inf, latest_paed]
    content: dict[Path, tuple[dict[str, object], str]] = {
        old_math: ({"Bereich": ["Mathematik"]}, _body("M-alt", "MR-alt")),
        latest_inf: ({"Bereich": ["Informatik"]}, _body("I-neu", "IR-neu")),
        latest_paed: ({"Bereich": ["Pädagogik"]}, _body("P-neu", "PR-neu")),
    }
    usecase = LoadLastUbInsightsUseCase(ub_repo=cast(UbRepository, _FakeUbRepo(ordered, content)))

    result = usecase.execute(workspace_root=Path("A:/7thCloud"), subject_name="Informatik")

    assert [section.domain_name for section in result.domain_sections] == ["Informatik", "Mathematik", "Pädagogik"]
    assert result.domain_sections[0].steps == ["I-neu"]
    assert result.domain_sections[2].resources == ["PR-neu"]


def test_execute_keeps_subject_and_paedagogik_fields_for_existing_callers():
    latest_inf = Path("UB latest inf.md")
    latest_paed = Path("UB latest paed.md")
    ordered = [latest_inf, latest_paed]
    content: dict[Path, tuple[dict[str, object], str]] = {
        latest_inf: ({"Bereich": ["Informatik"]}, _body("I-neu", "IR-neu")),
        latest_paed: ({"Bereich": ["Pädagogik"]}, _body("P-neu", "PR-neu")),
    }
    usecase = LoadLastUbInsightsUseCase(ub_repo=cast(UbRepository, _FakeUbRepo(ordered, content)))

    result = usecase.execute(workspace_root=Path("A:/7thCloud"), subject_name="Informatik")

    assert result.subject_steps == ["I-neu"]
    assert result.subject_resources == ["IR-neu"]
    assert result.paedagogik_steps == ["P-neu"]
    assert result.paedagogik_resources == ["PR-neu"]


def test_execute_ignores_same_day_ub_before_configured_cutoff():
    today = datetime(2026, 4, 10, 14, 30)
    today_inf = Path("UB 26-04-10 Heute Inf.md")
    yesterday_inf = Path("UB 26-04-09 Gestern Inf.md")
    ordered = [yesterday_inf, today_inf]
    content: dict[Path, tuple[dict[str, object], str]] = {
        today_inf: ({"Bereich": ["Informatik"]}, _body("I-heute", "IR-heute")),
        yesterday_inf: ({"Bereich": ["Informatik"]}, _body("I-gestern", "IR-gestern")),
    }
    usecase = LoadLastUbInsightsUseCase(
        ub_repo=cast(UbRepository, _FakeUbRepo(ordered, content)),
        past_cutoff_time_provider=lambda: time(hour=15, minute=0),
    )

    usecase._now = lambda: today  # type: ignore[method-assign]
    result = usecase.execute(workspace_root=Path("A:/7thCloud"), subject_name="Informatik")

    assert result.subject_steps == ["I-gestern"]
    assert result.subject_resources == ["IR-gestern"]


def test_execute_counts_same_day_ub_after_configured_cutoff():
    today = datetime(2026, 4, 10, 15, 1)
    today_inf = Path("UB 26-04-10 Heute Inf.md")
    yesterday_inf = Path("UB 26-04-09 Gestern Inf.md")
    ordered = [yesterday_inf, today_inf]
    content: dict[Path, tuple[dict[str, object], str]] = {
        today_inf: ({"Bereich": ["Informatik"]}, _body("I-heute", "IR-heute")),
        yesterday_inf: ({"Bereich": ["Informatik"]}, _body("I-gestern", "IR-gestern")),
    }
    usecase = LoadLastUbInsightsUseCase(
        ub_repo=cast(UbRepository, _FakeUbRepo(ordered, content)),
        past_cutoff_time_provider=lambda: time(hour=15, minute=0),
    )

    usecase._now = lambda: today  # type: ignore[method-assign]
    result = usecase.execute(workspace_root=Path("A:/7thCloud"), subject_name="Informatik")

    assert result.subject_steps == ["I-heute"]
    assert result.subject_resources == ["IR-heute"]
