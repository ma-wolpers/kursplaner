# kursplaner — Architektur einfach erklärt

Stand: 2026-03-01

Dieses Dokument ist die **einfachste Erklärung** der Projekt-Architektur.

Wenn du nur eine Sache mitnimmst, dann diese:

> Die GUI zeigt Dinge an und fragt Dinge ab. Die Fachlogik entscheidet. Das Dateisystem speichert.

---

## 1) Warum gibt es diese Architektur überhaupt?

Ohne klare Architektur passiert schnell Chaos:

- dieselbe Regel steht an 3 Stellen,
- kleine Änderungen machen an anderer Stelle etwas kaputt,
- Bugs sind schwer zu finden.

Mit dieser Architektur gilt:

- jede Schicht hat eine klare Aufgabe,
- Änderungen sind planbar,
- Tests sind einfacher.

---

## 1.1 Begriffe fuer Ansichten (UI-Terminologie)

Damit in Tickets und Diskussionen klar ist, welche Ansicht gemeint ist, gelten diese Begriffe:

- Kursraster: die rechte Hauptansicht, in der jede Spalte eine Einheit/Planzeile darstellt.
- Schattenliste: die linke Liste im Dialog "Schatteneinheiten", die unverlinkte Einheitsdateien zeigt.
- Schattenvorschau: die rechte Vorschau im Dialog "Schatteneinheiten" mit dem rohen Dateiinhalt inkl. YAML-Frontmatter.
- Plantabelle: die Markdown-Tabelle in der Plan-Datei mit den Spalten Datum, Stunden, Inhalt.

---

## 2) Die 5 Bausteine (ohne Fachwörter)

## 2.1 Domain (`core/domain`)

**Was ist das?**
- Die fachlichen Daten und Regeln.

**Merksatz:**
- „Was ist fachlich richtig?“

**Beispiel:**
- Was ist eine Planzeile?
- Wann ist etwas eine LZK?

## 2.2 Use Cases (`core/usecases`)

**Was ist das?**
- Konkrete Aktionen wie „Stunde planen“, „Ausfall setzen“, „Overview berechnen“.

**Merksatz:**
- „Was will der Nutzer tun?“

**Wichtig:**
- Use Cases treffen fachliche Entscheidungen.
- Use Cases kennen **keine** GUI-Widgets.

## 2.3 Ports (`core/ports`)

**Was ist das?**
- Schnittstellen/Verträge, z. B. „So spricht man mit einem Lesson-Repository“.

**Merksatz:**
- „Was wird gebraucht, aber nicht wie es technisch gemacht wird.“

## 2.4 Infrastructure (`infrastructure`)

**Was ist das?**
- Der technische Teil: Dateien lesen/schreiben, Markdown/YAML/Index.

**Merksatz:**
- „Wie wird gespeichert und geladen?“

## 2.5 Adapter (`adapters/gui`, `adapters/cli`)

**Was ist das?**
- GUI/CLI-Schicht.

**Merksatz:**
- „Eingabe rein, Ergebnis raus.“

**Wichtig:**
- Adapter sollen nicht fachlich entscheiden.

---

## 3) Der wichtigste Ort: Composition Root

Datei: `adapters/bootstrap/wiring.py`

Hier wird alles „verkabelt“:

- konkrete Repositories werden gebaut,
- Use Cases werden mit diesen Repositories verbunden,
- GUI bekommt fertige Abhängigkeiten.

**Regel:**
- Direkte Infra-Instanziierung gehört hierhin (und nicht in GUI-Dateien).

---

## 4) Wie läuft eine Aktion ab?

Beispiel: „Stunde als Ausfall markieren“

1. GUI erkennt, was markiert wurde.
2. GUI ruft den passenden Use Case auf.
3. Use Case entscheidet fachlich, was geändert werden muss.
4. Repository speichert die Änderung.
5. GUI aktualisiert die Anzeige.

So bleibt die Logik an einer Stelle und nicht im UI verteilt.

---

## 5) Index-Idee (warum der Lesson-Index wichtig ist)

Früher musste die App für Übersichten zu viele Dateien einzeln lesen.

Jetzt gibt es einen Lesson-Index:

- liefert schnelle Metadaten (z. B. `Stundenthema`, `Oberthema`),
- reduziert unnötige Dateizugriffe,
- macht Overview-Queries schneller.

Dazu gibt es:

- Rebuild-Use Case,
- Invalidate-Use Case,
- UI/CLI-Trigger zum Neuaufbau.

---

## 6) 3 Goldene Regeln für neue Änderungen

1. **Neue Fachregel?** -> in Domain/Use Case, nicht in GUI.
2. **Neuer Datei-Zugriff?** -> über Port + Infrastructure.
3. **Neue GUI-Aktion?** -> GUI ruft genau einen klaren Use Case/Flow auf.

---

## 7) Woran erkennst du einen Architektur-Fehler?

Warnzeichen:

- „Ich lese schnell direkt in der GUI eine Datei ein…“
- „Ich entscheide hier im Button-Handler fachlich…“
- „Ich importiere schnell `infrastructure` außerhalb von `wiring.py`…“

Wenn eines davon passiert: kurz stoppen, sauber in Schichten aufteilen.

---

## 8) Mini-Checkliste vor Merge

- Liegt Fachlogik im Use Case statt im Adapter?
- Läuft I/O über Port + Repository?
- Bleibt `wiring.py` die zentrale Verdrahtung?
- Sind Tests grün?
- Ist die Doku aktualisiert?

---

## 8.1 Wichtiger Undo-Hinweis für Exporte

- Undo/Redo stellt fachliche Daten und textbasierte Dateien vollständig wieder her.
- Binäre Exportdateien (z. B. PDF) werden als generierbare Artefakte behandelt.
- Das heißt: Nach Undo kann eine PDF auf dem zuletzt exportierten Stand bleiben und wird bei Bedarf neu exportiert.

## 8.2 Wichtiger Overwrite-Hinweis für Erwartungshorizont-Export

- Ziel der Export-Funktion ist, die EH-Tabelle zuverlässig ausfüllen zu können, ohne durch unachtsames Überschreiben Bewertungsdaten zu verlieren.
- Beim erneuten Export bleiben vorhandene Werte in `AFB | Aufg | Pkte` erhalten, sofern Zeilen fachlich zusammenpassen.
- Entfallene, bereits bewertete Ziele bleiben sichtbar markiert (z. B. `~~...~~`) statt still entfernt zu werden.

---

## 9) Wenn du unsicher bist

Arbeite immer nach diesem Muster:

1. **Use Case zuerst denken** (was soll fachlich passieren?),
2. dann **Port** (welche Daten braucht der Use Case?),
3. dann **Infrastructure** (technische Umsetzung),
4. zuletzt **GUI anbinden**.

Damit bleibt der Kern stabil und die Oberfläche austauschbar.
