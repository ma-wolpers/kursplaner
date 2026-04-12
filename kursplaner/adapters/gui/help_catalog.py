from __future__ import annotations

NEW_LESSON_HELP: dict[str, str] = {
    "period_input": (
        "Hier gibst du entweder ein Halbjahr (z. B. 26-1) oder ein Startdatum (YYYY-MM-DD) an.\n"
        "Bei einem Datum wird das Halbjahr automatisch aus den Kalenderdaten abgeleitet."
    ),
    "vacation_horizon": (
        "Nur bei Startdatum relevant: Lege die Anzahl kommender Ferienstarts fest, bis zur nächsten Halbjahresgrenze (Sommer/Winter)."
    ),
}

LESSON_BUILDER_HELP: dict[str, str] = {
    "title": (
        "Dateiname der Einheit.\nSollte kurz, eindeutig und stabil sein, damit Verlinkungen zuverlässig bleiben."
    ),
    "topic": "Konkretes Thema der Stunde, das später im Plan sichtbar ist.",
    "oberthema": "Größerer inhaltlicher Rahmen, zu dem die Stunde gehört.",
    "kompetenzen": (
        "Kompetenzen aus dem Katalog oder als eigene Einträge.\n"
        "Im Auswahlfenster toggelt Leertaste den aktiven Eintrag (hinzufügen/entfernen), Enter übernimmt und schließt.\n"
        "Esc entspricht Abbrechen und schließt das Fenster sofort."
    ),
    "stundenziel": (
        "Zielkompetenz bzw. erwarteter Lernzuwachs für diese Einheit.\n"
        "Didaktischer Rahmen (implizit): 'Am Ende dieser Einheit können die Lernenden insbesondere ...'.\n"
        "Beginne mit Kompetenzverweis, z. B. 'I.1 ...'.\n"
        "Im Auswahlfenster toggelt Leertaste den aktiven Eintrag (setzen/löschen), Enter übernimmt und schließt.\n"
        "Esc entspricht Abbrechen und schließt das Fenster sofort."
    ),
    "teilziele": (
        "Mehrere Teilziele, die in dieser Einheit auf das Stundenziel hinarbeiten.\n"
        "Didaktischer Rahmen (implizit): 'Am Ende dieser Einheit können die Lernenden auch ...'.\n"
        "Teilziele dürfen frei formuliert werden; ein Kompetenzverweis ist optional."
    ),
    "inhalte": (
        "Inhaltsquellen aus dem Fach-Baukasten.\nTippen filtert die Liste, ausgewählte Einträge erscheinen als Chips."
    ),
    "methodik": (
        "Methodikquellen aus dem Fachdidaktik-Baukasten.\n"
        "Tippen filtert die Liste, ausgewählte Einträge erscheinen als Chips."
    ),
}

