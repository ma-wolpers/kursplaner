"""Bewusster mypy-Guard gegen künftige Protocol/Implementierungs-Drift.

Root Cause eines bereits einmal aufgetretenen Bugs (siehe docs/DEVELOPMENT_LOG.md): Protocols in
`core/ports/repositories.py` und ihre konkreten Implementierungen hier in der Infrastructure-
Schicht werden manuell synchron gehalten, ohne automatisierte Prüfung -- mypy erkennt eine Lücke
bisher nur zufällig, an der jeweiligen Aufrufstelle, die tatsächlich durch den Protocol-Typ
hindurch aufruft (nicht überall, wo eine konkrete Klasse instanziiert wird).

Bewusst hier in `infrastructure/repositories/` platziert, nicht in `core/ports/`: die Hexagonal-
Architektur erlaubt Infrastructure, von core/ports UND von den eigenen konkreten Klassen
abzuhängen -- ein core/ports-Modul dürfte umgekehrt nicht von infrastructure importieren.

Jede Funktion unten wird NIE aufgerufen -- reiner Compile-Zeit-Mechanismus. mypy prüft jede Datei
im Paket unabhängig vom Import-Graphen, die Funktionen müssen also nirgends importiert werden, um
wirksam zu sein. Driftet eine konkrete Klasse künftig vom Protocol ab (fehlende Methode in beide
Richtungen), schlägt genau die passende Funktion hier mit einem sofortigen, eindeutigen mypy-Fehler
fehl, statt erst zufällig an einer neuen Aufrufstelle aufzufallen.

Bewusst KEIN generisches, instanziierungsfreies Protocol-Framework -- dieser kleine Guard reicht
für die aktuell betroffenen drei Paare. Voraussetzung: alle drei konkreten Klassen sind ohne
Konstruktor-Argumente instanziierbar (verifiziert). Bekommt eine von ihnen künftig einen
Pflicht-Parameter, schlägt die jeweilige Funktion hier mit einem klaren "fehlendes Argument"-Fehler
fehl -- der akzeptierte Wartungsaufwand ist dann, hier einen passenden Beispielwert zu ergänzen.

Umfang bewusst auf die drei bereits einmal betroffenen Paare begrenzt, nicht auf alle Protocol-
Klassen in `repositories.py` ausgeweitet -- trivial erweiterbar, falls gewünscht.
"""

from __future__ import annotations

from kursplaner.core.ports.repositories import (
    CommandRepository,
    KompetenzkatalogRepository,
    SubjectSourceRepository,
)
from kursplaner.infrastructure.repositories.command_repository import FileSystemCommandRepository
from kursplaner.infrastructure.repositories.kompetenzkatalog_repository import (
    FileSystemKompetenzkatalogRepository,
)
from kursplaner.infrastructure.repositories.subject_source_repository import (
    FileSystemSubjectSourceRepository,
)


def _conforms_to_command_repository() -> CommandRepository:
    return FileSystemCommandRepository()


def _conforms_to_subject_source_repository() -> SubjectSourceRepository:
    return FileSystemSubjectSourceRepository()


def _conforms_to_kompetenzkatalog_repository() -> KompetenzkatalogRepository:
    return FileSystemKompetenzkatalogRepository()
