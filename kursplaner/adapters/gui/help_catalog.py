from __future__ import annotations

NEW_COURSE_HELP: dict[str, str] = {
    "period_input": (
        "Hier gibst du entweder ein Halbjahr (z. B. 26-1) oder ein Startdatum (YYYY-MM-DD) an.\n"
        "Bei einem Datum wird das Halbjahr automatisch aus den Kalenderdaten abgeleitet."
    ),
    "vacation_horizon": (
        "Nur bei Startdatum relevant: Lege die Anzahl kommender Ferienstarts fest, bis zur nächsten Halbjahresgrenze (Sommer/Winter)."
    ),
}

LESSON_BUILDER_HELP: dict[str, str] = {
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
        "Esc entspricht Abbrechen und schließt das Fenster sofort.\n"
        "AFB-Hinweis: Teilziele stecken AFB I/II ab, das Stundenziel sollte darüber liegen (AFB III: Transfer/Vertiefung)."
    ),
    "teilziele": (
        "Mehrere Teilziele, die in dieser Einheit auf das Stundenziel hinarbeiten.\n"
        "Didaktischer Rahmen (implizit): 'Am Ende dieser Einheit können die Lernenden auch ...'.\n"
        "Teilziele dürfen frei formuliert werden; ein Kompetenzverweis ist optional.\n"
        "AFB-Hinweis: Teilziele stecken AFB I/II ab, das Stundenziel sollte darüber liegen (AFB III: Transfer/Vertiefung)."
    ),
    "sonderziele": (
        "Zusätzliche, freiwillige Ziele über das Stundenziel hinaus – für schnellere/interessierte Lernende.\n"
        "Anders als Teilziele kein verpflichtender Zwischenschritt zum Stundenziel.\n"
        "Erscheinen im Erwartungshorizont-Export kursiv, getrennt von Stundenziel und Teilzielen."
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
    "course_overview_new": "Legt einen neuen Kurs an. Das Kürzel gilt auch in der Kursliste.",
    "toggle_former_courses": "Blendet ehemalige Kurse ein/aus.",
    "school_wide_cancellations": (
        "Öffnet die Verwaltung schulweiter Ausfälle (z. B. Wandertag): betroffene Einheiten "
        "werden automatisch verschoben und als Ausfall markiert."
    ),
    "new": "Legt einen neuen Kurs an. Das Kürzel gilt auch in der Kursliste.",
    "refresh": "Lädt Kursübersicht und geöffneten Kursplan neu; Auswahl und Position bleiben. Das Kürzel gilt auch in der Kursliste.",
    "column_visibility": "Blendet Spaltenarten aus oder zeigt sie als dünne Marker an.",
    "export_as": "Exportiert die aktuelle Sequenz als Sequenzplan oder einen Kompetenzhorizont (PDF/Markdown); beim Kompetenzhorizont werden vorher die Oberthemen bis einschliesslich der gewaehlten Stunde abgefragt, beim PDF zusaetzlich eine leere Aufgaben-Spalte und die Schriftgroesse.",
    "undo": "Macht die letzte Plan-Änderung rückgängig. Das Kürzel gilt im Plan, nicht im Textfeld.",
    "redo": "Stellt die letzte Rücknahme wieder her. Das Kürzel gilt im Plan, nicht im Textfeld.",
    "as_unterricht": "Markiert die ausgewählte Spalte als Unterricht.",
    "extend_to_vacation": "Erweitert den Plan bis Ferienbeginn.",
    "as_ausfall": "Markiert die ausgewählte Spalte als Ausfall.",
    "as_hospitation": "Markiert die ausgewählte Spalte als Hospitation.",
    "as_lzk": "Markiert die ausgewählte Spalte als LZK.",
    "lzk_expected_horizon": "Exportiert den LZK-Kompetenzhorizont als Markdown und PDF: fragt die Oberthemen (nur Stunden vor der LZK), das PDF-Layout (leere Aufgaben-Spalte, Schriftgroesse) und den Speicherort ab. Bei gleicher Themenwahl wird der bisherige Kompetenzhorizont vorgeschlagen und aktualisiert (AFB/Aufg/Pkte bleiben erhalten, entfernte bewertete Ziele werden markiert). Undo/Redo stellt die PDF nicht vollstaendig wieder her.",
    "copy": "Kopiert Inhalte: bei Spaltenauswahl die ganze Einheit, bei Zellauswahl die ganze Zelle (nicht im Textfeld).",
    "paste": "Fügt Inhalte ein: bei Spaltenauswahl die ganze Einheit, bei Zellauswahl ersetzt es die ganze Zelle (im Zellmodus nur bei nicht-leerer Zwischenablage; nicht im Textfeld).",
    "find_markdown": "Verknüpft eine vorhandene Markdown-Datei.",
    "clear": "Leert die verlinkte Einheit (nur im Spaltenauswahlmodus).",
    "rename": "Benennt die verlinkte Einheitsdatei um.",
    "resume_ausfall": "Nimmt Ausfall zurück und gibt die Einheit wieder frei.",
    "move_left": "Verschiebt die Spalte nach links.",
    "move_right": "Verschiebt die Spalte nach rechts.",
    "lesson_tree": (
        "Kursübersicht mit nächstem Thema, nächster Einheit, Reststunden und nächster LZK.\n"
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
        "Nur im Spaltenauswahlmodus: Zifferntasten 0-9 wählen relativ zur markierten nächsten Einheit (0 = diese, 1 = die danach folgende stattfindende, 2 = die übernächste, …; Ausfalltage übersprungen, kein Wrap-around).\n"
        "Maus: 1. Klick auf editierbare Zelle markiert, 2. Klick startet Bearbeitung; Klick außerhalb beendet Bearbeitung; Klick auf Datum markiert die Spalte.\n"
        "Listenzellen (z. B. Kompetenzen, Material, mehrere Oberthemen): Einträge stehen untereinander, getrennt durch eine Zeile '--'. "
        "Beim Bearbeiten trennen eine Zeile aus mindestens zwei Strichen oder ein ';'; '|' und Leerzeilen trennen nicht. "
        "Ein Semikolon im Eintrag selbst steht als '\\;' da (so auch eintippen)."
    ),
}

