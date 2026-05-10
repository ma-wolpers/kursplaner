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
- Bei Feature- und Architektur-Aenderungen immer `docs/DEVELOPMENT_LOG.md` im selben Zyklus aktualisieren.

5. Guardrails sind bindend
- `tools/ci/check_ai_guardrails.py` muss lokal und in CI bestehen.

6. Zentrale UI-Module
- KeyBindings zentral in `bw_libs/ui_contract/keybinding.py` verwalten.
- Pop-up-Regeln zentral in `bw_libs/ui_contract/popup.py` verwalten.
- Neue Shortcut-/Popup-Funktionen zuerst zentral registrieren, dann an Views anbinden.

7. Strict bw-gui-only-Policy
- Keine lokale tkinter/ttk-Widgetimplementierung in Repos.
- Neue wiederverwendbare GUI-Bausteine zuerst in bw-gui implementieren und erst danach in Repos anbinden.

8. Commit-/Push-Workflow
- Feature-Aenderungen als eigene Commits strukturieren.
- Push bleibt manuell; kein automatisches Pushen.