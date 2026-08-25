from datetime import date, datetime, time, timedelta

from kursplaner.core.domain.course_rhythm import weekday_token
from kursplaner.core.domain.plan_table import PlanTableData
from kursplaner.core.usecases.plan_overview_query_usecase import PlanOverviewQueryUseCase
from kursplaner.infrastructure.repositories.lesson_index_repository import FileSystemLessonIndexRepository
from kursplaner.infrastructure.repositories.markdown_repositories import FileSystemLessonRepository
from kursplaner.infrastructure.repositories.ub_repository import FileSystemUbRepository


def test_plan_overview_uses_index(tmp_path):
    # Setup a simple Unterricht folder with one lesson
    root = tmp_path / "Unterricht"
    (root / "FachX" / "Einheiten").mkdir(parents=True)
    lesson_path = root / "FachX" / "Einheiten" / "stunde-1.md"
    lesson_path.write_text(
        '---\nStundentyp: Unterricht\nDauer: 2\nKompetenzen:\n  - ""\nStundenthema: Thema1\nStundenziel: ""\nMaterial:\n  - ""\nOberthema: ""\n---\n\n# Inhalt\n',
        encoding="utf-8",
    )

    repo = FileSystemLessonIndexRepository()
    repo.rebuild_index(root)

    lesson_repo = FileSystemLessonRepository()
    usecase = PlanOverviewQueryUseCase(lesson_repo=lesson_repo, lesson_index_repo=repo)

    future = (date.today() + timedelta(days=1)).strftime("%d-%m-%y")
    table = PlanTableData(
        markdown_path=root / "FachX" / "plan.md",
        headers=["datum", "stunden", "inhalt"],
        rows=[[future, "2", "[[Einheiten/stunde-1]]"]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={},
    )

    # summarize_plan should run using the index; result should reflect the indexed topic
    (
        theme,
        remaining,
        next_lzk,
        next_ub,
        next_unit,
        days_until_next_unit,
        has_upcoming_unit,
        has_any_dated_unit,
    ) = usecase.summarize_plan(table)
    assert theme is not None
    assert "Thema1" in theme or theme == ""
    assert next_unit == future
    assert days_until_next_unit == 1
    assert has_upcoming_unit is True
    assert has_any_dated_unit is True
    assert next_ub == ""


def test_plan_overview_exposes_next_ub_display(tmp_path):
    workspace_root = tmp_path / "7thCloud"
    root = workspace_root / "7thVault" / "Unterricht" / "FachX"
    (root / "Einheiten").mkdir(parents=True)

    lesson_path = root / "Einheiten" / "stunde-1.md"
    lesson_path.write_text(
        "---\n"
        "Stundentyp: Unterricht\n"
        "Dauer: 2\n"
        "Kompetenzen:\n"
        '  - ""\n'
        "Stundenthema: Thema1\n"
        'Stundenziel: ""\n'
        "Material:\n"
        '  - ""\n'
        "Oberthema: Ober\n"
        'Unterrichtsbesuch: "[[UB 26-05-18 Funktionen]]"\n'
        "---\n\n"
        "# Inhalt\n",
        encoding="utf-8",
    )

    ub_root = workspace_root / "7thVault" / "🏫 Pädagogik" / "00 Orga" / "02 UBs"
    ub_root.mkdir(parents=True)
    ub_path = ub_root / "UB 26-05-18 Funktionen.md"
    ub_path.write_text(
        "---\n"
        "Bereich:\n"
        '  - "Pädagogik"\n'
        '  - "Mathematik"\n'
        "Langentwurf: true\n"
        "Beobachtungsschwerpunkt: Fokus\n"
        'Einheit: "[[stunde-1]]"\n'
        "---\n\n"
        "# Reflexion\n",
        encoding="utf-8",
    )

    repo = FileSystemLessonIndexRepository()
    repo.rebuild_index(workspace_root / "7thVault" / "Unterricht")
    lesson_repo = FileSystemLessonRepository()
    ub_repo = FileSystemUbRepository()
    usecase = PlanOverviewQueryUseCase(lesson_repo=lesson_repo, lesson_index_repo=repo, ub_repo=ub_repo)

    table = PlanTableData(
        markdown_path=root / "plan.md",
        headers=["datum", "stunden", "inhalt"],
        rows=[["2026-05-18", "2", "[[Einheiten/stunde-1]]"]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={},
    )

    _theme, _remaining, _next_lzk, next_ub, *_rest = usecase.summarize_plan(table, reference_day=date(2026, 5, 1))
    assert next_ub == "18.5. MP+"


def test_plan_overview_next_ub_without_langentwurf_has_no_plus(tmp_path):
    workspace_root = tmp_path / "7thCloud"
    root = workspace_root / "7thVault" / "Unterricht" / "FachX"
    (root / "Einheiten").mkdir(parents=True)

    lesson_path = root / "Einheiten" / "stunde-1.md"
    lesson_path.write_text(
        "---\n"
        "Stundentyp: Unterricht\n"
        "Dauer: 2\n"
        "Kompetenzen:\n"
        '  - ""\n'
        "Stundenthema: Thema1\n"
        'Stundenziel: ""\n'
        "Material:\n"
        '  - ""\n'
        "Oberthema: Ober\n"
        'Unterrichtsbesuch: "[[UB 26-05-18 Funktionen]]"\n'
        "---\n\n"
        "# Inhalt\n",
        encoding="utf-8",
    )

    ub_root = workspace_root / "7thVault" / "🏫 Pädagogik" / "00 Orga" / "02 UBs"
    ub_root.mkdir(parents=True)
    ub_path = ub_root / "UB 26-05-18 Funktionen.md"
    ub_path.write_text(
        "---\n"
        "Bereich:\n"
        '  - "Pädagogik"\n'
        '  - "Mathematik"\n'
        "Langentwurf: false\n"
        "Beobachtungsschwerpunkt: Fokus\n"
        'Einheit: "[[stunde-1]]"\n'
        "---\n\n"
        "# Reflexion\n",
        encoding="utf-8",
    )

    repo = FileSystemLessonIndexRepository()
    repo.rebuild_index(workspace_root / "7thVault" / "Unterricht")
    lesson_repo = FileSystemLessonRepository()
    ub_repo = FileSystemUbRepository()
    usecase = PlanOverviewQueryUseCase(lesson_repo=lesson_repo, lesson_index_repo=repo, ub_repo=ub_repo)

    table = PlanTableData(
        markdown_path=root / "plan.md",
        headers=["datum", "stunden", "inhalt"],
        rows=[["2026-05-18", "2", "[[Einheiten/stunde-1]]"]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={},
    )

    _theme, _remaining, _next_lzk, next_ub, *_rest = usecase.summarize_plan(table, reference_day=date(2026, 5, 1))
    assert next_ub == "18.5. MP"


def test_plan_overview_falls_back_to_row_date_when_ub_stem_has_no_date(tmp_path):
    workspace_root = tmp_path / "7thCloud"
    root = workspace_root / "7thVault" / "Unterricht" / "FachX"
    (root / "Einheiten").mkdir(parents=True)

    lesson_path = root / "Einheiten" / "stunde-1.md"
    lesson_path.write_text(
        "---\n"
        "Stundentyp: Unterricht\n"
        "Dauer: 2\n"
        "Kompetenzen:\n"
        '  - ""\n'
        "Stundenthema: Thema1\n"
        'Stundenziel: ""\n'
        "Material:\n"
        '  - ""\n'
        "Oberthema: Ober\n"
        'Unterrichtsbesuch: "[[UB Sonderbesuch]]"\n'
        "---\n\n"
        "# Inhalt\n",
        encoding="utf-8",
    )

    ub_root = workspace_root / "7thVault" / "🏫 Pädagogik" / "00 Orga" / "02 UBs"
    ub_root.mkdir(parents=True)
    ub_path = ub_root / "UB Sonderbesuch.md"
    ub_path.write_text(
        "---\n"
        "Bereich:\n"
        "Langentwurf: false\n"
        "Beobachtungsschwerpunkt: Fokus\n"
        'Einheit: "[[stunde-1]]"\n'
        "---\n\n"
        "# Reflexion\n",
        encoding="utf-8",
    )

    repo = FileSystemLessonIndexRepository()
    repo.rebuild_index(workspace_root / "7thVault" / "Unterricht")
    lesson_repo = FileSystemLessonRepository()
    ub_repo = FileSystemUbRepository()
    usecase = PlanOverviewQueryUseCase(lesson_repo=lesson_repo, lesson_index_repo=repo, ub_repo=ub_repo)

    table = PlanTableData(
        markdown_path=root / "plan.md",
        headers=["datum", "stunden", "inhalt"],
        rows=[["2026-05-18", "2", "[[Einheiten/stunde-1]]"]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={},
    )

    _theme, _remaining, _next_lzk, next_ub, *_rest = usecase.summarize_plan(table, reference_day=date(2026, 5, 1))
    assert next_ub == "18.5."


def test_plan_overview_next_ub_uses_start_time_of_ub_date_not_row_date(tmp_path):
    """next_ub's Startzeit-Gate nutzt die Startzeit von ub_date (kann von row_date abweichen)."""
    workspace_root = tmp_path / "7thCloud"
    root = workspace_root / "7thVault" / "Unterricht" / "FachX"
    (root / "Einheiten").mkdir(parents=True)

    # row_date liegt in der Zukunft (besteht den Datumsfilter unabhaengig von
    # der Uhrzeit); ub_date ist "heute" -- ihr Rhythmus-Eintrag muss fuer das
    # Startzeit-Gate herangezogen werden, nicht der von row_date.
    ub_date = date(2026, 5, 18)
    row_date = date(2026, 5, 19)
    # Kanonisches Stamm-Format "ub yy-mm-dd" (klein geschrieben, ohne Titel) --
    # das alte "UB yy-mm-dd Titel"-Format gilt als unparsbar und faellt immer
    # auf row_date zurueck, was hier gerade NICHT getestet werden soll.
    ub_stem = f"ub {ub_date.strftime('%y-%m-%d')}"

    lesson_path = root / "Einheiten" / "stunde-1.md"
    lesson_path.write_text(
        "---\n"
        "Stundentyp: Unterricht\n"
        "Dauer: 2\n"
        "Kompetenzen:\n"
        '  - ""\n'
        "Stundenthema: Thema1\n"
        'Stundenziel: ""\n'
        "Material:\n"
        '  - ""\n'
        "Oberthema: Ober\n"
        f'Unterrichtsbesuch: "[[{ub_stem}]]"\n'
        "---\n\n"
        "# Inhalt\n",
        encoding="utf-8",
    )

    ub_root = workspace_root / "7thVault" / "🏫 Pädagogik" / "00 Orga" / "02 UBs"
    ub_root.mkdir(parents=True)
    ub_path = ub_root / f"{ub_stem}.md"
    ub_path.write_text(
        "---\n"
        "Bereich:\n"
        "Langentwurf: false\n"
        "Beobachtungsschwerpunkt: Fokus\n"
        'Einheit: "[[stunde-1]]"\n'
        "---\n\n"
        "# Reflexion\n",
        encoding="utf-8",
    )

    repo = FileSystemLessonIndexRepository()
    repo.rebuild_index(workspace_root / "7thVault" / "Unterricht")
    lesson_repo = FileSystemLessonRepository()
    ub_repo = FileSystemUbRepository()
    usecase = PlanOverviewQueryUseCase(lesson_repo=lesson_repo, lesson_index_repo=repo, ub_repo=ub_repo)

    # ub_date startet spaet (16:00), row_dates Wochentag frueh (08:00), ist
    # aber ohnehin irrelevant, da row_date in der Zukunft liegt. Waere
    # faelschlich row_dates Rhythmus-Eintrag fuer den UB-Startzeit-Check
    # herangezogen worden, gaelte 09:00 bereits als "nach Startzeit"
    # (>= 08:00) -- korrekt (ub_date-Rhythmus) ist 09:00 noch vor 16:00.
    table = PlanTableData(
        markdown_path=root / "plan.md",
        headers=["datum", "stunden", "inhalt"],
        rows=[[row_date.strftime("%d-%m-%y"), "2", "[[Einheiten/stunde-1]]"]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={
            "Rhythmus": [
                f"{weekday_token(row_date.weekday())} 08:00 2",
                f"{weekday_token(ub_date.weekday())} 16:00 2",
            ]
        },
    )

    _theme, _remaining, _next_lzk, next_ub, *_rest = usecase.summarize_plan(
        table, now=datetime.combine(ub_date, time(hour=9, minute=0))
    )

    assert next_ub == "18.5."


def test_plan_overview_next_lzk_uses_stundentyp_not_topic_keyword(tmp_path):
    root = tmp_path / "Unterricht"
    (root / "FachX" / "Einheiten").mkdir(parents=True)

    lesson_regular = root / "FachX" / "Einheiten" / "stunde-regular.md"
    lesson_regular.write_text(
        "---\n"
        "Stundentyp: Unterricht\n"
        "Dauer: 2\n"
        "Stundenthema: Vorbereitung LZK in Partnerarbeit\n"
        "---\n",
        encoding="utf-8",
    )

    lesson_lzk = root / "FachX" / "Einheiten" / "stunde-lzk.md"
    lesson_lzk.write_text(
        "---\n"
        "Stundentyp: LZK\n"
        "Dauer: 2\n"
        "Stundenthema: Leistungskontrolle Kapitel 1\n"
        "---\n",
        encoding="utf-8",
    )

    repo = FileSystemLessonIndexRepository()
    repo.rebuild_index(root)
    lesson_repo = FileSystemLessonRepository()
    usecase = PlanOverviewQueryUseCase(lesson_repo=lesson_repo, lesson_index_repo=repo)

    future_1 = (date.today() + timedelta(days=1)).strftime("%d-%m-%y")
    future_2 = (date.today() + timedelta(days=2)).strftime("%d-%m-%y")
    table = PlanTableData(
        markdown_path=root / "FachX" / "plan.md",
        headers=["datum", "stunden", "inhalt"],
        rows=[
            [future_1, "2", "[[Einheiten/stunde-regular]]"],
            [future_2, "2", "[[Einheiten/stunde-lzk]]"],
        ],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={},
    )

    _theme, _remaining, next_lzk, _next_ub, *_rest = usecase.summarize_plan(table)

    assert next_lzk == future_2


def test_plan_overview_counts_today_as_past_after_start_time(tmp_path):
    """Standardmodus (Startzeit): nach der tatsächlichen Startzeit gilt heute als vergangen."""
    root = tmp_path / "Unterricht"
    (root / "FachX").mkdir(parents=True)

    lesson_repo = FileSystemLessonRepository()
    usecase = PlanOverviewQueryUseCase(lesson_repo=lesson_repo)

    today_text = date.today().strftime("%d-%m-%y")
    table = PlanTableData(
        markdown_path=root / "FachX" / "plan.md",
        headers=["datum", "stunden", "inhalt"],
        rows=[[today_text, "2", ""]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={"Rhythmus": [f"{weekday_token(date.today().weekday())} 08:00 2"]},
    )

    (
        _theme,
        remaining,
        _next_lzk,
        _next_ub,
        next_unit,
        days_until_next_unit,
        has_upcoming_unit,
        has_any_dated_unit,
    ) = usecase.summarize_plan(table, now=datetime.combine(date.today(), time(hour=9, minute=0)))

    assert remaining == 0
    assert next_unit == "—"
    assert days_until_next_unit is None
    assert has_upcoming_unit is False
    assert has_any_dated_unit is True


def test_plan_overview_counts_today_as_upcoming_before_start_time(tmp_path):
    """Standardmodus (Startzeit): vor der tatsächlichen Startzeit gilt heute als anstehend."""
    root = tmp_path / "Unterricht"
    (root / "FachX").mkdir(parents=True)

    lesson_repo = FileSystemLessonRepository()
    usecase = PlanOverviewQueryUseCase(lesson_repo=lesson_repo)

    today_text = date.today().strftime("%d-%m-%y")
    table = PlanTableData(
        markdown_path=root / "FachX" / "plan.md",
        headers=["datum", "stunden", "inhalt"],
        rows=[[today_text, "2", ""]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={"Rhythmus": [f"{weekday_token(date.today().weekday())} 08:00 2"]},
    )

    (
        _theme,
        remaining,
        _next_lzk,
        _next_ub,
        next_unit,
        days_until_next_unit,
        has_upcoming_unit,
        has_any_dated_unit,
    ) = usecase.summarize_plan(table, now=datetime.combine(date.today(), time(hour=7, minute=0)))

    assert remaining == 2
    assert next_unit == today_text
    assert days_until_next_unit == 0
    assert has_upcoming_unit is True
    assert has_any_dated_unit is True


def test_plan_overview_treats_missing_rhythm_as_conservatively_upcoming(tmp_path):
    """Ohne Rhythmus-Eintrag (keine ermittelbare Startzeit) gilt heute bewusst weiterhin als anstehend."""
    root = tmp_path / "Unterricht"
    (root / "FachX").mkdir(parents=True)

    lesson_repo = FileSystemLessonRepository()
    usecase = PlanOverviewQueryUseCase(lesson_repo=lesson_repo)

    today_text = date.today().strftime("%d-%m-%y")
    table = PlanTableData(
        markdown_path=root / "FachX" / "plan.md",
        headers=["datum", "stunden", "inhalt"],
        rows=[[today_text, "2", ""]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={},
    )

    (
        _theme,
        _remaining,
        _next_lzk,
        _next_ub,
        next_unit,
        days_until_next_unit,
        has_upcoming_unit,
        has_any_dated_unit,
    ) = usecase.summarize_plan(table, now=datetime.combine(date.today(), time(hour=16, minute=0)))

    # Ohne Rhythmus-Eintrag liefert hours_for_date 0 Reststunden fuer den Tag,
    # der Tag selbst zaehlt aber (bewusster Fallback) weiterhin als anstehend.
    assert next_unit == today_text
    assert days_until_next_unit == 0
    assert has_upcoming_unit is True
    assert has_any_dated_unit is True


def test_plan_overview_global_cutoff_mode_overrides_start_time(tmp_path):
    """Opt-in Modus (globaler Cutoff): ersetzt die Startzeit-Pruefung vollstaendig."""
    root = tmp_path / "Unterricht"
    (root / "FachX").mkdir(parents=True)

    lesson_repo = FileSystemLessonRepository()
    usecase = PlanOverviewQueryUseCase(
        lesson_repo=lesson_repo,
        next_unit_global_cutoff_enabled_provider=lambda: True,
        next_unit_global_cutoff_time_provider=lambda: time(hour=15, minute=0),
    )

    today_text = date.today().strftime("%d-%m-%y")
    table = PlanTableData(
        markdown_path=root / "FachX" / "plan.md",
        headers=["datum", "stunden", "inhalt"],
        rows=[[today_text, "2", ""]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        # Rhythmus-Startzeit 08:00 ist im Cutoff-Modus irrelevant.
        metadata={"Rhythmus": [f"{weekday_token(date.today().weekday())} 08:00 2"]},
    )

    _theme, remaining_before, *_rest_before, has_upcoming_before, _dated_before = usecase.summarize_plan(
        table, now=datetime.combine(date.today(), time(hour=14, minute=0))
    )
    _theme, remaining_after, *_rest_after, has_upcoming_after, _dated_after = usecase.summarize_plan(
        table, now=datetime.combine(date.today(), time(hour=16, minute=0))
    )

    assert remaining_before == 2
    assert has_upcoming_before is True
    assert remaining_after == 0
    assert has_upcoming_after is False


def test_plan_overview_reference_day_bypass_stays_date_only_ignoring_start_time(tmp_path):
    """`reference_day` ist ein reiner Datums-Determinismuspfad -- bleibt von der Startzeit-Policy unberuehrt."""
    root = tmp_path / "Unterricht"
    (root / "FachX").mkdir(parents=True)

    lesson_repo = FileSystemLessonRepository()
    usecase = PlanOverviewQueryUseCase(lesson_repo=lesson_repo)

    row_date = date(2026, 5, 18)
    table = PlanTableData(
        markdown_path=root / "FachX" / "plan.md",
        headers=["datum", "stunden", "inhalt"],
        rows=[[row_date.strftime("%d-%m-%y"), "2", ""]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={"Rhythmus": [f"{weekday_token(row_date.weekday())} 08:00 2"]},
    )

    # 23:59 Uhr liegt weit nach der 08:00-Startzeit -- per Startzeit-Policy
    # waere die Zeile "nicht mehr anstehend"; der reference_day-Bypass ignoriert
    # das komplett und vergleicht nur Datum >= reference_day.
    _theme, remaining, *_rest, has_upcoming_unit, _dated = usecase.summarize_plan(
        table,
        reference_day=row_date,
        now=datetime.combine(row_date, time(hour=23, minute=59)),
    )

    assert remaining == 2
    assert has_upcoming_unit is True


def test_plan_overview_uses_now_provider_when_now_not_passed(tmp_path):
    """Ohne explizites `now` wird der injizierte `now_provider` genutzt, kein direkter `datetime.now()`-Aufruf."""
    root = tmp_path / "Unterricht"
    (root / "FachX").mkdir(parents=True)

    lesson_repo = FileSystemLessonRepository()
    fixed_now = datetime(2026, 5, 18, 7, 0)
    usecase = PlanOverviewQueryUseCase(lesson_repo=lesson_repo, now_provider=lambda: fixed_now)

    row_date = fixed_now.date()
    table = PlanTableData(
        markdown_path=root / "FachX" / "plan.md",
        headers=["datum", "stunden", "inhalt"],
        rows=[[row_date.strftime("%d-%m-%y"), "2", ""]],
        start_line=0,
        end_line=0,
        source_lines=[],
        had_trailing_newline=False,
        metadata={"Rhythmus": [f"{weekday_token(row_date.weekday())} 08:00 2"]},
    )

    _theme, remaining, *_rest, has_upcoming_unit, _dated = usecase.summarize_plan(table)

    assert remaining == 2
    assert has_upcoming_unit is True
