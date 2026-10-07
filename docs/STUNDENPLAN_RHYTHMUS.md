# Anleitung: Stundenplan eines Kurses (Feld `Rhythmus`)

Diese Anleitung beschreibt, wie der Kursplaner weiß, **an welchen Tagen** ein Kurs stattfindet, **wann** er beginnt und **wie viele Stunden** er dauert, und wie du das in der App oder direkt in der Plan-Datei einstellst.

Kurz gesagt: Jeder Kurs hat in seiner Plan-Datei ein Feld `Rhythmus`. Daraus berechnet der Kursplaner für jedes Datum Startzeit und Stundenzahl. Die Plantabelle selbst enthält keine Stunden-Spalte.

---

## 1. Wo steht der Stundenplan?

Ganz oben in der Plan-Datei eines Kurses (der Markdown-Datei mit der Plantabelle) steht ein YAML-Block zwischen zwei `---`-Zeilen:

```yaml
---
Lerngruppe: "[[GK blau-1]]"
Kursfach: "Mathematik"
Stufe: 11
Rhythmus:
  - "Mo 08:00 2"
  - "Do 07:50 2 gKW"
  - "Do 11:30 1 uKW"
---
```

Pflichtfelder sind `Lerngruppe` (als Wiki-Link), `Kursfach`, `Stufe` (1–13) und `Rhythmus`. Optional können `KC-Profil`, `Kompetenzen` und `Stundenziel` folgen.

---

## 2. Aufbau einer Rhythmus-Zeile

Jede Zeile unter `Rhythmus:` beschreibt **einen Unterrichtstag pro Woche**:

```text
[ab TT-MM-JJ] Wochentag Startzeit Stunden [gKW | uKW]
```

| Teil | Pflicht? | Bedeutung | Beispiel |
|---|---|---|---|
| `ab TT-MM-JJ` | nein | Gilt erst ab diesem Datum (siehe Abschnitt 4) | `ab 20-04-26` |
| Wochentag | ja | `Mo`, `Di`, `Mi`, `Do`, `Fr` (auch `Sa`, `So`) | `Do` |
| Startzeit | ja | Uhrzeit im Format `HH:MM` | `07:50` |
| Stunden | ja | Anzahl Stunden an diesem Tag, 1 bis 4 | `2` |
| `gKW` / `uKW` | nein | Nur in **g**eraden bzw. **u**ngeraden Kalenderwochen (siehe Abschnitt 3) | `gKW` |

Beispiele:

| Zeile | Bedeutung |
|---|---|
| `"Mo 08:00 2"` | jeden Montag, ab 08:00, 2 Stunden |
| `"Do 07:50 2 gKW"` | Donnerstag nur in geraden Kalenderwochen, 07:50, 2 Stunden |
| `"Fr 11:30 1 uKW"` | Freitag nur in ungeraden Kalenderwochen, 11:30, 1 Stunde |
| `"ab 20-04-26 Di 10:00 2"` | ab dem 20.04.2026 jeden Dienstag, 10:00, 2 Stunden |

Tipp: Die Zeilen in Anführungszeichen setzen (`- "Mo 08:00 2"`). So schreibt sie auch der Kursplaner selbst.

---

## 3. Zweiwöchiger Unterricht (`gKW` / `uKW`)

Findet ein Tag nur alle zwei Wochen statt, hängst du am Zeilenende ein Kürzel an:

- `gKW` = nur in **geraden** Kalenderwochen (KW 2, 4, 6, …)
- `uKW` = nur in **ungeraden** Kalenderwochen (KW 1, 3, 5, …)
- ohne Kürzel = **jede** Woche

### A/B-Woche: derselbe Tag, verschieden je Woche

Ein Wochentag darf einen `gKW`- **und** einen `uKW`-Eintrag haben, jeweils mit eigener Startzeit und Stundenzahl:

```yaml
Rhythmus:
  - "Do 07:50 2 gKW"
  - "Do 11:30 1 uKW"
```

→ In geraden Wochen donnerstags 2 Stunden ab 07:50, in ungeraden Wochen 1 Stunde ab 11:30.

### Was nicht erlaubt ist

Innerhalb eines Abschnitts (gleiches `ab`-Datum bzw. ohne `ab`) darf ein Wochentag nur auf eine dieser Arten vorkommen:

