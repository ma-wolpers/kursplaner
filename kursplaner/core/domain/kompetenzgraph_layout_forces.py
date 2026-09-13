from __future__ import annotations

from collections.abc import Mapping

_DEFAULT_ITERATIONS = 6
"""Feste Sweep-Anzahl -- reines Performance-Budget, kein Determinismus-Selbstzweck
(siehe Modul-Docstring: bitgenaue Koordinaten-Reproduzierbarkeit über verschiedene
Layout-Läufe hinweg ist ausdrücklich KEIN Ziel dieses Moduls)."""

MAX_NODES_FOR_RELAXATION = 2000
"""Performance-Budget (technische Grenze, KEINE fachliche): oberhalb dieser sichtbaren Knotenzahl
ruft `kompetenzgraph_layout.py` `relax_horizontal_positions()` mit `iterations=0` auf -- es bleibt
bei den reinen Slot-Index-Startpositionen. In der Praxis unkritisch, da Filter/Fokus/Matchingtiefe
die sichtbare Menge im Normalfall klein halten; verhindert aber, dass ein sehr großes, künftig
fachübergreifendes Vault die Relaxation unbegrenzt verlängert."""

_WEAK_BEREICH_COHESION_WEIGHT = 0.15
"""Blend-Gewicht Richtung Bereichs-Anker (siehe `_apply_bereich_cohesion()`) für einen Knoten MIT
mindestens einem sichtbaren Hierarchie-Nachbarn (Elternteil oder Kind) in der aktuellen Ansicht.

Bewusst klein: ein solcher Knoten hat ein echtes, fachlich bedeutsames Hierarchie-Ziel, das die
Bereichs-Kraft nicht dominieren darf."""

