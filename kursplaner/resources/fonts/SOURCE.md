# Gebündelte PDF-Schrift: DejaVu Sans 2.37

Alle PDF-Exporte des Kursplaners (Sequenzplan, Kompetenzhorizont, Achievement-Report)
betten diese Schrift ein, damit Umlaute und Sonderzeichen wie `→ ≤ α` korrekt erscheinen
(die Standardschrift Helvetica kann nur WinAnsi). Registrierung: `kursplaner/infrastructure/export/pdf_fonts.py`.

## Herkunft (reproduzierbar)

- Projekt: DejaVu Fonts, Version **2.37**
- Release: <https://github.com/dejavu-fonts/dejavu-fonts/releases/tag/version_2_37>
- Archiv: <https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.zip>
- SHA-256 des Archivs: `7576310b219e04159d35ff61dd4a4ec4cdba4f35c00e002a136f00e96a908b0a`
- Abgerufen: 2026-10-06
- Übernommene Dateien (unverändert aus `dejavu-fonts-ttf-2.37/ttf/` bzw. Archivwurzel):

| Datei | SHA-256 |
| --- | --- |
| `DejaVuSans.ttf` | `7da195a74c55bef988d0d48f9508bd5d849425c1770dba5d7bfc6ce9ed848954` |
| `DejaVuSans-Bold.ttf` | `e6476c1b80502924294eed40894c5b18e06c181444ca953e5334262df9c27724` |
| `DejaVuSans-Oblique.ttf` | `4af75fa16ee6d3ad43e1ecec41862c24954af26a55c6bb1ebb27bd486a50f5f4` |
| `DejaVuSans-BoldOblique.ttf` | `eb436dca0c2594b73d8b603b892e374fdfd8d885d25ffb4f18df4c4c0b49e50f` |
| `LICENSE` | `7a083b136e64d064794c3419751e5c7dd10d2f64c108fe5ba161eae5e5958a93` |

## Lizenz

Bitstream-Vera-Lizenz mit DejaVu-Änderungen (Public Domain) sowie Arev-Glyphen
(Tavmjong Bah); freie Weitergabe mit Lizenztext erlaubt. Vollständiger Text: `LICENSE`.

## Aktualisieren

Archiv der gewünschten Version herunterladen, SHA-256 prüfen, die vier `DejaVuSans*.ttf`
sowie `LICENSE` ersetzen und diese Datei (Version, URLs, Prüfsummen, Datum) anpassen.
`tests/test_pdf_fonts.py` prüft die Prüfsummen gegen diese Tabelle.
