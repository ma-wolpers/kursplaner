# GUI Theme Design Decisions

## Leitidee
Die GUI soll neutral starten (helles Grau/Weiss oder dunkles Grau/Schwarz), aber im Betrieb klar lesbare Farbinformation tragen.

Deshalb ist das System zweistufig:
1. Neutrales Fundament fuer Flaechen und Typografie.
2. Farbkanäle fuer Interaktion, Auswahl und fachliche Zustände.

So vermeiden wir zwei Extreme:
- Monochromie (alles wirkt gleich)
- Farbchaos (zu viele unverbundene Akzente)

## Farbarchitektur

### 1) Neutralleiter (Raum und Hierarchie)
- `bg_main`: Fenstergrund
- `bg_panel`: Sekundäre Container
- `bg_surface`: Eingabe-/Contentflaechen
- `panel_strong`: starke Trennung (Toolbar, Header)

### 2) Interaktion
- `accent`, `accent_hover`, `accent_soft`
- `focus_ring`

### 3) Auswahl
- `selection_bg`, `selection_fg`
- Eigener Kanal, damit Auswahl nicht mit Statusfarben kollidiert.

### 4) Semantik
- `info`, `success`, `warning`, `danger` plus `*_soft`
- Soft-Varianten fuer Flaechenhinweise, starke Varianten fuer aktive Controls.

## Button-Design-Entscheidung
Buttons sind nicht mehr einfarbig. Sie sind jetzt zweckgebunden eingefaerbt:
- Unterricht: `Action.Unterricht.TButton` (Interaktionsfarbe)
- LZK: `Action.Lzk.TButton` (Gruen-Kanal)
- Hospitation: `Action.Hospitation.TButton` (Lila-Kanal)
- Ausfall / Ausfall zurueck: `Action.Ausfall.TButton` (Orange/Braun-Kanal)
- Utility-Aktionen: `Action.Utility.TButton` (neutral)
- Ansichtsbuttons: gleiche Funktionsfarben wie die fachlichen Aktionen, aber in dezenterer Auspraegung

Damit ist die Toolbar auf einen Blick lesbar: fachliche Eingriffe sind visuell unterscheidbar, Hilfsaktionen bleiben ruhig.

## Konsistenzregel Buttons <-> Spalten
Die semantische Kanalzuordnung gilt sowohl fuer Buttons als auch fuer die Spalten-/Headerdarstellung:
- LZK = gruener Kanal
- Ausfall = orange/brauner Kanal
- Hospitation = lila Kanal

Dadurch entspricht die Farbwirkung der Plan-Spalte ihrer zugehoerigen Aktion.

## Rahmen in Dark Themes
ttk/clam erzeugt ohne Overrides haeufig helle Kanten.
Deshalb werden fuer Buttons, Entries, Combobox und Treeview explizit gesetzt:
- `bordercolor`
- `lightcolor`
- `darkcolor`

Das verhindert die vorherigen "weissen Rahmen" in dunklen Designwelten.

## Designwelten und Titel-Rationale

### Mono Day
- Einstimmung: ruhige, klare Tagesansicht fuer lange Organisationsphasen.
- Warum der Titel: "Mono" steht fuer neutrales Fundament, "Day" fuer helle Arbeitsumgebung.

### Porcelain
- Einstimmung: glatte, aufgeraeumte Oberflaeche wie ein heller Arbeitstisch.
- Warum der Titel: "Porcelain" beschreibt die helle, saubere Materialanmutung ohne Farbstich in den Flaechen.

### Steel Morning
- Einstimmung: praezise, sachliche Morgen-Session mit klarer Rasterwirkung.
- Warum der Titel: "Steel" steht fuer strukturierte Kante, "Morning" fuer die helle Neutralbasis.

### Foglight
- Einstimmung: weichere, nebelhelle Tagesansicht mit klaren Signalfarben.
- Warum der Titel: "Fog" fuer diffuse neutrale Basis, "Light" fuer hohe Lesbarkeit.

### Ledger
- Einstimmung: ordentliche, tabellarische Arbeitswelt mit Buchhaltungs-Praezision.
- Warum der Titel: "Ledger" betont Listen-/Rasterarbeit und visuelle Disziplin.

### Mono Night
- Einstimmung: dunkle, konzentrierte Session ohne farbige Grundflaechen.
- Warum der Titel: Gegenstueck zu Mono Day mit identischem Neutralprinzip in dunkel.

### Graphite Core
- Einstimmung: technisch-klares Dark Theme fuer hohe Informationsdichte.
- Warum der Titel: "Graphite" fuer neutralen Dunkelkern, "Core" fuer Fokus auf Arbeitsfunktion.

### Charcoal
- Einstimmung: reduzierte, matte Dunkelwelt mit klaren Signalakzenten.
- Warum der Titel: "Charcoal" beschreibt die tiefe, nicht-bunte Grundflaeche.

### Blackforge
- Einstimmung: tiefdunkle Werkbank-Atmosphaere, Signalfarben wie Werkzeuge.
- Warum der Titel: "Forge" verweist auf aktive Bearbeitung, "Black" auf die neutrale Basis.

### Farbkanal-Mapping (fachlich)
- Unterricht: Akzentkanal des Themes
- LZK: Gruen
- Hospitation: Lila
- Ausfall: Orange/Braun

## Warum das jetzt stimmig ist
1. Das Auge bekommt ruhige Basisflaechen.
2. Interaktion und Zustände sind trotzdem sofort differenzierbar.
3. Die Themen unterscheiden sich sichtbar, ohne das Neutralprinzip aufzugeben.
