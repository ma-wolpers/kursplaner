from kursplaner.core.domain.markdown_lists import markdown_bullet_lines


def test_markdown_bullet_lines_prefix_each_item():
    assert markdown_bullet_lines(["[[a]]", "[[b]]"]) == ["- [[a]]", "- [[b]]"]


def test_markdown_bullet_lines_empty_list_gives_no_lines():
    assert markdown_bullet_lines([]) == []
