from kursplaner.core.domain.lesson_yaml_policy import canonicalize_lesson_yaml, infer_stundentyp


def test_unterricht_defaults_include_unterrichtsbesuch_field():
    normalized = canonicalize_lesson_yaml({"Stundentyp": "Unterricht", "Stundenthema": "Test", "Dauer": "2"})
    assert "Unterrichtsbesuch" in normalized
    assert normalized["Unterrichtsbesuch"] == ""


def test_unterricht_defaults_include_teilziele_field():
    normalized = canonicalize_lesson_yaml({"Stundentyp": "Unterricht", "Stundenthema": "Test", "Dauer": "2"})
    assert "Teilziele" in normalized
    assert normalized["Teilziele"] == []


def test_unterricht_preserves_unterrichtsbesuch_value():
    normalized = canonicalize_lesson_yaml(
        {
            "Stundentyp": "Unterricht",
            "Stundenthema": "Test",
            "Dauer": "2",
            "Unterrichtsbesuch": "[[UB 26-03-31 Test]]",
        }
    )
    assert normalized["Unterrichtsbesuch"] == "[[UB 26-03-31 Test]]"


def test_unterricht_preserves_teilziele_values():
    normalized = canonicalize_lesson_yaml(
        {
            "Stundentyp": "Unterricht",
            "Stundenthema": "Test",
            "Dauer": "2",
            "Teilziele": [
                "I.1 zentrale Konzepte an neuen Beispielen erläutern.",
                "an einer Aufgabe begründet Lösungsschritte auswählen.",
            ],
        }
    )
    assert normalized["Teilziele"] == [
        "I.1 zentrale Konzepte an neuen Beispielen erläutern.",
        "an einer Aufgabe begründet Lösungsschritte auswählen.",
    ]


def test_non_unterricht_drops_unterrichtsbesuch_field():
    normalized = canonicalize_lesson_yaml(
        {
            "Stundentyp": "LZK",
            "Stundenthema": "LZK 1",
            "Dauer": "2",
            "Unterrichtsbesuch": "[[UB 26-03-31 LZK 1]]",
        }
    )
    assert "Unterrichtsbesuch" not in normalized


def test_lzk_defaults_include_oberthema_field():
    normalized = canonicalize_lesson_yaml({"Stundentyp": "LZK", "Stundenthema": "LZK 1", "Dauer": "2"})
    assert "Oberthema" in normalized
    assert normalized["Oberthema"] == ""


def test_lzk_preserves_oberthema_value():
    normalized = canonicalize_lesson_yaml(
        {
            "Stundentyp": "LZK",
            "Stundenthema": "LZK 1",
            "Dauer": "2",
            "Oberthema": "Informationen und Daten",
        }
    )
    assert normalized["Oberthema"] == "Informationen und Daten"


def test_infer_stundentyp_does_not_use_topic_keyword_heuristic_for_lzk():
    lesson_type = infer_stundentyp(
        {
            "Stundenthema": "Vorbereitung LZK im Team",
            "Dauer": "2",
        }
    )

    assert lesson_type == "Unterricht"
