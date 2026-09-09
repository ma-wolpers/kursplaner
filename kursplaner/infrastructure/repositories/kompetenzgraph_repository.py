from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

from kursplaner.core.config.path_store import resolve_fachinhalte_root
from kursplaner.core.domain.kompetenzgraph_bereich_mapping import parse_bereich_node_from_raw
from kursplaner.core.domain.kompetenzgraph_diagnostics import KompetenzFieldIssue, KompetenzFileDiagnostic
from kursplaner.core.domain.kompetenzgraph_mapping import parse_kompetenz_node_from_raw
from kursplaner.core.domain.kompetenzgraph_node import BereichNode, KompetenzNode
from kursplaner.core.domain.kompetenzgraph_snapshot import KompetenzGraphSnapshot
from kursplaner.core.domain.kompetenzgraph_snapshot_builder import build_kompetenz_graph_snapshot
from kursplaner.core.domain.kompetenzgraph_types import SourceRef
from kursplaner.core.domain.yaml_registry import body_after_frontmatter
from kursplaner.infrastructure.repositories.kompetenzgraph_repository_cache import (
    CachedFileEntry,
    load_cache_from_disk,
    save_cache_to_disk,
)

try:
    import yaml  # type: ignore[import-untyped]

    KOMPETENZGRAPH_YAML_AVAILABLE = True
except ImportError:
    KOMPETENZGRAPH_YAML_AVAILABLE = False
"""`PyYAML` ist optional (siehe Mini-ADR `docs/ARCHITEKTUR_KERN.md` §29) -- fehlt
es, bleibt diese Klasse importierbar (fuer `wiring.py`), darf aber nicht
instanziiert werden. Die Verfuegbarkeitspruefung liegt bei der Composition
Root (`wiring.py`), nicht hier -- exakt das bei `ExpectedHorizonPdfRenderer`/
`REPORTLAB_AVAILABLE` etablierte Muster."""

_NODE_ID_PATTERN = re.compile(r"^[A-Z]{2,3}-\d+$")
_SYNC_CONFLICT_MARKER = ".sync-conflict-"
_BEREICHE_SUBFOLDER_NAME = "Bereiche"


def _scan_node_files(subject_dir: Path) -> list[Path]:
    """Scannt Kompetenz-Dateien FLACH direkt in `subject_dir` (kein `rglob`, keine Unterordner).

    Nur Dateien, deren Stem dem `<Kürzel>-<Nummer>`-Muster entspricht,
    gelten als Kompetenz-Knoten -- `Bereiche/`, `Schulcurricula/`,
    `Unsortiert/`, `_Import-Scratch/`, `_Schema.md` etc. werden dadurch
    implizit nie betreten/gematcht. `.sync-conflict-*`-Duplikate eines
    externen Sync-Programms werden ausgeschlossen.
    """
    if not subject_dir.is_dir():
        return []
    return sorted(
        child
        for child in subject_dir.iterdir()
        if child.is_file()
        and child.suffix.lower() == ".md"
        and _SYNC_CONFLICT_MARKER not in child.name
        and _NODE_ID_PATTERN.match(child.stem)
    )


def _scan_bereich_files(subject_dir: Path) -> list[Path]:
    """Scannt Bereichs-Hub-Dateien flach im `Bereiche/`-Unterordner von `subject_dir`."""
    bereiche_dir = subject_dir / _BEREICHE_SUBFOLDER_NAME
    if not bereiche_dir.is_dir():
        return []
    return sorted(
        child
        for child in bereiche_dir.iterdir()
        if child.is_file() and child.suffix.lower() == ".md" and _SYNC_CONFLICT_MARKER not in child.name
    )


def _extract_frontmatter_text(raw_text: str) -> str | None:
    """Isoliert den rohen YAML-Text zwischen den beiden `---`-Marken (ohne die Marken selbst).

    Nutzt dieselbe Grenzerkennung wie `yaml_registry.py::body_after_frontmatter`
    (das stattdessen die andere Hälfte -- den Body -- liefert), da keine
    bestehende Funktion den reinen Frontmatter-Textblock isoliert
    zurückgibt. `None`, wenn kein gültiger Frontmatter-Block gefunden wird.
    """
    if not raw_text.startswith("---\n"):
        return None
    end = raw_text.find("\n---", 4)
    if end == -1:
        return None
    return raw_text[4:end]


def _unreadable_diagnostic(path: Path, node_id: str, error: Exception) -> KompetenzFileDiagnostic:
    """Baut die Diagnose für eine Datei, die beim Scan gar nicht erst gelesen/geparst werden konnte."""
    return KompetenzFileDiagnostic(
        source_path=path,
        node_id=node_id,
        issues=(KompetenzFieldIssue(field="<datei>", message=f"Datei nicht lesbar: {error}", severity="error"),),
    )


