import pytest

from kursplaner.infrastructure.repositories import subject_source_repository as module
from kursplaner.infrastructure.repositories.subject_source_repository import (
    FileSystemSubjectSourceRepository,
)


def test_write_manifest_propagates_write_errors(tmp_path, monkeypatch):
    def _raise(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(module, "atomic_write_json", _raise)

    repo = FileSystemSubjectSourceRepository()

    with pytest.raises(OSError):
        repo._write_manifest(tmp_path, files={}, dirs={})