_STRONG_BEREICH_COHESION_WEIGHT = 0.8
"""Blend-Gewicht Richtung Bereichs-Anker für einen Knoten OHNE jeden sichtbaren Hierarchie-Nachbarn
-- unabhängig davon, ob sein Bereich viele oder nur einen weiteren sichtbaren Peer hat (beides
läuft über denselben, einmalig fixierten Anker, siehe `_estimate_bereich_anchor_positions()`).
Bewusst an der Hierarchie-Nachbarschaft festgemacht, nicht an der Gruppengröße: ein gut
bevölkerter Bereich hätte bei einer größenabhängigen Gewichtung für jedes Mitglied denselben
(zwangsläufig schwachen) Wert -- ein reiner Filter-Waise ohne jedes Hierarchie-Signal braucht aber
denselben starken Zug wie jeder andere Knoten ohne Hierarchie-Signal, unabhängig von der Größe
seines Bereichs. Es gibt hier nichts fachlich Schützenswertes, das ein schwaches Gewicht
rechtfertigen würde.

**Wichtige Architektur-Entscheidung (Konvergenz-bedingt):** Das Bereichs-Ziel ist für JEDEN Knoten
ein EINMALIG vor der Sweep-Schleife aus den Start-Positionen berechneter, danach FIXER Wert -- nie
ein live pro Sweep neu berechneter Mittelwert bewegter Peers. Ein früherer Entwurf blendete
stattdessen Richtung eines live aktualisierten Gruppen-Mittelwerts (Peer zieht zu seinen ebenfalls
sich bewegenden anderen Peers). Das erwies sich beim Durchrechnen konkreter Szenarien als ECHT
INSTABIL, sobald ein Gruppenmitglied ZUGLEICH einen Hierarchie-Nachbarn außerhalb der Gruppe hatte
-- unabhängig von der Gruppengröße (auch mit 5 echten Peers reproduziert, nicht nur im
degenerierten 1-Peer-Fall): die Kopplung aus (a) Hierarchie-Pull zwischen diesem Mitglied und
seinem externen Nachbarn und (b) Bereichs-Pull zwischen den Gruppenmitgliedern erzeugte eine
Übergangsmatrix mit Eigenwert exakt `1.0` -- keine Konvergenz, sondern unbegrenzter linearer Drift
der GESAMTEN Gruppe plus des externen Nachbarn relativ zum Rest des Graphen (verifiziert über 200+
Sweeps, kein Abklingen; ein unbeteiligter Kontrollknoten in derselben Schicht blieb exakt an seiner
Startposition stehen, während sich der Abstand zu ihm unbegrenzt vergrößerte). Ursache im Detail:
sobald die live-blendeten Ziele zweier Gruppenmitglieder näher beieinander liegen als
`min_spacing`, muss `_resolve_min_spacing()` sie künstlich auseinanderziehen; die dabei
entstehende systematische Verschiebung (wer landet "links", wer "rechts") speist sich über den
externen Hierarchie-Nachbarn in die NÄCHSTE Sweep-Berechnung zurück und akkumuliert sich Sweep für
Sweep, statt sich auszugleichen -- dieselbe Fehlerklasse wie die beiden bereits dokumentierten
historischen Konvergenzfehler dieses Moduls (siehe DEVELOPMENT_LOG.md, 2026-09-11).

Erwogene Alternative, verworfen: eine schwache "Gravitation" jedes Knotens Richtung seiner EIGENEN
Startposition (statt Richtung anderer Knoten) würde das Eigenwert-1-Problem ebenfalls beheben
(empirisch verifiziert: konvergiert zu einem stabilen, endlichen Abstand statt unbegrenzt zu
driften). Verworfen, weil sie innerhalb des bestehenden Sweep-Budgets (`_DEFAULT_ITERATIONS = 6`)
nur bei einem Gewicht stark genug konvergiert, das gleichzeitig JEDE legitime Hierarchie-/
Bereichs-Neupositionierung im GESAMTEN Graphen spürbar abbremst -- ein globaler Tarif auf jede
Bewegung, um ein lokal begrenztes Problem zu lösen. Der fixe Anker erreicht dieselbe Stabilität
gezielt nur dort, wo sie gebraucht wird, und konvergiert dabei schon fast vollständig innerhalb
der bestehenden 6 Sweeps (keine Sweep-Budget-Erhöhung, kein zusätzlicher globaler Mechanismus
nötig).

Mit einem FIXEN Anker (Konstante, hängt nie von sich änderenden Positionen ab) verschwindet das
Rückkopplungsrisiko strukturell: die Kopplung Hierarchie-Nachbar<->Knoten<->Bereichs-Anker wird zu
einer reinen AFFINEN Rekursion mit konstantem Störterm (`x_{t+1} = a*x_t + c`, `|a|<1`), die
nachweislich zu einem stabilen Fixpunkt konvergiert (`x* = c/(1-a)`), unabhängig davon, was sonst
noch mit dem Anker-Wert verbunden ist -- er ändert sich während der gesamten Relaxation nie."""


def _median(values: list[float]) -> float:
    """Median einer nichtleeren Werteliste -- robuster gegen Ausreißer als der Mittelwert."""
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _mean(values: list[float]) -> float:
    """Arithmetisches Mittel einer nichtleeren Werteliste."""
    return sum(values) / len(values)


def _pull_toward_neighbor_median(
    node_ids: tuple[str, ...],
    positions: Mapping[str, float],
    neighbor_map: Mapping[str, tuple[str, ...]],
) -> dict[str, float]:
    """Berechnet je Knoten die Ziel-X-Position als Median ALLER seiner tatsächlichen Nachbarn (`neighbor_map`).

    Bewusst NICHT auf eine bestimmte Nachbarschicht beschränkt: Beim
    longest-path-Layering (`layer(kind) = 1 + max(layer(eltern))`) landen
    zwei direkte Eltern eines Knotens regelmäßig in UNTERSCHIEDLICHEN
    Schichten (der Elternteil mit der tieferen Kette bestimmt die Schicht
    des Kindes, ein anderer Elternteil kann beliebig viele Schichten
    höher liegen). Eine Beschränkung auf die unmittelbar benachbarte
    Schicht würde solche Eltern/Kinder ignorieren und zu falschem
    Kräfteungleichgewicht führen.

    Ein Knoten ohne jede Verbindung behält seine bisherige Position
    (`positions[node_id]`) statt an eine willkürliche Stelle zu springen.
    """
    targets: dict[str, float] = {}
    for node_id in node_ids:
        neighbor_positions = [positions[neighbor] for neighbor in neighbor_map.get(node_id, ()) if neighbor in positions]
        targets[node_id] = _median(neighbor_positions) if neighbor_positions else positions[node_id]
    return targets


