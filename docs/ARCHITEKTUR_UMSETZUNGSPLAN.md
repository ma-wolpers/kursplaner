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

Aktuell keine offenen Pakete.

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
