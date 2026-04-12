# Agent Guardrails (kursplaner)

Dieses Repository hat verbindliche Leitplanken fuer KI-Programmierer.

Ziel in einfachen Worten:
- Architektur stabil halten.
- Keine stillen Abkuerzungen im GUI/Infrastructure-Schnitt.
- Nur offene Arbeit im Umsetzungsplan dokumentieren.

Verbindliche Regeln:

1. GUI-Intents
- `main_window.py` bleibt Orchestrator.
- Intent-Dispatch bleibt in `ui_intent_controller.py`.

2. Index-Wartung
- Rebuild/Invalidate des Lesson-Index bleiben zentral im Lesson-Index-Repository.
- Diese Wartungsschritte muessen zentrale Logs schreiben.

3. Doku-Pflicht
- Bei Architektur-Schnitten muss `docs/ARCHITEKTUR_KERN.md` angepasst werden.
- `docs/ARCHITEKTUR_UMSETZUNGSPLAN.md` enthaelt nur offene Arbeit.

4. Automatische Gates
- Lokaler Hook und CI pruefen die Guardrails ueber `tools/ci/check_ai_guardrails.py`.
- Ein Verstoß blockiert Commit/PR.

Hinweis:
- Details der Architektur stehen in `docs/ARCHITEKTUR_KERN.md`.