def _estimate_bereich_anchor_positions(
    bereich_of_node: Mapping[str, str], initial_positions: Mapping[str, float]
) -> dict[str, float]:
    """Fixes Anker-Ziel PRO KNOTEN (nicht pro Bereich), EINMALIG aus den Start-Positionen berechnet
    -- ausschließlich aus `primarer_bereich_id`-Mitgliedern, unter Ausschluss des Knotens selbst
    (Mittelwert der ANDEREN sichtbaren Mitglieder desselben Bereichs). NICHT der offizielle,
    angezeigte Bereichs-Hub (das ist `compute_bereich_centroid_positions()`, läuft NACH der
    Relaxation, berücksichtigt primär+prozess für einen unabhängigen Zweck: die
    Hub-Zeilen-Positionierung). Dient als Ziel für JEDEN Knoten mit `primarer_bereich_id` während
    der Relaxation, siehe `_apply_bereich_cohesion()`.

    Ein Knoten, der die EINZIGE jemals sichtbare Kompetenz seines Bereichs ist, bekommt bewusst
    KEINEN Eintrag -- es gibt niemanden außer ihm selbst, zu dem er gezogen werden könnte.
    `_apply_bereich_cohesion()` fällt für ihn auf das reine Hierarchie-Ziel zurück. OHNE diesen
    Selbst-Ausschluss würde ein Knoten mit hohem Gewicht zu SEINER EIGENEN arbiträren
    Slot-Index-Startposition zurückgezogen -- exakt das Problem, das diese Kraft eigentlich
    beheben soll.

    Bewusst EINMALIG statt pro Sweep neu berechnet: ein sich mitbewegender, live aus den aktuellen
    Positionen abgeleiteter Anker (Peer zieht zu seinen ebenfalls sich bewegenden anderen Peers)
    erwies sich beim Durchrechnen konkreter Szenarien als instabil -- siehe
    `_STRONG_BEREICH_COHESION_WEIGHT`-Docstring für die vollständige Herleitung des dabei
    gefundenen, unbegrenzten Drifts und warum ein FIXER Anker ihn strukturell ausschließt.
    """
    sums: dict[str, list[float]] = {}
    for node_id, bereich_id in bereich_of_node.items():
        sums.setdefault(bereich_id, []).append(initial_positions[node_id])
    bereich_sum_count = {bereich_id: (sum(values), len(values)) for bereich_id, values in sums.items()}

    anchor_by_node: dict[str, float] = {}
    for node_id, bereich_id in bereich_of_node.items():
        total, count = bereich_sum_count[bereich_id]
        if count >= 2:
            anchor_by_node[node_id] = (total - initial_positions[node_id]) / (count - 1)
    return anchor_by_node


