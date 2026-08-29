from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from kursplaner.core.config.path_store import infer_workspace_root_from_path
from kursplaner.core.domain.course_rhythm import RHYTHM_YAML_KEY, parse_rhythm
from kursplaner.core.domain.day_column import DayColumn
from kursplaner.core.domain.lesson_directory import is_valid_unterricht_link
from kursplaner.core.domain.lesson_yaml_policy import canonicalize_lesson_yaml
from kursplaner.core.domain.plan_table import LessonYamlData, PlanTableData
from kursplaner.core.domain.wiki_links import extract_wiki_link_target, strip_wiki_link
from kursplaner.core.ports.repositories import LessonRepository, PlanRepository, UbRepository
from kursplaner.core.usecases.ub_markdown_sections import parse_list_section


@dataclass(frozen=True)
class PlanDetailResult:
    """Ergebnis eines Detail-Ladevorgangs für eine Planungsdatei."""

    table: PlanTableData
    day_columns: list[DayColumn]


class MissingLessonYamlFrontmatterError(RuntimeError):
    """Signalisiert fehlendes YAML-Frontmatter in einer verlinkten Stunden-Datei."""

    def __init__(self, lesson_path: Path, details: str):
        """Initialisiert den Fehler mit betroffenem Pfad und Originaldetails."""
        self.lesson_path = lesson_path
        super().__init__(details)


