"""Compatibility shim: re-export repository classes from split modules.

This module preserves the original import path while the implementation
is split into per-repository modules for better maintainability.
"""

from .calendar_repository import FileSystemCalendarRepository
from .command_repository import FileSystemCommandRepository
from .kompetenzkatalog_repository import FileSystemKompetenzkatalogRepository
from .lesson_file_repository import FileSystemLessonFileRepository
from .lesson_repository import FileSystemLessonRepository
from .lesson_setup_repository import FileSystemLessonSetupRepository
from .plan_repository import FileSystemPlanRepository
from .subject_source_repository import FileSystemSubjectSourceRepository
from .ub_repository import FileSystemUbRepository

__all__ = [
    "FileSystemPlanRepository",
    "FileSystemLessonRepository",
    "FileSystemCalendarRepository",
    "FileSystemCommandRepository",
    "FileSystemLessonFileRepository",
    "FileSystemSubjectSourceRepository",
    "FileSystemUbRepository",
    "FileSystemLessonSetupRepository",
    "FileSystemKompetenzkatalogRepository",
]