def _apply_bereich_cohesion(
    node_ids: tuple[str, ...],
    hierarchy_targets: Mapping[str, float],
    bereich_of_node: Mapping[str, str],
    bereich_anchor_positions: Mapping[str, float],
    has_hierarchy_neighbor: Mapping[str, bool],
) -> dict[str, float]:
    """Blendet die bereits berechneten Hierarchie-Ziele mit einem FIXEN Primärbereich-Anker.

    Zwei UNABHÄNGIGE Entscheidungen (siehe auch Modul-Docstring der beiden Gewichts-Konstanten):

    1. **Gibt es ein Bereichs-Ziel?** Ja, falls der Knoten `primarer_bereich_id` hat UND
       `_estimate_bereich_anchor_positions()` für ihn einen Anker berechnen konnte (mindestens
       ein weiterer sichtbarer Knoten desselben Bereichs existiert). Sonst: KEIN Bereichs-Ziel,
       reines Hierarchie-Ziel unverändert.
    2. **Wie stark?** (nur relevant, wenn 1. zutrifft)
       - Hat der Knoten mindestens einen sichtbaren Hierarchie-Nachbarn: `_WEAK_BEREICH_COHESION_
         WEIGHT` -- ein echtes Hierarchie-Ziel wird nur sanft ergänzt, nicht verdrängt.
       - Kein Hierarchie-Nachbar: `_STRONG_BEREICH_COHESION_WEIGHT` -- es gibt kein fachliches
         Signal, das geschützt werden müsste.

    `prozessbereiche` fließen in KEINEN Teil dieser Funktion ein -- `bereich_of_node` enthält
    ausschließlich `primarer_bereich_id`-Zuordnungen (siehe Aufrufstelle in
    `kompetenzgraph_layout.py`).
    """
    blended: dict[str, float] = {}
    for node_id in node_ids:
        hierarchy_target = hierarchy_targets[node_id]
        if bereich_of_node.get(node_id) is None or node_id not in bereich_anchor_positions:
            blended[node_id] = hierarchy_target
            continue
        weight = (
            _WEAK_BEREICH_COHESION_WEIGHT if has_hierarchy_neighbor.get(node_id, False) else _STRONG_BEREICH_COHESION_WEIGHT
        )
        anchor = bereich_anchor_positions[node_id]
        blended[node_id] = (1 - weight) * hierarchy_target + weight * anchor
    return blended


def _resolve_min_spacing(node_ids: tuple[str, ...], target_x: Mapping[str, float], min_spacing: float) -> dict[str, float]:
    """Positioniert `node_ids` so nah wie möglich an `target_x`, unter Einhaltung von `min_spacing`.

    `node_ids` muss bereits nach `target_x` aufsteigend sortiert sein (siehe
    `relax_horizontal_positions()`/`compute_bereich_centroid_positions()`
    -- beide sortieren ihre Eingabe genau deshalb VOR diesem Aufruf; das
    allein verhindert bereits große künstliche Lücken zu fernen,
    unbeteiligten Knoten, siehe Modul-Docstring von
    `relax_horizontal_positions()`).

    Für die verbleibende Aufgabe -- ECHTE Konflikte zwischen benachbarten,
    zu nah beieinanderliegenden (oder identischen) Zielen auflösen -- reicht
    ein simpler "nur nach rechts schieben"-Sweep NICHT aus: er behandelt
    Gleichstände einseitig (der erste Knoten behält sein Ziel exakt, jeder
    Folgeknoten wird stur um `min_spacing` weitergeschoben). Bei einer
    Rückkopplung -- z. B. zwei Elternteile, die denselben Kindknoten
    anziehen, der wiederum beide Elternteile anzieht -- verschiebt das den
    Schwerpunkt bei jedem Sweep-Paar unwiderruflich weiter (empirisch per
    Iterations-Stabilitätstest gefunden: nach 20 Sweeps bereits ein
    Vielfaches der Startposition, statt zu konvergieren).

    Stattdessen wird eine transformierte **isotonische Regression** (Pool-
    Adjacent-Violators-Algorithmus, PAVA) verwendet: `y_i = ziel_i - i *
    min_spacing` macht "Mindestabstand einhalten" äquivalent zu "y muss
    monoton nicht-fallend sein"; PAVA liefert dazu die (im Sinne der
    kleinsten quadratischen Abweichung) nächstgelegene nicht-fallende
    Folge. Im Konfliktfall bekommt eine ganze Gruppe im Konflikt stehender
    Knoten den MITTELWERT ihrer Ziele -- symmetrisch, nicht einseitig --
    wodurch sich ein Rückkopplungs-Schwerpunkt stabil einpendelt statt zu
    driften (siehe `test_more_iterations_stabilize_instead_of_drifting_further`).
    """
    if not node_ids:
        return {}
    targets = [target_x[node_id] for node_id in node_ids]
    offsets = [targets[i] - i * min_spacing for i in range(len(targets))]
    fitted = _isotonic_regression(offsets)
    return {node_ids[i]: fitted[i] + i * min_spacing for i in range(len(node_ids))}


