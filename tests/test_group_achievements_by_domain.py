from kursplaner.core.usecases.query_ub_achievements_usecase import (
    AchievementProgress,
    group_achievements_by_domain,
)


def _item(*, key: str, domain: str, current: int, target: int) -> AchievementProgress:
    return AchievementProgress(
        key=key,
        domain=domain,
        category="half",
        symbol="?",
        title=key,
        current=current,
        target=target,
        tooltip="",
        is_fulfilled=current >= target,
    )


def test_group_achievements_by_domain_orders_groups_by_domain_order():
    items = [
        _item(key="mat", domain="Mathematik", current=1, target=4),
        _item(key="paed", domain="Pädagogik", current=1, target=5),
        _item(key="inf", domain="Informatik", current=1, target=4),
    ]

    groups = group_achievements_by_domain(items, domain_order=("Pädagogik", "Mathematik", "Informatik"))

    assert [group.domain for group in groups] == ["Pädagogik", "Mathematik", "Informatik"]


def test_group_achievements_by_domain_sorts_within_group_by_completion_ratio_desc():
    items = [
        _item(key="low", domain="Mathematik", current=1, target=4),  # 0.25
        _item(key="high", domain="Mathematik", current=3, target=4),  # 0.75
        _item(key="complete", domain="Mathematik", current=4, target=4),  # 1.0
    ]

    groups = group_achievements_by_domain(items, domain_order=("Mathematik",))

    assert [item.key for item in groups[0].items] == ["complete", "high", "low"]


def test_group_achievements_by_domain_skips_domains_without_items():
    items = [_item(key="mat", domain="Mathematik", current=1, target=4)]

    groups = group_achievements_by_domain(items, domain_order=("Pädagogik", "Mathematik", "Informatik"))

    assert [group.domain for group in groups] == ["Mathematik"]


def test_group_achievements_by_domain_uses_default_domain_order():
    items = [
        _item(key="mat", domain="Mathematik", current=1, target=4),
        _item(key="paed", domain="Pädagogik", current=1, target=5),
    ]

    groups = group_achievements_by_domain(items)

    assert [group.domain for group in groups] == ["Pädagogik", "Mathematik"]
