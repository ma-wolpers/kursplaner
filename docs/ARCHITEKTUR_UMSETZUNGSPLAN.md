# kursplaner - Umsetzungsplan (nur offene Punkte)

Stand: 2026-03-27

Kurz: Dieses Dokument enthaelt nur Arbeit, die noch passieren soll. Abgeschlossene Aenderungen und historische Statusnotizen gehoeren nicht hierher.

---

## Zielbild (offen)

- Kein Klebercode zwischen View/Controller/UseCase.
- Kein Brute-Force-Rendering im Interaktionspfad.
- Eindeutiger Ablaufbesitz pro Nutzerintent.

Referenz fuer dauerhafte Leitplanken:
- docs/ARCHITEKTUR_KERN.md (Abschnitt GUI-Infrastruktur-Orientierung und bindende Regeln)

---

## Offene Arbeitspakete (priorisiert)

- **`NewLesson*UseCase`-Umbenennung** (2026-08-09 vermerkt): Der GUI-Dialog heißt seit dieser Session `NewCourseWindow`, die dahinterliegenden Use Cases (`NewLessonFormUseCase`, `NewLessonUseCase`, `new_lesson_form_usecase.py`, `new_lesson_usecase.py`) bewusst noch nicht mit umbenannt — größere, hier nicht angegangene Umbenennung mit vielen Importstellen.
- **`lesson_conversion_controller.py`-Split** (2026-08-09 vermerkt, siehe `ARCHITEKTUR_KERN.md` §28 Ausnahme-Tabelle): Prefill-Hilfsfunktionen (`_unterricht_prefill_values`, `_coerce_string_list`, `_extract_markdown_section_refs`, `_prefill_ausfall_reason_from_content`) in ein eigenes `lesson_conversion_prefill.py` auslagern.
- **`grid_cell_policy_usecase.py`/`lesson_context_controller.py`-Duplikation** (2026-08-09 vermerkt): `GridCellPolicyUseCase.field_value`/`is_editable` sind ein nahezu wortgleicher Klon von `MainWindowLessonContextController.field_value`/`RowDisplayModeUseCase.is_editable` — bereits vor dieser Session bestehend, durch die Rhythmus-Umstellung (`"startzeit"`-Feld musste an beiden Stellen ergänzt werden) erneut sichtbar geworden. Konsolidierung auf eine Quelle empfohlen.

---

## Ticket-Regeln fuer KI-Umsetzung

- 1 Ticket = 1 Modulgrenze oder 1 Ablaufkante.
- Maximal 3 Dateien mit strukturellem Umbau pro Ticket.
- Vor Coding: Ziel, Nicht-Ziel, Abnahmekriterien klar notieren.
- Nach Coding: Fehlercheck + Testnachweis + kurzes Doku-Delta.
- Bei Aenderungen an Shortcut- oder Popup-Semantik: sichtbare Hover-/Hilfetexte im gleichen Zyklus aktualisieren und mit testen.

---

## Arbeits-Runbook (offen)

1. Tests:

```powershell
& .venv\Scripts\python.exe -m pytest -q
```

2. Benchmark-Schnellcheck:

```powershell
& .venv\Scripts\python.exe tools/benchmarks/overview_query_benchmark.py --rows 5 --iterations 3
# optional als Guard (Beispiel):
# & .venv\Scripts\python.exe tools/benchmarks/overview_query_benchmark.py --rows 5 --iterations 3 --max-avg-ms 50
```

3. Index manuell neu aufbauen:
- GUI: Datei -> Lesson-Index neu aufbauen
- CLI: `tools/rebuild_lesson_index.py`

---

## Naechster konkreter Schritt

- Naechstes Paket nur bei neuem Architektur-Bedarf definieren (inkl. Ziel/Nicht-Ziel/Abnahme).
