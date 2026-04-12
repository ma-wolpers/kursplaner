from datetime import datetime, time
from pathlib import Path
from typing import cast

from kursplaner.core.ports.repositories import UbRepository
from kursplaner.core.usecases.query_ub_achievements_usecase import QueryUbAchievementsUseCase


class _FakeUbRepo:
    def __init__(self, rows: list[tuple[list[str], bool]], paths: list[Path] | None = None):
        self._paths = paths or [Path(f"UB 20-01-{idx + 1:02d} Test.md") for idx, _ in enumerate(rows)]
        self._rows = rows

    def list_ub_markdown_files(self, _workspace_root: Path) -> list[Path]:
        return list(self._paths)

    def load_ub_markdown(self, ub_path: Path):
        idx = self._paths.index(ub_path)
        bereiche, langentwurf = self._rows[idx]
        yaml_data = {
            "Bereich": list(bereiche),
            "Langentwurf": bool(langentwurf),
        }
        return yaml_data, ""


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
        Path("UB 26-03-30 Bereits durchgeführt.md"),
        Path("UB 26-04-01 Zukünftig.md"),
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
    paths = [Path("UB 26-04-10 Heute.md")]
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
    paths = [Path("UB 26-04-10 Heute.md")]
    repo = _FakeUbRepo(rows, paths=paths)
    usecase = QueryUbAchievementsUseCase(
        ub_repo=cast(UbRepository, repo),
        past_cutoff_time_provider=lambda: time(hour=15, minute=0),
    )

    usecase._now = lambda: datetime(2026, 4, 10, 15, 0)  # type: ignore[method-assign]
    result = usecase.execute(workspace_root=Path("A:/7thCloud"))

    paed_half = next(item for item in result.items if item.key == "paed_half")
    assert paed_half.current == 1
