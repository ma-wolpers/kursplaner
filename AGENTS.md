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
- Feature- und Architektur-Aenderungen muessen im selben Zyklus in `docs/DEVELOPMENT_LOG.md` protokolliert werden.

4. Automatische Gates
- Lokaler Hook und CI pruefen die Guardrails ueber `tools/ci/check_ai_guardrails.py`.
- Ein Verstoß blockiert Commit/PR.

5. Zentrale UI-Steuerung
- KeyBindings werden zentral in `kursplaner/adapters/gui/keybinding_registry.py` verwaltet.
- Pop-up-Verhalten wird zentral in `kursplaner/adapters/gui/popup_policy.py` verwaltet.
- Neue Shortcuts und neue Pop-ups werden zuerst in diesen Zentralmodulen definiert und erst danach in konkrete Views eingebunden.

6. Feature-Commit und Push-Disziplin
- Feature-Aenderungen werden in eigenstaendigen Commits gebuendelt.
- Push erfolgt manuell durch den Nutzer; kein Auto-Push.

Hinweis:
- Details der Architektur stehen in `docs/ARCHITEKTUR_KERN.md`.