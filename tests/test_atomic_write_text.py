from bw_libs.app_paths import atomic_write_text


def test_atomic_write_text_keeps_lf_line_endings(tmp_path):
    target = tmp_path / "sub" / "datei.md"

    atomic_write_text(target, "---\nx: 1\n---\n\nText\n")

    assert target.read_bytes() == b"---\nx: 1\n---\n\nText\n"
    assert list(tmp_path.joinpath("sub").iterdir()) == [target]