- **einmal ohne Kürzel** (jede Woche), **oder**
- **höchstens einmal mit `gKW` und höchstens einmal mit `uKW`**.

Nicht erlaubt sind also z. B. `"Mo 08:00 2"` zusammen mit `"Mo 10:00 1 gKW"` oder zweimal `Mo … gKW`. Solche Dateien lehnt der Kursplaner beim Laden mit einer Fehlermeldung zum Feld `Rhythmus` ab.

### Welche Kalenderwoche zählt?

Gezählt wird nach der **ISO-Kalenderwoche** (die übliche „KW“ im deutschen Kalender). In Jahren mit 53 Kalenderwochen folgen zwei ungerade Wochen direkt aufeinander, z. B. **KW 53/2026 und KW 1/2027**. Ein `uKW`-Tag findet dann zweimal hintereinander statt, ein `gKW`-Tag hat eine Woche länger Pause. Meist liegen diese Wochen ohnehin in den Weihnachtsferien.

---

## 4. Stundenplanwechsel im Halbjahr (`ab`-Abschnitte)

Ändert sich der Stundenplan im Laufe des Kurses, bleibt der alte Rhythmus für die vergangenen Wochen erhalten. Der neue Rhythmus steht darunter mit `ab <Datum>`:

```yaml
Rhythmus:
  - "Mo 08:00 2"
  - "Do 07:50 2"
  - "ab 20-04-26 Di 10:00 2"
  - "ab 20-04-26 Do 07:50 2 gKW"
```

Alle Zeilen mit demselben `ab`-Datum bilden einen **Abschnitt**. Die Zeilen ohne `ab` bilden den **Grundrhythmus** seit Kursbeginn.

**Wichtig: Ein `ab`-Abschnitt beschreibt den vollständigen Rhythmus ab diesem Datum.** Wochentage, die im Abschnitt nicht vorkommen, finden ab dann nicht mehr statt. Im Beispiel gilt ab dem 20.04.2026:

- Dienstag 10:00, 2 Stunden (neu)
- Donnerstag nur noch in geraden Wochen
- **kein Montag mehr**, weil `Mo` im Abschnitt fehlt.

Willst du nur einen Tag ändern, musst du die unveränderten Tage im neuen Abschnitt trotzdem wiederholen.

Weitere Regeln:

- Für ein Datum gilt immer der Abschnitt mit dem **spätesten `ab`-Datum, das nicht nach diesem Datum liegt**.
- Es muss immer **mindestens eine Zeile ohne `ab`** geben (Grundrhythmus). Sonst wäre unklar, was vor dem ersten `ab`-Datum gilt, und die Datei wird abgelehnt.
- Das Datumsformat ist `TT-MM-JJ`, also z. B. `20-04-26` für den 20.04.2026.

---

## 5. Einstellen in der App

### Neuer Kurs

Im Dialog **„Neuer Kurs“** gibt es den Bereich **„Unterrichtsrhythmus (Mo–Fr)“**. Pro Wochentag:

1. **Häkchen** setzen, wenn an diesem Tag Unterricht ist. Ohne Häkchen wird der Tag ignoriert, auch wenn Felder ausgefüllt sind.
2. **Woche** wählen:
   - **jede Woche**
   - **gKW**: nur gerade Kalenderwochen
   - **uKW**: nur ungerade Kalenderwochen
   - **gKW + uKW**: A/B-Woche. Es erscheint eine zweite Zeile: Die Zeile **g** gilt für gerade Wochen, die Zeile **u** für ungerade.
3. **Startzeit** (`HH:MM`) und **Stunden** (1–4) eintragen.

Beim Anlegen erzeugt der Kursplaner die Plantabelle mit allen Terminen. Zweiwöchige Tage erscheinen nur in den passenden Wochen.

### Stundenplanänderung

Menü **Aktion → Stundenplanänderung…**:

1. **Von** / **Bis** festlegen. Die Knöpfe **Kursbeginn** und **Kursende** füllen das erste bzw. letzte Plandatum ein.
2. Den neuen Rhythmus wie oben einstellen. Der Dialog ist mit dem heute gültigen Rhythmus vorbelegt.
3. **Berechnen**: Links steht der alte Plan, rechts der Entwurf. Die Inhalte der bisherigen Stunden werden der Reihe nach auf die neuen Termine verteilt. Mit **Ausfall / Stattfinden**, **↑ / ↓** und **Entfernen** lässt sich der Entwurf anpassen.
4. **Übernehmen** schreibt die neuen Termine und den Rhythmus in die Plan-Datei.

