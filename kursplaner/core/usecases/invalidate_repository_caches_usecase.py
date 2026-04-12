from __future__ import annotations

from pathlib import Path
from typing import Iterable

from kursplaner.core.ports.repositories import PlanRepository, SubjectSourceRepository


class InvalidateRepositoryCachesUseCase:
    """Invalidiert Repository-Caches explizit für gegebene Basisverzeichnisse."""

    def __init__(self, plan_repo: PlanRepository, subject_source_repo: SubjectSourceRepository):
        """Initialisiert Use Case mit den zu invalidierenden Repository-Ports."""
        self.plan_repo = plan_repo
        self.subject_source_repo = subject_source_repo

    @staticmethod
    def _resolve_base_dirs(base_dirs: Iterable[str | Path]) -> list[Path]:
        """Normalisiert übergebene Basisverzeichnisse zu aufgelösten Pfaden."""
        resolved_dirs: list[Path] = []
        for base_dir in base_dirs:
            if isinstance(base_dir, Path):
                candidate: Path | None = base_dir
            else:
                text = str(base_dir).strip()
                candidate = Path(text) if text else None
            if candidate is None:
                continue
            resolved_dirs.append(candidate.expanduser().resolve())
        return resolved_dirs

    def execute(self, *base_dirs: str | Path) -> None:
        """Invalidiert Caches gezielt je übergebenem Basisverzeichnis."""
        if not base_dirs:
            self.plan_repo.invalidate_cache()
            self.subject_source_repo.invalidate_cache()
            return

        for resolved in self._resolve_base_dirs(base_dirs):
            self.plan_repo.invalidate_cache(resolved)
            self.subject_source_repo.invalidate_cache(unterricht_dir=resolved)
