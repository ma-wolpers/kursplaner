from datetime import datetime, time
from pathlib import Path
from typing import cast

from kursplaner.core.domain.achievement_grade_rules import GradeRequirement
from kursplaner.core.ports.repositories import AchievementGradeRequirementsRepository, UbRepository
from kursplaner.core.usecases.query_ub_achievements_usecase import QueryUbAchievementsUseCase


class _FakeUbRepo:
    def __init__(
        self,
        rows: list[tuple[list[str], bool]],
        paths: list[Path] | None = None,
        jahrgangsstufen: list[int | None] | None = None,
    ):
        self._paths = paths or [Path(f"ub 20-01-{idx + 1:02d}.md") for idx, _ in enumerate(rows)]
        self._rows = rows
        self._jahrgangsstufen = jahrgangsstufen or [None] * len(rows)

    def list_ub_markdown_files(self, _workspace_root: Path) -> list[Path]:
        return list(self._paths)

    def load_ub_markdown(self, ub_path: Path):
        idx = self._paths.index(ub_path)
        bereiche, langentwurf = self._rows[idx]
        yaml_data = {
            "Bereich": list(bereiche),
            "Langentwurf": bool(langentwurf),
            "Jahrgangsstufe": self._jahrgangsstufen[idx],
        }
        return yaml_data, ""


class _FakeGradeRequirementsRepo:
    def __init__(self, requirements: dict[str, tuple[GradeRequirement, ...]]):
        self._requirements = requirements

    def load_requirements(self) -> dict[str, tuple[GradeRequirement, ...]]:
        return self._requirements


def test_query_ub_achievements_exposes_structured_fields_and_symbols():
    repo = _FakeUbRepo(
        [
            (["Pädagogik", "Mathematik"], True),
            (["Pädagogik", "Informatik"], True),
            (["Darstellendes Spiel"], False),
        ]
    )
    usecase = QueryUbAchievementsUseCase(ub_repo=cast(UbRepository, repo))

    result = usecase.execute(workspace_root=Path("A:/7thCloud"))

    sample = next(item for item in result.items if item.key == "Mathematik_ubplus")
    assert sample.domain == "Mathematik"
    assert sample.category == "ubplus"
    assert sample.symbol == "∑"
    assert sample.title == "Mat UBplus"
    assert sample.is_fulfilled is True


def test_query_ub_achievements_applies_domain_rules_for_paedagogik_and_dsp():
    repo = _FakeUbRepo(
        [
            (["Pädagogik", "Mathematik"], True),
            (["Pädagogik", "Informatik"], True),
            (["Darstellendes Spiel"], True),
        ]
    )
    usecase = QueryUbAchievementsUseCase(ub_repo=cast(UbRepository, repo))

    result = usecase.execute(workspace_root=Path("A:/7thCloud"))
    keys = {item.key for item in result.items}

    assert "paed_bub" in keys
    paed_bub = next(item for item in result.items if item.key == "paed_bub")
    assert paed_bub.current == 2
    assert paed_bub.target == 2
    assert paed_bub.is_fulfilled is True

    assert "Darstellendes Spiel_ubplus" not in keys
    assert "Darstellendes Spiel_bub" not in keys


def test_query_ub_achievements_sorts_fulfilled_then_category_then_domain():
    repo = _FakeUbRepo(
        [
            (["Pädagogik", "Mathematik"], True),
            (["Pädagogik"], False),
            (["Darstellendes Spiel"], False),
        ]
    )
    usecase = QueryUbAchievementsUseCase(ub_repo=cast(UbRepository, repo))

    result = usecase.execute(workspace_root=Path("A:/7thCloud"))

    fulfilled_prefix = []
    for item in result.items:
        if item.is_fulfilled:
            fulfilled_prefix.append(item)
        else:
            break
    assert fulfilled_prefix
    assert all(item.is_fulfilled for item in fulfilled_prefix)

    first_unfulfilled_index = len(fulfilled_prefix)
    if first_unfulfilled_index < len(result.items):
        assert all(not item.is_fulfilled for item in result.items[first_unfulfilled_index:])


def test_query_ub_achievements_counts_only_strict_past_dates():
    rows = [
        (["Pädagogik", "Mathematik"], False),
        (["Pädagogik", "Mathematik"], False),
    ]
    paths = [
        Path("ub 26-03-30.md"),
        Path("ub 26-04-01.md"),
    ]
    repo = _FakeUbRepo(rows, paths=paths)
    usecase = QueryUbAchievementsUseCase(ub_repo=cast(UbRepository, repo))
    usecase._now = lambda: datetime(2026, 3, 31, 10, 0)  # type: ignore[method-assign]

    result = usecase.execute(workspace_root=Path("A:/7thCloud"))

    paed_half = next(item for item in result.items if item.key == "paed_half")
    mat_half = next(item for item in result.items if item.key == "Mathematik_half")
    assert paed_half.current == 1
    assert mat_half.current == 1


