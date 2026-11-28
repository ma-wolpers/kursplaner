from kursplaner.core.domain.lesson_yaml_policy import allowed_keys_for_type, canonicalize_lesson_yaml


def test_hospitation_defaults_include_oberthema_field():
    normalized = canonicalize_lesson_yaml({"Stundentyp": "Hospitation", "Stundenthema": "Hospitation 1", "Dauer": "2"})
    assert "Oberthema" in normalized
    assert normalized["Oberthema"] == ""


def test_hospitation_preserves_oberthema_value():
    normalized = canonicalize_lesson_yaml(
        {
            "Stundentyp": "Hospitation",
            "Stundenthema": "Hospitation 1",
            "Dauer": "2",
            "Oberthema": "Optik",
        }
    )
    assert normalized["Oberthema"] == "Optik"


def test_hospitation_allowed_keys_include_oberthema():
    assert "Oberthema" in allowed_keys_for_type("Hospitation")


def test_hospitation_has_no_development_fields_and_drops_old_ones():
    """Entwicklungsfelder gehören allein zur UB-Datei, nie in eine Stunden-YAML."""
    normalized = canonicalize_lesson_yaml(
        {
            "Stundentyp": "Hospitation",
            "Stundenthema": "Hospitation 1",
            "Dauer": "2",
            "Beobachtungsschwerpunkte": "Classroom-Management",
            "Ressourcen": ["alt"],
            "Baustellen": ["alt"],
        }
    )

    assert "Ressourcen" not in normalized
    assert "Baustellen" not in normalized
    assert normalized["Beobachtungsschwerpunkte"] == "Classroom-Management"
    assert not {"Ressourcen", "Baustellen"} & set(allowed_keys_for_type("Hospitation"))
