# Copilot Instructions (kursplaner)

Arbeite in einfacher, klarer Struktur.

Pflichtregeln:

1. `kursplaner/adapters/gui/main_window.py`
- bleibt Orchestrator.
- keine neue fachliche Entscheidungslogik.

2. `kursplaner/adapters/gui/ui_intent_controller.py`
- enthaelt den Intent-Dispatch der GUI.
- neue UI-Interaktionen zuerst hier anbinden.

3. `kursplaner/infrastructure/repositories/lesson_index_repository.py`
- enthaelt zentrale Wartungs-Logs fuer Rebuild/Invalidate.
- keine verteilten Neben-Logs derselben Wartungsaktion in GUI-Adaptern.

4. Architektur-Doku pflegen
- Bei Architektur-Schnitten `docs/ARCHITEKTUR_KERN.md` aktualisieren.
- `docs/ARCHITEKTUR_UMSETZUNGSPLAN.md` nur mit offener Arbeit fuehren.

5. Guardrails sind bindend
- `tools/ci/check_ai_guardrails.py` muss lokal und in CI bestehen.