def _isotonic_regression(values: list[float]) -> list[float]:
    """Pool-Adjacent-Violators-Algorithmus (PAVA), O(n) amortisiert.

    Liefert die nicht-fallende Folge mit der kleinsten Summe quadrierter
    Abweichungen von `values`. Klassischer Stack-Algorithmus: verletzt ein
    neuer Wert die Monotonie gegenüber dem letzten Block (sein Mittelwert
    wäre kleiner als der des Vorgänger-Blocks), werden beide Blöcke zu
    einem gemeinsamen Block mit dem gemeinsamen Mittelwert verschmolzen --
    wiederholt, bis die Monotonie wiederhergestellt ist.
    """
    blocks: list[list[float]] = []  # je Block: [Summe, Anzahl, Mittelwert]
    for value in values:
        block_sum, block_count = value, 1.0
        while blocks and blocks[-1][2] > block_sum / block_count:
            previous_sum, previous_count, _ = blocks.pop()
            block_sum += previous_sum
            block_count += previous_count
        blocks.append([block_sum, block_count, block_sum / block_count])
    result: list[float] = []
    for _block_sum, block_count, average in blocks:
        result.extend([average] * int(block_count))
    return result


def relax_horizontal_positions(
    sorted_layers: Mapping[int, tuple[str, ...]],
    edges: Mapping[str, tuple[str, ...]],
    *,
    iterations: int = _DEFAULT_ITERATIONS,
    min_spacing: float = 170.0,
    bereich_of_node: Mapping[str, str] | None = None,
) -> dict[str, float]:
    """Positioniert Knoten nahe am Median ihrer verbundenen Nachbarn -- Reihenfolge folgt den Kräften.

    Pipeline pro Sweep: (1) Kräfte-Ziel je Knoten berechnen
    (`_pull_toward_neighbor_median`), (2) die Schicht NACH DIESEM ZIEL neu
    sortieren (Tie-Break: Knoten-ID), (3) Mindestabstand auf die so
    entstandene Reihenfolge anwenden (`_resolve_min_spacing`). Abwechselnd
    Top-Down- (Richtung Eltern) und Bottom-Up-Sweeps (Richtung Kinder).

    **Bewusste Architekturentscheidung:** Die Schicht-Reihenfolge ist KEIN
    eigener Optimierungsgegenstand mehr und wird nicht von außen
    vorgegeben/fixiert -- `sorted_layers` liefert nur die Sweep-0-
    Startreihenfolge (z. B. nach `(primarer_bereich_id, id)`), sie darf sich
    über die Sweeps hinweg beliebig ändern. Grund: eine von einem
    FACHFREMDEN Ziel (z. B. Crossing-Minimierung) vorgegebene, über den
    ganzen Lauf fixierte Reihenfolge zwingt eine Verträglichkeit zwischen
    zwei unabhängigen Zielen -- steht darin ein Knoten mit einem legitim
    weit entfernten Ziel vor einem unabhängigen Knoten mit kleinem Ziel,
    wurde Letzterer früher stur auf "Vorgänger + Mindestabstand" gezwungen,
    unabhängig von der Größe der Diskrepanz (das war die tatsächliche
    Ursache einer beobachteten Lücke von über 100.000px im echten Vault).
    Mit Sortierung nach Kräfte-Ziel kann das nicht mehr passieren: ein
    Ausreißer sortiert sich einfach dorthin ein, wo sein Ziel tatsächlich
    liegt, statt alles Nachfolgende in der alten Reihenfolge mitzuziehen.

    **Explizit in Kauf genommener Trade-off:** Kantenkreuzungen werden durch
    diese Positionierung NICHT mehr aktiv minimiert -- das ist ein visuelles,
    kein fachliches Problem (die tatsächliche Verbindung bleibt über Kante +
    sichtbaren Andockpunkt am Knotenrand erkennbar, siehe
    `kompetenzgraph_canvas_render.py`). Es besteht weiterhin KEIN Anspruch
    auf bitgenau reproduzierbare Koordinaten über mehrere separate Aufrufe
    hinweg (z. B. bei unterschiedlicher sichtbarer Knotenmenge); Determinismus
    gilt nur innerhalb eines einzelnen Aufrufs (reine Funktion, keine
    verdeckte Zufälligkeit oder externer Zustand).

    **Primärbereich-Kohäsion (optional, `bereich_of_node`):** löst das "Filterwaisen"-Problem --
    ein Knoten ohne jeden sichtbaren Hierarchie-Nachbarn (z. B. weil ein Filter seinen echten
    Elternteil oder alle Kinder entfernt hat) wird von `_pull_toward_neighbor_median()` sonst an
    seiner arbiträren Slot-Index-Startposition eingefroren, obwohl sein `primarer_bereich_id` eine
    fachlich sinnvolle Verankerung nahelegt. Ist `bereich_of_node` gesetzt, wird das je Sweep
    berechnete Hierarchie-Ziel zusätzlich mit einem FIXEN, einmalig aus den Start-Positionen
    berechneten Primärbereich-Anker geblendet -- siehe `_apply_bereich_cohesion()` für die
    vollständige Fallunterscheidung und `_STRONG_BEREICH_COHESION_WEIGHT` für die Begründung,
    warum der Anker fix statt live neu berechnet ist. Default `None` → bit-identisches Verhalten
    zu vorher für jeden bestehenden Aufrufer.

    Args:
        sorted_layers: Schicht-Index → Start-Reihenfolge dieser Schicht
            (dient nur als Sweep-0-Basis, keine über den Lauf fixierte Vorgabe).
        edges: Knoten-ID → Tupel der Eltern-IDs (Kind→Eltern-Richtung,
            wie von `ancestors_of()`/`kompetenzgraph_layout.py` geliefert;
            bewusst das VOLLE Kantenbild inkl. Rückkanten).
        iterations: Anzahl der Sweeps (Performance-Budget, siehe
            `MAX_NODES_FOR_RELAXATION`). `0` liefert reine
            Slot-Index-Startpositionen ohne Relaxation.
        min_spacing: Mindestabstand zwischen zwei benachbarten Knoten
            derselben Schicht.
        bereich_of_node: Optionale Knoten-ID → `primarer_bereich_id`-Zuordnung (NIEMALS
            `prozessbereiche`) für die Primärbereich-Kohäsion. `None` deaktiviert sie vollständig.

    Returns:
        Knoten-ID → berechnete X-Position (nur Hierarchie-Schichten, keine
        Bereichs-Hubs -- siehe `compute_bereich_centroid_positions` dafür).
    """
    layer_indices = sorted(sorted_layers)
    positions: dict[str, float] = {}
    current_order: dict[int, tuple[str, ...]] = {}
    for layer_index in layer_indices:
        current_order[layer_index] = tuple(sorted_layers[layer_index])
        for position_index, node_id in enumerate(current_order[layer_index]):
            positions[node_id] = position_index * min_spacing

    if len(layer_indices) < 2 or iterations <= 0:
        return positions

    children_of: dict[str, list[str]] = {}
    for node_id, parents in edges.items():
        for parent in parents:
            children_of.setdefault(parent, []).append(node_id)
    children_of_tuples = {parent: tuple(children) for parent, children in children_of.items()}

    bereich_anchor_positions: dict[str, float] = {}
    has_hierarchy_neighbor: dict[str, bool] = {}
    if bereich_of_node is not None:
        # Beide EINMALIG vor der Sweep-Schleife berechnet, danach FIX -- weder der Anker noch die
        # Hierarchie-Nachbarschaft eines Knotens ändern sich innerhalb eines Aufrufs (Sichtbarkeit
        # und Start-Positionen stehen fest; siehe `_estimate_bereich_anchor_positions()`-Docstring
        # dafür, warum ein LIVE pro Sweep neu berechneter Anker instabil wäre).
        bereich_anchor_positions = _estimate_bereich_anchor_positions(bereich_of_node, positions)
        has_hierarchy_neighbor = {
            node_id: bool(edges.get(node_id)) or bool(children_of_tuples.get(node_id)) for node_id in positions
        }

    for sweep_index in range(iterations):
        if sweep_index % 2 == 0:
            # Top-Down: Schichten aufsteigend, jeder Knoten wird Richtung des Medians ALLER
            # seiner Eltern gezogen (gleich welcher Schicht) -- Eltern liegen beim
            # longest-path-Layering immer in einer strikt kleineren Schicht und sind in
            # diesem Sweep bereits aktualisiert (Gauss-Seidel-Stil).
            for layer_index in layer_indices[1:]:
                targets = _pull_toward_neighbor_median(current_order[layer_index], positions, edges)
                if bereich_of_node is not None:
                    targets = _apply_bereich_cohesion(
                        current_order[layer_index], targets, bereich_of_node, bereich_anchor_positions, has_hierarchy_neighbor
                    )
                new_order = tuple(sorted(current_order[layer_index], key=lambda nid: (targets[nid], nid)))
                current_order[layer_index] = new_order
                positions.update(_resolve_min_spacing(new_order, targets, min_spacing))
        else:
            # Bottom-Up: Schichten absteigend, Richtung Median ALLER Kinder.
            for layer_index in reversed(layer_indices[:-1]):
                targets = _pull_toward_neighbor_median(current_order[layer_index], positions, children_of_tuples)
                if bereich_of_node is not None:
                    targets = _apply_bereich_cohesion(
                        current_order[layer_index], targets, bereich_of_node, bereich_anchor_positions, has_hierarchy_neighbor
                    )
                new_order = tuple(sorted(current_order[layer_index], key=lambda nid: (targets[nid], nid)))
                current_order[layer_index] = new_order
                positions.update(_resolve_min_spacing(new_order, targets, min_spacing))

    return positions


