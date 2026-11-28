"""Tests für `tools/remove_hospitation_development_fields.py` (synthetische Daten)."""

from pathlib import Path

from tools.remove_hospitation_development_fields import main


def _course(root: Path, name: str = "Mat 7a 26-1") -> Path:
    course = root / name
    (course / "Einheiten").mkdir(parents=True)
    (course / f"{name}.md").write_text("---\nx: y\n---\n", encoding="utf-8")
    return course


def _hospitation(course: Path, stem: str, extra: str = "") -> Path:
    path = course / "Einheiten" / f"{stem}.md"
    path.write_text(
        "---\nStundentyp: Hospitation\nDauer: 2\nStundenthema: Hospitation 1\n"
        f'Beobachtungsschwerpunkte: "Ruhe"\n{extra}---\n\n# Notizen\n\nText bleibt.\n',
        encoding="utf-8",
    )
    return path


def test_dry_run_counts_without_writing(tmp_path, capsys):
    course = _course(tmp_path)
    path = _hospitation(course, "ab12cd", 'Ressourcen:\n  - "alt"\n')
    before = path.read_text(encoding="utf-8")

    assert main(["--dry-run", "--unterricht-dir", str(tmp_path)]) == 0

    assert path.read_text(encoding="utf-8") == before
    assert "1 Datei(en)" in capsys.readouterr().out


def test_removes_old_fields_and_keeps_everything_else(tmp_path):
    course = _course(tmp_path)
    affected = _hospitation(course, "ab12cd", 'Ressourcen:\n  - "alt"\nBaustellen: []\n')
    untouched = _hospitation(course, "ef34gh")
    untouched_before = untouched.read_text(encoding="utf-8")

    assert main(["--unterricht-dir", str(tmp_path)]) == 0

    text = affected.read_text(encoding="utf-8")
    assert "Ressourcen" not in text
    assert "Baustellen" not in text
    assert "Beobachtungsschwerpunkte" in text
    assert "Text bleibt." in text
    assert untouched.read_text(encoding="utf-8") == untouched_before
    assert main(["--dry-run", "--unterricht-dir", str(tmp_path)]) == 0