def test_query_ub_achievements_excludes_same_day_before_cutoff():
    rows = [
        (["Pädagogik", "Mathematik"], False),
    ]
    paths = [Path("ub 26-04-10.md")]
    repo = _FakeUbRepo(rows, paths=paths)
    usecase = QueryUbAchievementsUseCase(
        ub_repo=cast(UbRepository, repo),
        past_cutoff_time_provider=lambda: time(hour=15, minute=0),
    )

    usecase._now = lambda: datetime(2026, 4, 10, 14, 59)  # type: ignore[method-assign]
    result = usecase.execute(workspace_root=Path("A:/7thCloud"))

    paed_half = next(item for item in result.items if item.key == "paed_half")
    assert paed_half.current == 0


def test_query_ub_achievements_includes_same_day_after_cutoff():
    rows = [
        (["Pädagogik", "Mathematik"], False),
    ]
    paths = [Path("ub 26-04-10.md")]
    repo = _FakeUbRepo(rows, paths=paths)
    usecase = QueryUbAchievementsUseCase(
        ub_repo=cast(UbRepository, repo),
        past_cutoff_time_provider=lambda: time(hour=15, minute=0),
    )

    usecase._now = lambda: datetime(2026, 4, 10, 15, 0)  # type: ignore[method-assign]
    result = usecase.execute(workspace_root=Path("A:/7thCloud"))

    paed_half = next(item for item in result.items if item.key == "paed_half")
    assert paed_half.current == 1


def test_query_ub_achievements_ignores_domainless_zusatzbesuch_entries():
    repo = _FakeUbRepo(
        [
            ([], False),
            (["Pädagogik"], False),
        ]
    )
    usecase = QueryUbAchievementsUseCase(ub_repo=cast(UbRepository, repo))

    result = usecase.execute(workspace_root=Path("A:/7thCloud"))

    paed_half = next(item for item in result.items if item.key == "paed_half")
    mat_half = next(item for item in result.items if item.key == "Mathematik_half")
    assert paed_half.current == 1
    assert mat_half.current == 0


def test_query_ub_achievements_without_grade_requirements_repo_adds_no_grade_items():
    """Regressionstest: ohne konfiguriertes Repo darf sich an der bestehenden
    Achievement-Liste nichts aendern (current/target-Semantik unangetastet)."""
    repo = _FakeUbRepo([(["Pädagogik"], False)], jahrgangsstufen=[5])
    usecase = QueryUbAchievementsUseCase(ub_repo=cast(UbRepository, repo))

    result = usecase.execute(workspace_root=Path("A:/7thCloud"))

    assert not any(item.key.startswith("Pädagogik_grade_") for item in result.items)


def test_query_ub_achievements_with_empty_requirements_adds_no_grade_items():
    """Ein Fach mit leerer Vorgaben-Liste gilt als nicht konfiguriert -- keine Fake-Items."""
    repo = _FakeUbRepo([(["Pädagogik"], False)], jahrgangsstufen=[5])
    usecase = QueryUbAchievementsUseCase(
        ub_repo=cast(UbRepository, repo),
        grade_requirements_repo=cast(AchievementGradeRequirementsRepository, _FakeGradeRequirementsRepo({})),
    )

    result = usecase.execute(workspace_root=Path("A:/7thCloud"))

    assert not any(item.key.startswith("Pädagogik_grade_") for item in result.items)


def test_query_ub_achievements_reports_configured_grade_group_progress():
    repo = _FakeUbRepo(
        [
            (["Pädagogik"], False),
            (["Pädagogik"], False),
            (["Pädagogik"], False),
        ],
        jahrgangsstufen=[5, 5, 9],
    )
    requirements = {
        "Pädagogik": (
            GradeRequirement(label="5./6.", grade_min=5, grade_max=6, min_count=1),
            GradeRequirement(label="7.-10.", grade_min=7, grade_max=10, min_count=1),
            GradeRequirement(label="11.-13.", grade_min=11, grade_max=13, min_count=1),
        )
    }
    usecase = QueryUbAchievementsUseCase(
        ub_repo=cast(UbRepository, repo),
        grade_requirements_repo=cast(AchievementGradeRequirementsRepository, _FakeGradeRequirementsRepo(requirements)),
    )

    result = usecase.execute(workspace_root=Path("A:/7thCloud"))

    group_5_6 = next(item for item in result.items if item.key == "Pädagogik_grade_0")
    group_7_10 = next(item for item in result.items if item.key == "Pädagogik_grade_1")
    group_11_13 = next(item for item in result.items if item.key == "Pädagogik_grade_2")

    assert group_5_6.title == "Päd 5./6."
    # `current` wird wie bei allen anderen Achievements auf `target` gekappt (2 tatsaechliche
    # Treffer, aber Anzeige nie > target) -- dieselbe bestehende Semantik, keine neue.
    assert (group_5_6.current, group_5_6.target, group_5_6.is_fulfilled) == (1, 1, True)
    assert (group_7_10.current, group_7_10.target, group_7_10.is_fulfilled) == (1, 1, True)
    assert (group_11_13.current, group_11_13.target, group_11_13.is_fulfilled) == (0, 1, False)

    # Fach ohne Vorgaben bleibt unberuehrt.
    assert not any(item.key.startswith("Mathematik_grade_") for item in result.items)
