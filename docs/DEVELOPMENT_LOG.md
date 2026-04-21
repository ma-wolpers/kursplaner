# Development Log (kursplaner)

Dieses Dokument trackt technische Aenderungen fuer Feature- und Architekturarbeit.

Regel:
- Keine Feature- oder Architekturaenderung ohne Update in diesem Log.
- Bugfix-Only-Changes koennen ohne Eintrag erfolgen.

## [Unreleased]

### Changed
- HO/LZK-Erzeugung vereinheitlicht: neue Hospitationen speichern in der Kurstabelle nur noch den Markdown-Link, HO-Dateithemen werden ohne doppelte Lerngruppen-Nennung gesetzt, und LZK-Titel werden mit Fachkuerzel statt Vollfach erzeugt.
- Hospitations-Detailmodus erweitert: `Stundenthema` ist jetzt im Hospitationsmodus sichtbar, analog zur Themenanzeige bei Unterrichtseinheiten.
- Dokumentrollen formal getrennt: Architektur-Referenz (`docs/ARCHITEKTUR_KERN.md`) vs offene Arbeit (`docs/ARCHITEKTUR_UMSETZUNGSPLAN.md`) vs Verlauf (`docs/DEVELOPMENT_LOG.md`).
- Guardrail-Regeln erweitert um verpflichtendes Development-Log-Update fuer relevante Aenderungen.
- Repo-Path-Guardrails repariert: CI verwendet jetzt wieder ein vorhandenes Pruefskript (`tools/repo_ci/check_no_absolute_paths.py`) fuer absolute JSON-Pfade.
- AI-Guardrails erweitert, damit Workflow-/Script-Drift fuer Repo-Path-Checks frueh erkannt und lokal blockiert wird.
- ttk-Themekonfiguration erweitert: `TScrollbar`, `Horizontal.TScrollbar` und `Vertical.TScrollbar` werden zentral modern gestylt, damit Scrollbereiche in allen GUI-Teilen konsistent zur Theme-Sprache passen.

### Added
- `CHANGELOG.md` fuer oeffentliche, nutzerorientierte Kommunikation.
- `.github/pull_request_template.md` mit Pflichtfeldern fuer Doku- und Release-Kommunikation.

## [History]

### 2026-04-12
- Development-Log-Governance eingefuehrt und in Guardrails verankert.
