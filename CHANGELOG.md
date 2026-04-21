# Changelog

All notable user-facing changes to this project will be documented in this file.

The format is based on Keep a Changelog.

## [Unreleased]

### Changed
- Neue Hospitationen erzeugen jetzt den Dateititel im Format `Lerngruppe MM-DD Hospitation` statt mit doppelter Lerngruppen-Nennung im Titel.
- Beim Erstellen von Hospitationen wird in der Kurstabelle nur noch der Markdown-Link gespeichert, ohne zusaetzlichen `HO ...`-Praefixtext.
- Neue LZK-Dateititel nutzen das Fachkuerzel im Format `Lerngruppe MM-DD LZK Fachkuerzel HJ NR`.
- Der Hospitationsmodus zeigt `Stundenthema` aus der YAML-Datei in der Detailansicht analog zu Unterrichtseinheiten.
- Documentation governance now separates stable architecture reference from development history.
- Repo Path Guardrails wurden repariert; der CI-Check fuer persistierte JSON-Pfade laeuft wieder stabil mit einem vorhandenen Pruefskript.

### Added
- Public communication workflow via changelog, PR template, and release-ready structure.