def compute_bereich_centroid_positions(
    bereich_ids: frozenset[str],
    node_x_by_id: Mapping[str, float],
    classification_edges: Mapping[str, tuple[str, ...]],
    *,
    min_spacing: float = 170.0,
) -> dict[str, float]:
    """Positioniert Bereichs-Hubs über dem Schwerpunkt der sie klassifizierenden Kompetenzen statt alphabetisch.

    X-Position = arithmetisches Mittel der X-Positionen aller sichtbaren
    Kompetenzen, deren `primarer_bereich`/`prozessbereiche` auf diesen Hub
    zeigt (`classification_edges`). Ein Hub ohne sichtbare klassifizierte
    Kompetenz (z. B. isoliert über den Filter erreichbar) fällt auf `0.0`
    zurück. Anschließende Mindestabstands-Auflösung wie bei
    `relax_horizontal_positions` (Reihenfolge nach Schwerpunkt, Tie-Break
    über die ID für Stabilität bei Gleichstand) -- folgt demselben Prinzip
    "sortieren nach Ziel, dann Mindestabstand", das jetzt auch für die
    Kompetenz-Schichten gilt.

    Args:
        bereich_ids: Aktuell sichtbare Bereichs-Hub-IDs.
        node_x_by_id: Bereits berechnete X-Positionen der Kompetenz-Knoten
            (aus `relax_horizontal_positions`).
        classification_edges: Bereichs-ID → Tupel der sie klassifizierenden,
            sichtbaren Kompetenz-IDs.
        min_spacing: Mindestabstand zwischen zwei benachbarten Hubs.

    Returns:
        Bereichs-ID → berechnete X-Position.
    """
    centroid_by_id: dict[str, float] = {}
    for bereich_id in bereich_ids:
        member_positions = [node_x_by_id[node_id] for node_id in classification_edges.get(bereich_id, ()) if node_id in node_x_by_id]
        centroid_by_id[bereich_id] = _mean(member_positions) if member_positions else 0.0

    ordered_ids = tuple(sorted(bereich_ids, key=lambda bereich_id: (centroid_by_id[bereich_id], bereich_id)))
    return _resolve_min_spacing(ordered_ids, centroid_by_id, min_spacing)
