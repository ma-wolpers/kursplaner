# Copilot Workflow (kursplaner)

Ziel: Du beschreibst nur die Aenderung. Copilot setzt Umsetzung und Pflicht-Doku konsistent mit Guardrails um.

## Standard-Prompt (empfohlen)

Nutze diese Formulierung am Ticket-Start:

"Setze folgende Aenderung um: <Beschreibung>. Halte Guardrails ein, aktualisiere Pflichtdokumente (Development-Log bei Feature/Architektur, Architektur-Kern nur bei Regel-/Leitplanken-Aenderung, Umsetzungsplan nur fuer offene Arbeit), aktualisiere Changelog bei nutzerrelevanten Aenderungen, fuehre Checks aus und liste am Ende alle geaenderten Dateien auf."

## Was Copilot im Regelfall mitziehen soll

1. Code-Aenderung in betroffenen Schichten.
2. `docs/DEVELOPMENT_LOG.md` bei Feature-/Architektur-Aenderung.
3. `docs/ARCHITEKTUR_KERN.md` nur bei stabilen Regel-/Leitplanken-Aenderungen.
4. `docs/ARCHITEKTUR_UMSETZUNGSPLAN.md` nur fuer offene Pakete, nie als Historie.
5. `CHANGELOG.md` bei nutzerrelevanter Aenderung.
6. PR-Checkliste in `.github/pull_request_template.md` beachten.

## Wann du kurz nachschaerfen solltest

1. Wenn unklar ist, ob die Aenderung Feature oder Bugfix-only ist.
2. Wenn mehrere Architekturgrenzen beruehrt werden.
3. Wenn ein Eintrag in `ARCHITEKTUR_UMSETZUNGSPLAN.md` als offenes Folgepaket benoetigt wird.

## Minimaler Review-Check (30 Sekunden)

1. Sind Code, Development-Log und ggf. Changelog zusammen aktualisiert?
2. Wurde `ARCHITEKTUR_KERN.md` nur dann angepasst, wenn Regeln wirklich geaendert wurden?
3. Ist der Umsetzungsplan weiterhin nur offene Arbeit?
4. Sind Guardrail-Checks gruen?

## Verbindliche Quellen in kursplaner

1. Guardrails: `AGENTS.md`
2. Copilot-Regeln: `.github/copilot-instructions.md`
3. Architektur Ist-Zustand: `docs/ARCHITEKTUR_KERN.md`
4. Offene Architekturarbeit: `docs/ARCHITEKTUR_UMSETZUNGSPLAN.md`
5. Entwicklungsverlauf: `docs/DEVELOPMENT_LOG.md`
6. Oeffentliche Kommunikation: `CHANGELOG.md`