SHADOW_LESSONS_HELP: dict[str, str] = {
    "list": "Unverlinkte Einheiten im Einheiten-Ordner des aktuellen Kurses.",
    "preview": "Vollständiger Inhalt der ausgewählten Datei inklusive YAML-Kopf.",
    "set_clipboard": "Setzt die Datei als Quelle für Einfügen im Hauptfenster.",
    "copy_path": "Kopiert den vollständigen Dateipfad in die Zwischenablage.",
}

SCHOOL_WIDE_CANCELLATION_HELP: dict[str, str] = {
    "entry_list": "Bestehende schulweite Ausfälle. Auswahl lädt den Eintrag rechts zum Bearbeiten.",
    "reason": "Grund des Ausfalls (z. B. Wandertag), wird als Ausfall-Markierung in die betroffenen Kurspläne geschrieben.",
    "date_from": "Erster Tag des Ausfalls (DD.MM.YYYY).",
    "date_to": "Letzter Tag des Ausfalls (DD.MM.YYYY).",
    "grade_groups": "Betroffene Jahrgangsstufen. Gruppen aufklappen, um einzelne Stufen an-/abzuwählen.",
    "preview": (
        "Kurse/Einheiten, die aktuell betroffen wären. Aktualisiert sich live bei jeder Datums-/Stufenänderung.\n"
        "Bereits durch einen anderen Ausfall beanspruchte Tage sind markiert."
    ),
    "diagnostics": "Abweichungen zwischen gespeicherten Einträgen und dem tatsächlichen Kursplan-Zustand (rein informativ).",
}

SEQUENCE_LADDER_HELP: dict[str, str] = {
    "import": (
        "Öffnet das Kompetenznetz: Kompetenzen markieren (Strg+Klick/Leertaste oder „Alle gefilterten "
        "markieren“) und übernehmen. Sie landen je Spalte in der ersten offenen Sprosse über der höchsten belegten."
    ),
    "keys": (
        "Jede Sprosse mit Unterrichtstermin zeigt ihre Einheit: der oberste linke Baustein ist das Stundenziel "
        "(hervorgehoben), darunter die Teilziele, rechts die Kompetenzen, Ideen unter „## Ideen“ – Änderungen "
        "landen direkt in der Einheit. LZK, Hospitation und Ausfall sind gesperrt; „??“-Sprossen sind die Ablage "
        "der Sequenzdatei. „→ Einheit“ an einer gefüllten „??“-Sprosse ordnet sie einer Plan-Zeile zu (leere "
        "Zeile: neue Unterrichtsdatei; vorhandene Ziele/Kompetenzen nach Rückfrage ersetzt, Ideen angehängt). "
        "Pfeile: wählen · Strg+↑/↓: Baustein höher/tiefer (über Sprossen hinweg) · "
        "Strg+C/Strg+V: kopieren/darüber einfügen mit neuem Namen · Entf: löschen · F2 oder Doppelklick: "
        "umbenennen (nur eigene) · Enter: in leerer Zelle neuer Baustein, im Ideenfeld bearbeiten · "
        "Strg+Z/Strg+Y: rückgängig/wiederholen."
    ),
}

KOMPETENZGRAPH_HELP: dict[str, str] = {
    "mark_visible": (
        "Markiert alle aktuell gefilterten Kompetenzen (ohne gedimmte Kontextknoten). Einzeln markieren: "
        "Strg+Klick auf einen Knoten oder Leertaste auf dem gewählten Knoten. Inhaltsbezogene "
        "Hauptkompetenzen (doppelter Rahmen) werden über ihre Einzelkompetenzen erworben und nicht markiert."
    ),
    "import_marked": (
        "Übernimmt die markierten Kompetenzen als Bausteine in eine Sequenzleiter: Inhaltsbereiche links, "
        "Prozessbereiche rechts, jeweils in die Sprosse über der höchsten belegten."
    ),
    "subjects": "Fach-Mehrfachauswahl: mehrere angehakte Fächer werden ODER-verknüpft angezeigt.",
    "kontexttiefe": (
        "Matchingtiefe: 0 zeigt nur echte Filtertreffer. Ab 1 werden zusätzlich Graph-Nachbarn "
        "bis zur gewählten Anzahl Schritte eingeblendet (gedimmt dargestellt) -- auch aus anderen Fächern."
    ),
    "kc_verweis": "Klick kopiert das wörtliche Kerncurriculum-Zitat in die Zwischenablage (z. B. für das Stundenziel).",
    "abhaengigkeiten_ansicht": (
        "Durchgezogene Kanten zeigen Teilkompetenzen (fachliche Bestandteile), gestrichelte Kanten "
        "zeigen echte Voraussetzungen (vorausgesetztes Wissen/Können) -- beide beantworten "
        "'was braucht diese Kompetenz', sind aber nicht dasselbe."
    ),
}