MAIN_WINDOW_HELP: dict[str, str] = {
    "course_dir": (
        "Hier wählst du den Unterrichtsordner, aus dem Kurse geladen werden.\n"
        "Ein Wechsel lädt eine andere Kursübersicht."
    ),
    "new": "Legt einen neuen Unterricht an. - Strg+N (immer)",
    "refresh": "Lädt Kursübersicht/Status neu. - Strg+R (immer)",
    "column_visibility": "Blendet Spaltenarten aus oder zeigt sie als dünne Marker an. - Strg+L",
    "export_as": "Exportiert die aktuelle Sequenz als Sequenzplan oder Kompetenzhorizont (PDF/Markdown). - Strg+P",
    "undo": "Macht die letzte Plan-Änderung rückgängig. - Strg+Z (im Plan, nicht im Textfeld)",
    "redo": "Stellt die letzte Rücknahme wieder her. - Strg+Y (im Plan, nicht im Textfeld)",
    "as_unterricht": "Markiert die ausgewählte Spalte als Unterricht. - Strg+U",
    "extend_to_vacation": "Erweitert den Plan bis Ferienbeginn. - Strg+E",
    "as_ausfall": "Markiert die ausgewählte Spalte als Ausfall. - Strg+Q",
    "as_hospitation": "Markiert die ausgewählte Spalte als Hospitation. - Strg+O",
    "as_lzk": "Markiert die ausgewählte Spalte als LZK. - Strg+K",
    "lzk_expected_horizon": "Exportiert den LZK-Kompetenzhorizont automatisch als Markdown und PDF. Ziel: Tabelle ausfuellen ohne Bewertungsverlust durch Overwrite (AFB/Aufg/Pkte bleiben erhalten, entfernte bewertete Ziele werden markiert). - Strg+K (Undo/Redo stellt die PDF nicht vollstaendig wieder her)",
    "copy": "Kopiert Inhalte. - Strg+C (Spaltenauswahl: ganze Einheit, Zellauswahl: ganze Zelle; nicht im Textfeld)",
    "paste": "Fügt Inhalte ein. - Strg+V (Spaltenauswahl: ganze Einheit, Zellauswahl: ersetzt ganze Zelle; im Zellmodus nur aktiv bei nicht-leerer Zwischenablage; nicht im Textfeld)",
    "cut": "Schneidet im Zellauswahlmodus die ganze Zelle aus. - Strg+X (kopiert und leert; nicht im Textfeld)",
    "find_markdown": "Verknüpft eine vorhandene Markdown-Datei. - Strg+G",
    "clear": "Leert die verlinkte Einheit. - Strg+Entf (nur im Spaltenauswahlmodus)",
    "rename": "Benennt die verlinkte Einheitsdatei um. - Strg+J",
    "split": "Teilt eine mehrstündige Einheit auf. - Strg+T",
    "merge": "Führt passende Einheiten zusammen. - Strg+M",
    "resume": "Nimmt Ausfall zurück. - Kontextaktion Strg+B",
    "move_left": "Verschiebt die Spalte nach links. - Strg+Links",
    "move_right": "Verschiebt die Spalte nach rechts. - Strg+Rechts",
    "lesson_tree": (
        "Kursübersicht mit nächstem Thema, Reststunden und nächster LZK.\n"
        "Mit Hoch/Runter wechselst du die Kursauswahl, Pos1/Ende springt zum ersten/letzten Kurs.\n"
        "Öffnen per Klick oder Enter; Esc schließt die Einheitenansicht wieder."
    ),
    "mode_unterricht": "Zeigt typische Unterrichtsfelder im Raster.",
    "mode_lzk": "Zeigt LZK-spezifische Felder im Raster.",
    "mode_ausfall": "Zeigt Ausfall-spezifische Felder im Raster.",
    "mode_hospitation": "Zeigt Hospitationsfelder im Raster.",
    "mode_auto": "Passt die Ansicht automatisch an die ausgewählte Spalte an.",
    "mark_ub": "Markiert die ausgewählte Unterrichtseinheit als Unterrichtsbesuch und legt die UB-Datei an.",
    "ub_achievements": "Öffnet die UB-Ansicht mit Fortschrittsringen und den letzten Entwicklungsimpulsen.",
    "detail_navigation": (
        "Navigation im Detailraster: Links/Rechts wechselt Spalten (Alt+Links/Rechts ohne Skip), Enter startet Zellauswahl/Bearbeitung.\n"
        "In Zellauswahl: Hoch/Runter = nächste editierbare Zelle, Strg+Runter/Strg+Hoch = aktuelle Zeile auf-/zuklappen, Pos1/Ende = oberste/unterste, Entf/Backspace = Zelle leeren, Esc geht stufenweise zurück.\n"
        "Maus: 1. Klick auf editierbare Zelle markiert, 2. Klick startet Bearbeitung; Klick außerhalb beendet Bearbeitung; Klick auf Datum markiert die Spalte."
    ),
}

SHADOW_LESSONS_HELP: dict[str, str] = {
    "list": "Unverlinkte Einheiten im Einheiten-Ordner des aktuellen Kurses.",
    "preview": "Vollständiger Inhalt der ausgewählten Datei inklusive YAML-Kopf.",
    "set_clipboard": "Setzt die Datei als Quelle für Einfügen im Hauptfenster.",
    "copy_path": "Kopiert den vollständigen Dateipfad in die Zwischenablage.",
}
