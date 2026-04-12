# adapters

Hauptverantwortung: Übersetzt UI/CLI-Interaktionen in Use-Case-Aufrufe und rendert Ergebnisse zurück in die jeweilige Oberfläche.

Regeln:
- keine Fachentscheidungen und keine Persistenz-Orchestrierung,
- keine direkten Datei-I/O-Implementierungen,
- Verdrahtung nur über `adapters/bootstrap`.
