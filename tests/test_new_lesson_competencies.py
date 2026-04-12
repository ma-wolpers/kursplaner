from pathlib import Path

from kursplaner.core.domain.kompetenzkatalog import KompetenzAbschnitt, Kompetenzkatalog, KompetenzkatalogManifestEntry
from kursplaner.core.usecases.new_lesson_form_usecase import NewLessonFormData, NewLessonFormUseCase


class _CalendarRepoStub:
    def infer_term_from_date(self, start_date, calendar_dir):
        return "26-1"


class _KompetenzRepoStub:
    def __init__(self):
        self._entries = (
            KompetenzkatalogManifestEntry(
                profile_id="inf-sek1",
                profile_label="Informatik Sek I (5-9)",
                subject_code="INF",
                grade_min=5,
                grade_max=10,
                file_path=Path("inf-sek1.json"),
            ),
            KompetenzkatalogManifestEntry(
                profile_id="inf-sek2",
                profile_label="Informatik Sek II (11-13)",
                subject_code="INF",
                grade_min=11,
                grade_max=13,
                file_path=Path("inf-sek2.json"),
            ),
        )
        self._catalogs = {
            "inf-sek1.json": Kompetenzkatalog(
                profile_id="inf-sek1",
                profile_label="Informatik Sek I (5-10)",
                subject_code="INF",
                grade_min=5,
                grade_max=10,
                process_sections=(KompetenzAbschnitt(title="S1", competencies=("P1", "P2")),),
                content_sections=(KompetenzAbschnitt(title="C1", competencies=("I1", "I2")),),
            ),
            "inf-sek2.json": Kompetenzkatalog(
                profile_id="inf-sek2",
                profile_label="Informatik Sek II (11-13)",
                subject_code="INF",
                grade_min=11,
                grade_max=13,
                process_sections=(KompetenzAbschnitt(title="S2", competencies=("PK1", "PK2")),),
                content_sections=(KompetenzAbschnitt(title="C2", competencies=("IK1", "IK2")),),
            ),
        }

    def list_manifest_entries(self):
        return self._entries

    def default_manifest_path(self):
        return Path("catalog_manifest.json")

    def load_manifest_entries_from(self, manifest_path):
        return self._entries

    def load_catalog_file(self, path, profile_id):
        return self._catalogs[path.name]


def test_informatik_catalog_options_for_grade_8_include_only_sek1():
    usecase = NewLessonFormUseCase(
        calendar_repo=_CalendarRepoStub(),
        kompetenz_repo=_KompetenzRepoStub(),
    )

    options = usecase.get_informatik_competency_options(8)

    assert "inf-sek1" in options.profile_ids
    assert "inf-sek2" not in options.profile_ids


def test_build_start_request_persists_selected_competencies_for_informatik(tmp_path):
    base_dir = tmp_path / "unterricht"
    calendar_dir = tmp_path / "kalender"
    base_dir.mkdir(parents=True)
    calendar_dir.mkdir(parents=True)

    usecase = NewLessonFormUseCase(
        calendar_repo=_CalendarRepoStub(),
        kompetenz_repo=_KompetenzRepoStub(),
    )
    options = usecase.get_informatik_competency_options(8)
    profile_id = "inf-sek1"
    process_selected = options.process_competencies_by_profile[profile_id][:2]
    content_selected = options.content_competencies_by_profile[profile_id][0]

    form = NewLessonFormData(
        subject_raw="Informatik",
        group_raw="gruen-6",
        grade_raw="8",
        period_raw="26-1",
        base_dir_raw=str(base_dir),
        calendar_dir_raw=str(calendar_dir),
        day_hours_raw={1: "2"},
        kc_profile_id_raw=profile_id,
        process_competencies_raw=process_selected,
        content_competency_raw=content_selected,
    )

    request = usecase.build_start_request(form)

    assert request.kc_profile_label == options.profile_labels[profile_id]
    assert request.process_competencies == process_selected
    assert request.content_competency == content_selected
