# Einheitendateien: Schema und Governance

## Zweck

Dieses Dokument definiert verbindlich,

- wo die Regeln fuer Einheitendateien liegen,
- welche Datei die jeweilige Single Source of Truth ist,
- und welche Schritte bei Aenderungen immer gemeinsam ausgefuehrt werden muessen.

Ziel: Verhindern, dass nur ein Teil (z. B. nur README oder nur Code) geaendert wird.

## Single Source of Truth

1. YAML-Feldmenge pro Typ:
`kursplaner/core/domain/lesson_yaml_policy.py`

2. Erforderliche YAML-Mindestvalidierung beim Parsen:
`kursplaner/core/domain/yaml_registry.py`

3. Dateibenennung (`Lerngruppe mm-dd Titel`):
`kursplaner/core/domain/lesson_naming.py`

4. Persistenz/Kanonisierung beim Lesen/Schreiben:
`kursplaner/infrastructure/repositories/plan_table_file_repository.py`

5. Benutzernahe Beschreibung:
`README.md`

6. Vault-Bestandsaufnahme (Ist-Dateien):
`7thVault/🏫 Pädagogik/10 Unterricht/YAML-Tags Einheitendateien.md`

## Verbindliche Regel

Aenderungen an YAML-Schema oder Dateinamen gelten nur dann als fertig, wenn alle betroffenen Ebenen synchronisiert wurden.

## Pflicht-Checkliste bei Aenderungen

1. Domain-Regel anpassen:
`lesson_yaml_policy.py` und/oder `lesson_naming.py`
2. Parser-/Schema-Regel anpassen:
`yaml_registry.py`
3. Repository-Kanonisierung pruefen/anpassen:
`plan_table_file_repository.py`
4. Schreib-UseCases pruefen/anpassen (Typsetzung, Rename):
`core/usecases/*.py`
5. Tests/Fixures anpassen:
`tests/*.py`
6. README aktualisieren:
`README.md`
7. Vault-Uebersicht aktualisieren:
`7thVault/🏫 Pädagogik/10 Unterricht/YAML-Tags Einheitendateien.md`
8. Migration planen/ausfuehren fuer bestehende Dateien (falls notwendig):
einmaliges Migrationsskript im jeweiligen Branch (nicht als dauerhafte Projektabhaengigkeit)
9. Validieren:
- `get_errors` ohne Fehler
- Tabellenlinks aufloesbar
- YAML in Einheitendateien enthaelt nur erlaubte Felder

## Review-Regel (Pull Request / Selbstcheck)

Ein Review muss explizit bestaetigen:

- Rule-Code aktualisiert (`lesson_yaml_policy.py`, `lesson_naming.py`)
- Enforcement aktualisiert (`yaml_registry.py`, Repository)
- Doku aktualisiert (`README.md`, dieses Dokument, Vault-Uebersicht)
- Tests/Fixures angepasst

Wenn einer dieser Punkte fehlt, ist die Aenderung nicht done.

## Automatischer Guardrail

Vor Commit ausfuehren:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\ci\check_einheiten_schema_consistency.ps1
```

Der Check bricht mit Exit-Code 1 ab, wenn eine Einheitendatei gegen Naming- oder YAML-Regeln verstoesst.

