"""Synthetische `TopicSequencePlanView`s für Tests – eine Quelle statt Handbau in jeder Testdatei.

Läufe mit derselben Sequenzdatei werden wie im Sync zu **einer** `TopicSequence`
und damit zu einer View zusammengefasst.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from kursplaner.core.domain.topic_sequence_runs import TopicSequence, TopicSequenceRun
from kursplaner.core.usecases.sync_topic_sequence_plans_usecase import TopicSequencePlanView


def make_plan_views(
    entries: Iterable[tuple[TopicSequenceRun, Path]],
    *,
    sequenzziel: str = "",
    leitkompetenzen: tuple[str, ...] = (),
    shared_rows: dict[Path, tuple[int, ...]] | None = None,
) -> list[TopicSequencePlanView]:
    """Je Sequenzdatei eine View aus ihren Läufen (Reihenfolge des ersten Auftretens).

    *shared_rows* je Datei = geteilte Mehrthemen-LZKs.
    """
    runs_by_path: dict[Path, list[TopicSequenceRun]] = {}
    for run, path in entries:
        runs_by_path.setdefault(path, []).append(run)
    shared = shared_rows or {}
    return [
        TopicSequencePlanView(
            TopicSequence(runs[0].oberthema, tuple(runs), shared.get(path, ())), path, sequenzziel, leitkompetenzen
        )
        for path, runs in runs_by_path.items()
    ]


def make_plan_view(
    run: TopicSequenceRun,
    path: Path = Path("sequenz.md"),
    *,
    sequenzziel: str = "",
    leitkompetenzen: tuple[str, ...] = (),
) -> TopicSequencePlanView:
    """Eine View, deren Sequenz nur aus *run* besteht."""
    return make_plan_views([(run, path)], sequenzziel=sequenzziel, leitkompetenzen=leitkompetenzen)[0]
