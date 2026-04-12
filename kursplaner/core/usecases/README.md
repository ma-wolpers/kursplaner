# core/usecases

Hauptverantwortung: Orchestriert je Nutzerabsicht genau einen fachlichen Ablauf über Ports.

Regeln:
- Transaktionsgrenze liegt im Use Case,
- Konfliktstrategie und Delta-Erzeugung liegen im Use Case,
- keine direkten konkreten I/O-Implementierungen.