class FileSystemKompetenzGraphRepository:
    """Liest das Kompetenznetz aus dem Vault -- einziger Ort im Projekt mit `import yaml`.

    Implementiert `KompetenzGraphRepository` (`core/ports/repositories.py`).
    Scannt pro Fachordner flach (kein rekursiver Vollscan) und cached pro
    Datei über `mtime_ns` + `size` (siehe `kompetenzgraph_repository_cache.py`)
    -- der Cache ist reine Beschleunigung, niemals Wahrheitsquelle: ein
    beschädigter/versions-inkompatibler Cache wird wie leer behandelt, eine
    einzelne nicht lesbare Datei erzeugt nur eine Diagnose statt eines
    Abbruchs und bekommt keinen Cache-Eintrag (automatischer Retry beim
    nächsten Laden).
    """

    def __init__(self) -> None:
        """Initialisiert den In-Memory-Cache (lazy von der Festplatte geladen, siehe `_cache()`)."""
        self._cache_state: dict[str, CachedFileEntry] | None = None

    def _cache(self) -> dict[str, CachedFileEntry]:
        if self._cache_state is None:
            self._cache_state = load_cache_from_disk()
        return self._cache_state

    def _persist_cache(self) -> None:
        save_cache_to_disk(self._cache())

    @staticmethod
    def _mtime_ns(stat_result) -> int:
        return getattr(stat_result, "st_mtime_ns", int(stat_result.st_mtime * 1_000_000_000))

    def discover_structured_subjects(self, unterricht_dir: Path) -> tuple[str, ...]:
        """Siehe `KompetenzGraphRepository.discover_structured_subjects`."""
        fachinhalte_root = resolve_fachinhalte_root(unterricht_dir)
        if fachinhalte_root is None:
            return ()

        subjects: list[str] = []
        for child in fachinhalte_root.iterdir():
            if not child.is_dir():
                continue
            if not (child / _BEREICHE_SUBFOLDER_NAME).is_dir():
                continue
            if _scan_node_files(child):
                subjects.append(child.name)
        return tuple(sorted(subjects, key=str.lower))

    def _process_node_file(
        self, path: Path, *, subject: str, cache: dict[str, CachedFileEntry]
    ) -> tuple[KompetenzNode | None, KompetenzFileDiagnostic | None]:
        """Verarbeitet eine Kompetenz-Datei über den Cache -- Kern der Cache-Hit-/-Miss-Logik."""
        node_id = path.stem
        key = str(path)
        try:
            stat_result = path.stat()
        except OSError as error:
            cache.pop(key, None)
            return None, _unreadable_diagnostic(path, node_id, error)

        mtime_ns, size = self._mtime_ns(stat_result), stat_result.st_size
        cached = cache.get(key)
        if cached is not None and cached.kind == "node" and cached.mtime_ns == mtime_ns and cached.size == size:
            source = SourceRef(path=path, mtime_ns=mtime_ns, size=size, subject=subject)
            node, issues = parse_kompetenz_node_from_raw(
                cached.frontmatter or {}, "", node_id=node_id, source=source, title_override=cached.title
            )
            return node, (KompetenzFileDiagnostic(path, node_id, issues) if issues else None)

        try:
            raw_text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            cache.pop(key, None)
            return None, _unreadable_diagnostic(path, node_id, error)

        frontmatter_text = _extract_frontmatter_text(raw_text)
        if frontmatter_text is None:
            cache.pop(key, None)
            return None, KompetenzFileDiagnostic(
                path, node_id, (KompetenzFieldIssue("<frontmatter>", "Kein gültiger YAML-Frontmatter-Block gefunden.", "error"),)
            )

        try:
            frontmatter_raw = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as error:
            cache.pop(key, None)
            return None, KompetenzFileDiagnostic(
                path, node_id, (KompetenzFieldIssue("<frontmatter>", f"YAML-Syntaxfehler: {error}", "error"),)
            )

        if not isinstance(frontmatter_raw, dict):
            cache.pop(key, None)
            return None, KompetenzFileDiagnostic(
                path, node_id, (KompetenzFieldIssue("<frontmatter>", "Frontmatter ist kein Objekt.", "error"),)
            )

        body = body_after_frontmatter(raw_text)
        source = SourceRef(path=path, mtime_ns=mtime_ns, size=size, subject=subject)
        node, issues = parse_kompetenz_node_from_raw(frontmatter_raw, body, node_id=node_id, source=source)
        cache[key] = CachedFileEntry(
            mtime_ns=mtime_ns,
            size=size,
            kind="node",
            frontmatter=frontmatter_raw,
            body=None,
            title=node.title if node is not None else "",
        )
        return node, (KompetenzFileDiagnostic(path, node_id, issues) if issues else None)

    def _process_bereich_file(
        self, path: Path, *, subject: str, cache: dict[str, CachedFileEntry]
    ) -> tuple[BereichNode | None, KompetenzFileDiagnostic | None]:
        """Verarbeitet eine Bereichs-Hub-Datei über den Cache (Body bleibt eager gecacht, siehe `CachedFileEntry`)."""
        node_id = path.stem
        key = str(path)
        try:
            stat_result = path.stat()
        except OSError as error:
            cache.pop(key, None)
            return None, _unreadable_diagnostic(path, node_id, error)

        mtime_ns, size = self._mtime_ns(stat_result), stat_result.st_size
        cached = cache.get(key)
        if cached is not None and cached.kind == "bereich" and cached.mtime_ns == mtime_ns and cached.size == size:
            source = SourceRef(path=path, mtime_ns=mtime_ns, size=size, subject=subject)
            node, issues = parse_bereich_node_from_raw(cached.body or "", node_id=node_id, source=source)
            return node, (KompetenzFileDiagnostic(path, node_id, issues) if issues else None)

        try:
            raw_text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            cache.pop(key, None)
            return None, _unreadable_diagnostic(path, node_id, error)

        source = SourceRef(path=path, mtime_ns=mtime_ns, size=size, subject=subject)
        node, issues = parse_bereich_node_from_raw(raw_text, node_id=node_id, source=source)
        cache[key] = CachedFileEntry(mtime_ns=mtime_ns, size=size, kind="bereich", frontmatter=None, body=raw_text, title="")
        return node, (KompetenzFileDiagnostic(path, node_id, issues) if issues else None)

    def load_snapshot(
        self, unterricht_dir: Path, subject_folders: Sequence[str] | None = None
    ) -> tuple[KompetenzGraphSnapshot, tuple[KompetenzFileDiagnostic, ...], tuple[str, ...]]:
        """Siehe `KompetenzGraphRepository.load_snapshot`."""
        fachinhalte_root = resolve_fachinhalte_root(unterricht_dir)
        if fachinhalte_root is None:
            return build_kompetenz_graph_snapshot([], []), (), ()

        subjects_to_load = (
            tuple(subject_folders) if subject_folders is not None else self.discover_structured_subjects(unterricht_dir)
        )

        cache = self._cache()
        all_nodes: list[KompetenzNode] = []
        all_bereiche: list[BereichNode] = []
        diagnostics: list[KompetenzFileDiagnostic] = []

        for subject in subjects_to_load:
            subject_dir = fachinhalte_root / subject
            for path in _scan_node_files(subject_dir):
                node, diagnostic = self._process_node_file(path, subject=subject, cache=cache)
                if node is not None:
                    all_nodes.append(node)
                if diagnostic is not None:
                    diagnostics.append(diagnostic)
            for path in _scan_bereich_files(subject_dir):
                bereich, diagnostic = self._process_bereich_file(path, subject=subject, cache=cache)
                if bereich is not None:
                    all_bereiche.append(bereich)
                if diagnostic is not None:
                    diagnostics.append(diagnostic)

        self._persist_cache()
        snapshot = build_kompetenz_graph_snapshot(all_nodes, all_bereiche)
        return snapshot, tuple(diagnostics), subjects_to_load

    def rebuild_snapshot(
        self, unterricht_dir: Path, subject_folders: Sequence[str] | None = None
    ) -> tuple[KompetenzGraphSnapshot, tuple[KompetenzFileDiagnostic, ...], tuple[str, ...]]:
        """Siehe `KompetenzGraphRepository.rebuild_snapshot`."""
        self.invalidate_cache()
        return self.load_snapshot(unterricht_dir, subject_folders)

    def read_body(self, source_path: Path) -> str:
        """Siehe `KompetenzGraphRepository.read_body`."""
        raw_text = source_path.read_text(encoding="utf-8")
        return body_after_frontmatter(raw_text)

    def invalidate_cache(self, unterricht_dir: Path | None = None, subject_folder: str | None = None) -> None:
        """Siehe `KompetenzGraphRepository.invalidate_cache`.

        Ohne auflösbaren Fachordner (fehlendes `subject_folder` oder
        `unterricht_dir`) wird der gesamte Cache verworfen -- ein
        sicherer Standard, der nie einen inkonsistenten Teil-Zustand
        hinterlässt.
        """
        if subject_folder is None or unterricht_dir is None:
            self._cache_state = {}
            self._persist_cache()
            return

        fachinhalte_root = resolve_fachinhalte_root(unterricht_dir)
        if fachinhalte_root is None:
            self._cache_state = {}
            self._persist_cache()
            return

        subject_prefix = str((fachinhalte_root / subject_folder).resolve())
        self._cache_state = {
            path_str: entry for path_str, entry in self._cache().items() if not path_str.startswith(subject_prefix)
        }
        self._persist_cache()