class LoadPlanDetailUseCase:
    """Lädt Planungstabelle und bereitet UI-unabhängige Tages-Spalten auf.

    Der Use Case ist read-only: fehlende YAML-Felder werden nur in-memory ergänzt,
    ohne persistente Schreibnebenwirkung im Ladepfad.
    """

    def __init__(
        self,
        plan_repo: PlanRepository,
        lesson_repo: LessonRepository,
        ub_repo: UbRepository | None = None,
    ):
        """Initialisiert den Use Case mit Plan- und Lesson-Repository-Port."""
        self.plan_repo = plan_repo
        self.lesson_repo = lesson_repo
        self.ub_repo = ub_repo

    def _load_ub_development_lists(self, *, workspace_root: Path, ub_link_stem: str) -> tuple[list[str], list[str]]:
        """Lädt UB-Listenfelder aus der UB-Markdown-Datei, falls vorhanden."""
        if self.ub_repo is None:
            return [], []
        stem = strip_wiki_link(str(ub_link_stem).strip())
        if not stem:
            return [], []
        ub_path = self.ub_repo.ensure_ub_root(workspace_root) / f"{stem}.md"
        if not ub_path.exists() or not ub_path.is_file():
            return [], []
        try:
            _, body = self.ub_repo.load_ub_markdown(ub_path)
        except Exception:
            return [], []
        return (
            parse_list_section(body, "Professionalisierungsschritte"),
            parse_list_section(body, "Nutzbare Ressourcen"),
        )

    @staticmethod
    def _workspace_root_from_table(table: PlanTableData) -> Path:
        return infer_workspace_root_from_path(table.markdown_path)

    @staticmethod
    def _extract_markdown_link_target(text: str) -> str:
        """Extrahiert das sichtbare Linkziel (Alias bevorzugt) aus `[[...]]`."""
        match = re.search(r"\[\[([^\]]+)\]\]", text)
        if not match:
            return ""
        target = match.group(1).strip()
        if "|" in target:
            left, right = target.split("|", 1)
            return right.strip() or left.strip()
        return target

    @classmethod
    def _header_content_label(cls, inhalt: str) -> tuple[str, bool]:
        """Leitet Headertext ab und kennzeichnet, ob er aus einem Link stammt."""
        raw = str(inhalt).strip()
        if not raw:
            return "—", False
        link_target = cls._extract_markdown_link_target(raw)
        if link_target:
            return link_target, True
        return raw, False

    def _ensure_valid_lesson_yaml(self, lesson_path: Path, topic: str) -> LessonYamlData:
        """Lädt und validiert YAML einer Stunden-Datei und ergänzt fehlende Keys.

        Bei komplett fehlendem Frontmatter wird kein stilles Auto-Fix ausgeführt,
        sondern ein gezielter `MissingLessonYamlFrontmatterError` ausgelöst,
        damit die GUI eine Nutzerentscheidung zur Art-Auswahl anbieten kann.

        Für vorhandenes Frontmatter ergänzt der Use Case fehlende Schlüssel nur
        in-memory und gibt ein normiertes `LessonYamlData` zurück.
        """
        try:
            lesson = self.lesson_repo.load_lesson_yaml(lesson_path)
        except Exception as exc:
            error_text = str(exc)
            if "Fehlendes YAML-Frontmatter" in error_text:
                raise MissingLessonYamlFrontmatterError(lesson_path, error_text) from exc
            raise

        merged_data = canonicalize_lesson_yaml(
            lesson.data if isinstance(lesson.data, dict) else {},
            topic_hint=topic,
        )

        topic_now = str(merged_data.get("Stundenthema", "")).strip()
        if not topic_now and topic.strip():
            merged_data["Stundenthema"] = topic.strip()

        return LessonYamlData(lesson_path=lesson.lesson_path, data=merged_data)

    def execute(self, markdown_path: Path) -> PlanDetailResult:
        """Lädt Tabelle und erzeugt Spalten-Daten für die Detailansicht."""
        table = self.plan_repo.load_plan_table(markdown_path)
        return PlanDetailResult(table=table, day_columns=self.build_day_columns(table))

    def _header_indices(self, table: PlanTableData) -> tuple[int, int, int | None]:
        """Liest die Spaltenindizes von Datum/Inhalt/Thema-Ausfall aus den Tabellen-Headern."""
        header_map = {name.lower(): idx for idx, name in enumerate(table.headers)}
        return header_map.get("datum", 0), header_map.get("inhalt", 1), header_map.get("thema/ausfall")

    def _plan_level_context(self, table: PlanTableData) -> tuple[str, tuple]:
        """Leitet die planweiten (nicht pro-Zeile variierenden) Baukontext-Werte ab."""
        group_name = strip_wiki_link(str(table.metadata.get("Lerngruppe", "")))
        rhythm = parse_rhythm(table.metadata.get(RHYTHM_YAML_KEY, []))
        return group_name, rhythm

    def _build_one_day_column(
        self,
        table: PlanTableData,
        row_index: int,
        *,
        idx_datum: int,
        idx_inhalt: int,
        idx_thema_ausfall: int | None,
        group_name: str,
        rhythm: tuple,
    ) -> DayColumn:
        """Baut EIN `DayColumn` für genau eine Planzeile (I/O-Orchestrierung, gemeinsamer

        Helfer für :meth:`build_day_columns` und :meth:`build_day_columns_incremental` —
        beide Pfade müssen dieselbe Zeilen-Konstruktionslogik verwenden, damit ein
        vollständiger Rebuild und ein Einzelzeilen-Patch niemals auseinanderlaufen.
        Liest den verlinkten Stunden-YAML tatsächlich von der Festplatte (der
        eigentliche I/O-Kern dieses Use Cases); ruft `row_index`, um kein
        `DayColumn` unabsichtlich mit dem falschen Index zu bauen.
        """
        row = table.rows[row_index]
        datum = row[idx_datum] if idx_datum < len(row) else ""
        inhalt = row[idx_inhalt] if idx_inhalt < len(row) else ""
        thema_ausfall = (
            row[idx_thema_ausfall] if idx_thema_ausfall is not None and idx_thema_ausfall < len(row) else ""
        )

        link = self.lesson_repo.resolve_row_link_path(table, row_index)
        link_target = extract_wiki_link_target(inhalt)

        yaml_data: dict[str, object] = {}
        if is_valid_unterricht_link(link) and isinstance(link, Path):
            extracted_topic = link_target
            split = link_target.split(" ", 1)
            if len(split) == 2:
                extracted_topic = split[1].strip() or link_target
            lesson = self._ensure_valid_lesson_yaml(link, topic=extracted_topic)
            yaml_data = lesson.data if isinstance(lesson.data, dict) else {}
            ub_link = str(yaml_data.get("Unterrichtsbesuch", "")).strip()
            if ub_link:
                steps, resources = self._load_ub_development_lists(
                    workspace_root=self._workspace_root_from_table(table),
                    ub_link_stem=ub_link,
                )
                yaml_data = dict(yaml_data)
                yaml_data["Professionalisierungsschritte"] = steps
                yaml_data["Nutzbare Ressourcen"] = resources

        return DayColumn(
            row_index=row_index,
            datum=datum,
            inhalt=inhalt,
            thema_ausfall=thema_ausfall,
            link=link,
            yaml=yaml_data,
            group_name=group_name,
            rhythm=rhythm,
        )

    def build_day_columns(self, table: PlanTableData) -> list[DayColumn]:
        """Erzeugt `DayColumn`-Objekte inkl. geladener YAML-Daten für JEDE Planzeile.

        Reine I/O-Orchestrierung: löst Links auf, lädt/kanonisiert YAML
        verlinkter Stunden-Dateien (inkl. UB-Entwicklungslisten) und baut
        daraus ein `DayColumn` je Zeile — über `_build_one_day_column()`, den
        gemeinsamen Helfer mit `build_day_columns_incremental()`. Alle
        fachlichen Ableitungen (Ausfall-/Hospitation-/Unterricht-/LZK-
        Erkennung, Stunden/Startzeit aus dem Rhythmus, Kopfzeilentext,
        Oberthema, …) leben als Methoden auf `DayColumn` selbst
        (`core.domain.day_column`), nicht hier.

        Liest aus dem 3-Spalten-Format (Datum | Inhalt | Thema/Ausfall):
        - Inhalt (col 1): Wiki-Link zur Stundendatei oder leer
        - Thema/Ausfall (col 2): ``X Grund`` für Ausfall, ``X Grund X`` für
          Ferien/Feiertag, ``[[gruppe thema]]`` für Unterricht/Hospitation,
          ``LZK [[...]]`` für LZK, sonst leer

        Jedes `DayColumn` trägt den kompletten geparsten `Rhythmus` (nicht
        nur den für seine Zeile relevanten Ausschnitt) — `DayColumn.stunden()`/
        `startzeit()` lösen live gegen ihr eigenes `datum` auf.

        Teuer bei großen Plänen: liest für JEDE verlinkte Zeile die YAML-Datei
        neu von der Festplatte, auch wenn sich nur eine einzige Zeile geändert
        hat. Für den Hot Path "eine Zelle bearbeiten" `build_day_columns_incremental()`
        verwenden, das nur die tatsächlich betroffene(n) Zeile(n) neu liest.
        """
        idx_datum, idx_inhalt, idx_thema_ausfall = self._header_indices(table)
        group_name, rhythm = self._plan_level_context(table)

        return [
            self._build_one_day_column(
                table,
                row_index,
                idx_datum=idx_datum,
                idx_inhalt=idx_inhalt,
                idx_thema_ausfall=idx_thema_ausfall,
                group_name=group_name,
                rhythm=rhythm,
            )
            for row_index in range(len(table.rows))
        ]

    def build_day_columns_incremental(
        self,
        table: PlanTableData,
        previous_day_columns: list[DayColumn] | None,
        changed_row_indices: set[int],
    ) -> list[DayColumn]:
        """Baut `DayColumn`-Objekte, liest aber nur für tatsächlich geänderte Zeilen neu.

        Primärfix des Performance-Problems "eine Zellbearbeitung liest den
        gesamten Plan neu ein" (statt nur die Ursache mit einem Cache zu
        kaschieren): unveränderte Zeilen bekommen ihr bisheriges `DayColumn`-
        Objekt zurück (sicher wiederverwendbar, da `DayColumn` per Konvention
        ein unveränderlicher Snapshot ist, der bei jeder Datenänderung ohnehin
        neu gebaut wird — s. `DayColumn`-Klassendocstring) statt eines
        erneuten Festplatten-Lesevorgangs. Nutzt exakt denselben
        Zeilen-Konstruktionshelfer (`_build_one_day_column`) wie
        `build_day_columns()` für tatsächlich neu zu bauende Zeilen — keine
        zweite, potenziell auseinanderlaufende Bau-Logik.

        Fällt auf einen vollständigen `build_day_columns()`-Aufruf zurück,
        sobald eine der Sicherheitsannahmen nicht zutrifft (kein vorheriger
        Stand, andere Zeilenanzahl, geänderte Lerngruppe/Rhythmus) — lieber
        einmal zu viel neu lesen als eine strukturelle Änderung übersehen.

        Behandelt zusätzlich den Randfall "mehrere Zeilen verlinken dieselbe
        Datei" (von `FileSystemLessonRepository.load_lessons_for_rows()` an
        anderer Stelle bereits als möglich behandelt): jede Zeile, deren
        aufgelöster Link-Pfad mit dem alten ODER neuen Link-Pfad einer
        geänderten Zeile übereinstimmt, wird ebenfalls neu gebaut statt aus
        dem alten Bestand übernommen.

        Args:
            table: Aktuell geladene Planungstabelle.
            previous_day_columns: Zuvor gebaute `DayColumn`-Liste (`app.raw_day_columns`),
                oder ``None``, wenn noch keine existiert.
            changed_row_indices: Zeilenindizes, die seit `previous_day_columns`
                tatsächlich editiert wurden (typischerweise eine einzelne Zeile).

        Returns:
            Vollständige `DayColumn`-Liste für `table`, teils wiederverwendet,
            teils frisch gebaut.
        """
        idx_datum, idx_inhalt, idx_thema_ausfall = self._header_indices(table)
        group_name, rhythm = self._plan_level_context(table)

        def _full_rebuild() -> list[DayColumn]:
            return [
                self._build_one_day_column(
                    table,
                    row_index,
                    idx_datum=idx_datum,
                    idx_inhalt=idx_inhalt,
                    idx_thema_ausfall=idx_thema_ausfall,
                    group_name=group_name,
                    rhythm=rhythm,
                )
                for row_index in range(len(table.rows))
            ]

        if previous_day_columns is None or len(previous_day_columns) != len(table.rows):
            return _full_rebuild()
        if previous_day_columns and (
            previous_day_columns[0].group_name != group_name or previous_day_columns[0].rhythm != rhythm
        ):
            return _full_rebuild()
        for idx in changed_row_indices:
            if not (0 <= idx < len(previous_day_columns)):
                return _full_rebuild()

        if not changed_row_indices:
            # Nichts geändert (Aufrufer behauptet keine Edits) -- der gesamte
            # vorherige Bestand bleibt gültig, kein Rebuild und schon gar kein
            # Festplatten-Zugriff nötig. Eigener Zweig statt still im
            # allgemeinen Pfad mitzulaufen: dirty_paths bliebe sonst leer und
            # jede Zeile würde denselben (überflüssigen) resolve_row_link_path()-
            # Aufruf durchlaufen wie im "es gibt geänderte Zeilen"-Fall.
            return list(previous_day_columns)

        dirty_paths: set[Path] = set()
        for idx in changed_row_indices:
            old_link = previous_day_columns[idx].link
            if isinstance(old_link, Path):
                dirty_paths.add(old_link.resolve())
            new_link = self.lesson_repo.resolve_row_link_path(table, idx)
            if isinstance(new_link, Path):
                dirty_paths.add(new_link.resolve())

        collected: list[DayColumn] = []
        for row_index in range(len(table.rows)):
            needs_rebuild = row_index in changed_row_indices
            if not needs_rebuild and dirty_paths:
                current_link = self.lesson_repo.resolve_row_link_path(table, row_index)
                if isinstance(current_link, Path) and current_link.resolve() in dirty_paths:
                    needs_rebuild = True

            if needs_rebuild:
                collected.append(
                    self._build_one_day_column(
                        table,
                        row_index,
                        idx_datum=idx_datum,
                        idx_inhalt=idx_inhalt,
                        idx_thema_ausfall=idx_thema_ausfall,
                        group_name=group_name,
                        rhythm=rhythm,
                    )
                )
            else:
                collected.append(previous_day_columns[row_index])

        return collected
