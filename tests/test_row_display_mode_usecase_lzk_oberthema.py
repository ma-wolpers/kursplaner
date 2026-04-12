from kursplaner.core.usecases.row_display_mode_usecase import RowDisplayModeUseCase


def test_lzk_mode_contains_oberthema_row():
    usecase = RowDisplayModeUseCase()

    row_defs = usecase.row_defs_for_mode(usecase.MODE_LZK)
    keys = [field for field, _ in row_defs]

    assert "Oberthema" in keys


def test_unterricht_mode_places_teilziele_after_stundenziel_and_treats_as_list():
    usecase = RowDisplayModeUseCase()

    row_defs = usecase.row_defs_for_mode(usecase.MODE_UNTERRICHT)
    keys = [field for field, _ in row_defs]

    assert "Teilziele" in keys
    assert keys.index("Teilziele") == keys.index("Stundenziel") + 1
    assert "Teilziele" in usecase.list_like_fields()
