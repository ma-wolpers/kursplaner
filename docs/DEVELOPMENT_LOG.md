# Development Log (kursplaner)

Dieses Dokument trackt technische Aenderungen fuer Feature- und Architekturarbeit.

Regel:
- Keine Feature- oder Architekturaenderung ohne Update in diesem Log.
- Bugfix-Only-Changes koennen ohne Eintrag erfolgen.

## [Unreleased]

### Changed
- Strg+Enter fuer Spaltenmodus ausgebaut: im Spaltenauswahlmodus oeffnet jetzt ein typabhaengiger Bestaetigungsdialog (Unterricht, LZK, Ausfall, Hospitation) statt des reinen Edit-Commits.
- Unterricht-Dialog bei Strg+Enter nutzt denselben Builder wie bei neuer Planung, aber mit Voll-Prefill aus bestehender Stunde (YAML + Inhalte/Methodik-Abschnitte aus Markdown), sodass bestehende Spaltenwerte direkt bearbeitbar sind.
- Ausfall/Hospitation auf bestehendem Dialogmuster belassen und um Vorbelegung erweitert (Ausfallgrund aus Markertext, Beobachtungsschwerpunkt aus YAML).
- Neues separates LZK-MVP-Fenster fuer Strg+Enter hinzugefuegt; optionaler Titel-Override, anschliessend bestehender LZK-Write-Flow.
- Escape-Verhalten in Popup-Basisklasse verfeinert: Esc schliesst nur sofort bei Popup-Fokus; bei Fokus in editierbaren Eingabefeldern wird zunaechst auf Popup-Ebene fokussiert.
- UB-Fokus in der GUI ausgebaut: Kursuebersicht zeigt jetzt `Naechster UB` im Format `D.M. Initialen+` (leer ohne zukuenftigen UB), Einheiten mit UB erhalten eine theme-abhaengige Vollspalten-Umrandung.
- UB-Interaktion umgestellt: erneuter Klick auf UB oeffnet den UB-Dialog zur Bearbeitung (mit Vorbelegung) statt sofortigem Entfernen; Loeschen erfolgt jetzt explizit ueber eigene Dialogaktion.
- UB-Ansicht als Tab-UI neu strukturiert: `Achievements`, `UB-Plan` (kommende/absolvierte Listen mit Spalten `Datum`, `Faecher`, `+`, `Kurs`) und `Entwicklungsimpulse`; Tabwechsel per Maus und Pfeiltasten.
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