Was dabei im Feld `Rhythmus` passiert:

- **Änderung mitten im Kurs:** Der neue Rhythmus wird als `ab <Von>`-Abschnitt angehängt.
- **Änderung ab dem ersten Plantag:** Der Rhythmus wird von Beginn an ersetzt (ohne `ab`).
- **„Bis“ liegt vor dem Kursende (befristete Änderung):** Ab dem Tag nach „Bis“ gilt automatisch wieder der vorherige Rhythmus. Dafür steht ein weiterer `ab`-Abschnitt in der Datei.

Beispiel: Grundrhythmus `Mo 08:00 2`, vom 09.03. bis 15.03.2026 ausnahmsweise `Mo 11:30 1`:

```yaml
Rhythmus:
  - "Mo 08:00 2"
  - "ab 09-03-26 Mo 11:30 1"
  - "ab 16-03-26 Mo 08:00 2"
```

### Plan verlängern

Der Button **„Plan bis nächste Ferien erweitern“** (Strg+E) hängt Termine bis zum nächsten Ferienbeginn an. Er folgt dem Rhythmus inklusive aller `ab`-Abschnitte und `gKW`/`uKW`-Kürzel. Die letzte Zeile ist der Ferienbeginn als Ferienzeile (siehe Abschnitt 6).

### Kommandozeile (`planer_cli.py`)

Für jeden Wochentag fragt die CLI zuerst `Woche (leer = jede, g, u, gu)`, danach Stunden und Startzeit. Bei `gu` werden Stunden und Startzeit getrennt für gerade und ungerade Wochen abgefragt. Ungültige Eingaben werden erneut abgefragt.

---

## 6. Die Plantabelle

Unter dem YAML-Block steht die Plantabelle mit genau drei Spalten:

```text
| Datum | Inhalt | Thema/Ausfall |
| --- | --- | --- |
| 03-09-26 | [[ab12cd]] |  |
| 10-09-26 |  | Bruchrechnung |
| 17-09-26 |  | X Wandertag |
| 15-10-26 |  | X Herbstferien X |
```

| Spalte | Inhalt |
|---|---|
| `Datum` | Termin im Format `TT-MM-JJ` |
| `Inhalt` | Link auf die Einheiten-Datei (z. B. `[[ab12cd]]`) oder leer |
| `Thema/Ausfall` | Oberthema einer noch nicht angelegten Einheit, oder ein Ausfall-Marker |

Ausfall-Marker:

- `X <Grund>`: Ausfall, z. B. `X Wandertag`
- `X <Grund> X` (mit Schluss-X): Ferien oder Feiertag, z. B. `X Herbstferien X`. Diese Zeilen setzt der Kursplaner beim Anlegen und Verlängern automatisch.

**Startzeit und Stunden stehen nicht in der Tabelle.** Der Kursplaner berechnet sie für jedes Datum aus dem `Rhythmus`. Ferien- und Ausfallzeilen zählen immer mit 0 Stunden, auch wenn der Rhythmus an diesem Tag eigentlich Unterricht vorsieht.

---

## 7. Häufige Fehler

| Meldung / Problem | Ursache | Lösung |
|---|---|---|
| Datei wird abgelehnt, Feld `Rhythmus` ungültig | Wochentag doppelt im selben Abschnitt, oder „jede Woche“ zusammen mit `gKW`/`uKW` | pro Abschnitt und Tag entweder eine Zeile ohne Kürzel oder je eine mit `gKW`/`uKW` |
| Datei wird abgelehnt, Feld `Rhythmus` ungültig | nur `ab`-Zeilen, keine Grundzeile | mindestens eine Zeile ohne `ab` ergänzen |
| Ein Tag fehlt nach einem `ab`-Datum | der Tag steht nicht im `ab`-Abschnitt | Tag im Abschnitt wiederholen (Abschnitt 4) |
| Zweiwöchiger Tag „springt“ um den Jahreswechsel | Jahr mit KW 53 | gewolltes Verhalten (Abschnitt 3) |
| Falsches Format | z. B. `Mo 8:00 2`, `Mo 08:00 5`, `ab 20.04.26 …` | Startzeit `HH:MM`, Stunden 1–4, Datum `TT-MM-JJ` |
