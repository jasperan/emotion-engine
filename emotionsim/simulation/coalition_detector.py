"""Coalition Detector: graph-based emergent coalition/alliance detection from agent interactions."""
from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any


@dataclass
class Coalition:
    """A detected coalition of cooperating agents."""

    id: str
    members: set[str]
    formed_at_step: int
    dissolved_at_step: int | None = None
    strength: float = 0.0  # internal cooperation density 0-1
    stability: float = 0.0  # fraction of steps it persisted
    leader: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "members": sorted(self.members),
            "formed_at_step": self.formed_at_step,
            "dissolved_at_step": self.dissolved_at_step,
            "strength": round(self.strength, 4),
            "stability": round(self.stability, 4),
            "leader": self.leader,
        }


@dataclass
class CoalitionReport:
    """Full report from coalition detection."""

    coalitions: list[Coalition]
    isolated_agents: list[str]
    modularity: float
    timeline: list[tuple[int, str, Coalition]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "coalitions": [c.to_dict() for c in self.coalitions],
            "isolated_agents": sorted(self.isolated_agents),
            "modularity": round(self.modularity, 4),
            "timeline": [
                (step, event, c.to_dict()) for step, event, c in self.timeline
            ],
        }


# ---------------------------------------------------------------------------
# Interaction types and their default weights
# ---------------------------------------------------------------------------
_COOPERATIVE_TYPES = {"speak", "help", "trade", "vouch", "share_plan", "delegate", "co_locate"}
_ADVERSARIAL_TYPES = {"attack", "betray", "steal", "threaten"}

_DEFAULT_WEIGHTS: dict[str, float] = {
    "speak": 0.5,
    "help": 2.0,
    "trade": 1.5,
    "vouch": 2.5,
    "share_plan": 1.5,
    "delegate": 1.0,
    "co_locate": 0.3,
    "attack": -2.0,
    "betray": -3.0,
    "steal": -2.0,
    "threaten": -1.5,
}


class CoalitionDetector:
    """
    Detects emergent coalitions from agent interaction data using graph-based
    community detection. No external dependencies beyond the stdlib.

    Data is collected via record_* methods. Detection runs on demand via
    detect_coalitions() / detect_coalitions_at_step().
    """

    def __init__(self, detection_interval: int = 1):
        # --- interaction storage ---
        # (a, b) -> list of (step, interaction_type, weight)
        self._interactions: dict[tuple[str, str], list[tuple[int, str, float]]] = defaultdict(list)
        # trust deltas: (a, b) -> list of (step, delta)
        self._trust_changes: dict[tuple[str, str], list[tuple[int, float]]] = defaultdict(list)
        # co-location: step -> location -> set of agent_ids
        self._co_locations: dict[int, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

        # --- agent registry ---
        self._agents: set[str] = set()

        # --- temporal tracking ---
        self._detection_interval = detection_interval
        self._snapshots: dict[int, list[Coalition]] = {}  # step -> coalitions at that step
        self._timeline: list[tuple[int, str, Coalition]] = []
        self._current_step: int = 0

    # ------------------------------------------------------------------
    # Data collection
    # ------------------------------------------------------------------

    def record_interaction(
        self,
        agent_a: str,
        agent_b: str,
        interaction_type: str,
        step: int,
        weight: float | None = None,
    ) -> None:
        """Record an interaction between two agents."""
        self._agents.add(agent_a)
        self._agents.add(agent_b)
        self._current_step = max(self._current_step, step)

        if weight is None:
            weight = _DEFAULT_WEIGHTS.get(interaction_type, 1.0)

        key = tuple(sorted([agent_a, agent_b]))  # type: ignore[assignment]
        self._interactions[key].append((step, interaction_type, weight))

    def record_trust_change(
        self,
        agent_a: str,
        agent_b: str,
        delta: float,
        step: int,
    ) -> None:
        """Record a trust level change between agents."""
        self._agents.add(agent_a)
        self._agents.add(agent_b)
        self._current_step = max(self._current_step, step)

        key = tuple(sorted([agent_a, agent_b]))  # type: ignore[assignment]
        self._trust_changes[key].append((step, delta))

    def record_co_location(
        self,
        agents: list[str],
        location: str,
        step: int,
    ) -> None:
        """Record a group of agents co-located at the same place."""
        for a in agents:
            self._agents.add(a)
        self._current_step = max(self._current_step, step)
        self._co_locations[step][location].update(agents)

        # Generate pairwise co_locate interactions
        for a, b in combinations(agents, 2):
            key = tuple(sorted([a, b]))  # type: ignore[assignment]
            w = _DEFAULT_WEIGHTS.get("co_locate", 0.3)
            self._interactions[key].append((step, "co_locate", w))

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def _build_graph(
        self,
        up_to_step: int | None = None,
    ) -> dict[str, dict[str, float]]:
        """Build weighted adjacency dict from recorded interactions.

        Positive weights = cooperative affinity, negative allowed (adversarial).
        Trust changes add directly to edge weight.
        """
        graph: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

        for (a, b), records in self._interactions.items():
            for step, _itype, weight in records:
                if up_to_step is not None and step > up_to_step:
                    continue
                graph[a][b] += weight
                graph[b][a] += weight

        for (a, b), records in self._trust_changes.items():
            for step, delta in records:
                if up_to_step is not None and step > up_to_step:
                    continue
                graph[a][b] += delta
                graph[b][a] += delta

        return graph

    def get_interaction_graph(self) -> dict[str, dict[str, float]]:
        """Return the current adjacency dict (node -> node -> weight)."""
        raw = self._build_graph()
        # Convert defaultdicts to plain dicts for external consumption
        return {a: dict(neighbors) for a, neighbors in raw.items()}

    # ------------------------------------------------------------------
    # Modularity computation
    # ------------------------------------------------------------------

    @staticmethod
    def _modularity(
        graph: dict[str, dict[str, float]],
        communities: list[set[str]],
    ) -> float:
        """Compute Newman-Girvan modularity Q for a partition.

        Q = (1/2m) * sum_ij [ A_ij - (k_i * k_j) / 2m ] * delta(c_i, c_j)

        Only considers positive edge weights (negative edges are ignored for
        modularity but inform the graph structure).
        """
        # Total positive edge weight
        m2 = 0.0  # 2m
        degrees: dict[str, float] = defaultdict(float)
        for u, neighbors in graph.items():
            for v, w in neighbors.items():
                if w > 0:
                    degrees[u] += w
                    m2 += w  # each edge counted twice in adjacency
        if m2 == 0:
            return 0.0

        # Map node -> community index
        node_comm: dict[str, int] = {}
        for idx, comm in enumerate(communities):
            for node in comm:
                node_comm[node] = idx

        q = 0.0
        for u, neighbors in graph.items():
            cu = node_comm.get(u, -1)
            for v, w in neighbors.items():
                cv = node_comm.get(v, -1)
                if cu == cv and cu >= 0:
                    a_ij = max(w, 0.0)
                    expected = (degrees[u] * degrees[v]) / m2
                    q += a_ij - expected

        return q / m2

    # ------------------------------------------------------------------
    # Greedy modularity optimization
    # ------------------------------------------------------------------

    def _greedy_modularity(
        self,
        graph: dict[str, dict[str, float]],
        min_size: int = 2,
    ) -> list[set[str]]:
        """Greedy agglomerative community detection (CNM-style) with incremental delta-Q.

        Uses community-level aggregates (internal weight, total degree) to compute
        the modularity gain of each merge in O(1) instead of recomputing full Q.

        delta_Q(i,j) = 2 * (e_ij / m2 - (a_i * a_j) / m2^2)

        where e_ij = sum of positive edge weights between communities i and j,
              a_i  = sum of degrees of nodes in community i,
              m2   = total positive edge weight (double-counted).
        """
        nodes = set()
        for u in graph:
            nodes.add(u)
            for v in graph[u]:
                nodes.add(v)

        if not nodes:
            return []

        # Precompute positive-weight degrees and total weight
        degrees: dict[str, float] = defaultdict(float)
        m2 = 0.0
        for u, neighbors in graph.items():
            for v, w in neighbors.items():
                if w > 0:
                    degrees[u] += w
                    m2 += w
        if m2 == 0:
            # No positive edges; every node is isolated
            return []

        # Initialize: each node in own community
        communities: dict[int, set[str]] = {i: {n} for i, n in enumerate(nodes)}
        node_comm: dict[str, int] = {n: i for i, n in enumerate(nodes)}
        next_id = len(nodes)

        # Community aggregates: total degree (a_c) and inter-community positive weights
        comm_degree: dict[int, float] = {}
        for cid, members in communities.items():
            comm_degree[cid] = sum(degrees.get(n, 0.0) for n in members)

        # Build inter-community positive edge weight cache: (c1, c2) -> weight
        # Only for c1 < c2
        comm_edge: dict[tuple[int, int], float] = defaultdict(float)
        for u, neighbors in graph.items():
            cu = node_comm[u]
            for v, w in neighbors.items():
                if w <= 0:
                    continue
                cv = node_comm[v]
                if cu < cv:
                    comm_edge[(cu, cv)] += w
                elif cv < cu:
                    comm_edge[(cv, cu)] += w
                # cu == cv is internal, skip

        improved = True
        while improved:
            improved = False
            best_delta = 0.0
            best_merge: tuple[int, int] | None = None

            # Only consider community pairs with positive inter-community edges
            for (ci, cj), e_ij in list(comm_edge.items()):
                if ci not in communities or cj not in communities:
                    continue
                if e_ij <= 0:
                    continue
                # delta_Q = 2 * (e_ij / m2 - (a_i * a_j) / m2^2)
                # e_ij in comm_edge is single-direction sum; the adjacency is symmetric
                # so actual cross-community weight counted once = e_ij (we built from u<v pairs)
                # but each edge appears once in the directed adjacency iteration above.
                # Actually, we iterated all (u,v) pairs directionally, accumulating only when cu<cv,
                # so e_ij = sum of w for all directed edges u->v where comm(u)<comm(v).
                # In the symmetric adjacency, each undirected edge contributes to both u->v and v->u
                # so e_ij already double-counts (each undirected positive edge adds w once here
                # since we only add when cu<cv, but the adjacency has both directions and we only
                # visit the cu<cv direction). Let's be precise: for each undirected edge {u,v} with
                # cu<cv, the loop visits u's neighbor v (adds w) and v's neighbor u (cu>cv, so
                # the elif branch adds w to (cu,cv) again). So e_ij = 2 * actual_weight.
                # For the modularity formula we want e_ij = sum of A_ij for cross-community pairs
                # which in the symmetric adjacency = 2 * undirected weight. So e_ij here is correct.
                delta = 2.0 * (e_ij / m2 - (comm_degree[ci] * comm_degree[cj]) / (m2 * m2))
                if delta > best_delta + 1e-12:
                    best_delta = delta
                    best_merge = (ci, cj)

            if best_merge is not None:
                ci, cj = best_merge
                merged = communities[ci] | communities[cj]

                # Update comm_edge: merge all edges involving ci or cj
                new_edges: dict[int, float] = defaultdict(float)
                keys_to_remove: list[tuple[int, int]] = []
                for (a, b), w in comm_edge.items():
                    if a == ci or a == cj or b == ci or b == cj:
                        keys_to_remove.append((a, b))
                        # Determine the "other" community
                        other = b if (a == ci or a == cj) else a
                        if other == ci or other == cj:
                            # Internal edge between ci and cj, skip
                            continue
                        new_edges[other] += w

                for k in keys_to_remove:
                    del comm_edge[k]

                # Insert new edges for merged community
                for other, w in new_edges.items():
                    if other not in communities:
                        continue
                    key = (min(next_id, other), max(next_id, other))
                    comm_edge[key] = w

                # Update communities
                del communities[ci]
                del communities[cj]
                communities[next_id] = merged
                for n in merged:
                    node_comm[n] = next_id

                # Update degree
                comm_degree[next_id] = comm_degree.pop(ci) + comm_degree.pop(cj)

                next_id += 1
                improved = True

        # Filter by min_size
        return [c for c in communities.values() if len(c) >= min_size]

    # ------------------------------------------------------------------
    # Clique-based detection (Bron-Kerbosch)
    # ------------------------------------------------------------------

    def _find_cliques(
        self,
        graph: dict[str, dict[str, float]],
        min_size: int = 3,
        cooperation_threshold: float = 0.0,
    ) -> list[set[str]]:
        """Find maximal cliques in the positive-weight subgraph using Bron-Kerbosch.

        Returns cliques of size >= min_size, sorted by internal cooperation strength.
        """
        # Build adjacency set using only edges above threshold
        adj: dict[str, set[str]] = defaultdict(set)
        for u, neighbors in graph.items():
            for v, w in neighbors.items():
                if w > cooperation_threshold:
                    adj[u].add(v)
                    adj[v].add(u)

        cliques: list[set[str]] = []

        def bron_kerbosch(r: set[str], p: set[str], x: set[str]) -> None:
            if not p and not x:
                if len(r) >= min_size:
                    cliques.append(r.copy())
                return
            # Pivot: choose node in P union X with most neighbors in P
            pivot = max(p | x, key=lambda n: len(adj[n] & p)) if (p | x) else None
            candidates = p - adj[pivot] if pivot else p.copy()
            for v in list(candidates):
                bron_kerbosch(
                    r | {v},
                    p & adj[v],
                    x & adj[v],
                )
                p.discard(v)
                x.add(v)

        all_nodes = set(adj.keys())
        bron_kerbosch(set(), all_nodes, set())

        # Sort by total internal cooperation weight (descending)
        def internal_strength(clique: set[str]) -> float:
            total = 0.0
            for a, b in combinations(clique, 2):
                total += max(graph.get(a, {}).get(b, 0.0), 0.0)
            return total

        cliques.sort(key=internal_strength, reverse=True)
        return cliques

    # ------------------------------------------------------------------
    # Coalition strength & leader detection
    # ------------------------------------------------------------------

    def _coalition_strength(
        self,
        members: set[str],
        graph: dict[str, dict[str, float]],
    ) -> float:
        """Internal cooperation density: actual positive weight / max possible.

        Returns 0-1 float.
        """
        if len(members) < 2:
            return 0.0

        pairs = list(combinations(members, 2))
        total_weight = 0.0
        for a, b in pairs:
            w = graph.get(a, {}).get(b, 0.0)
            total_weight += max(w, 0.0)

        if total_weight == 0:
            return 0.0

        # Normalize: find max edge weight in entire graph for scale
        max_weight = 1.0
        for u, neighbors in graph.items():
            for v, w in neighbors.items():
                if w > max_weight:
                    max_weight = w

        max_possible = len(pairs) * max_weight
        return min(total_weight / max_possible, 1.0) if max_possible > 0 else 0.0

    def _find_leader(
        self,
        members: set[str],
        graph: dict[str, dict[str, float]],
    ) -> str | None:
        """Find the agent with highest degree centrality within the subgroup."""
        if not members:
            return None

        centrality: dict[str, float] = {}
        for m in members:
            c = 0.0
            for other in members:
                if other == m:
                    continue
                c += max(graph.get(m, {}).get(other, 0.0), 0.0)
            centrality[m] = c

        if not centrality or max(centrality.values()) == 0:
            return None
        return max(centrality, key=lambda k: centrality[k])

    # ------------------------------------------------------------------
    # Main detection entry points
    # ------------------------------------------------------------------

    def detect_coalitions_at_step(
        self,
        step: int,
        min_size: int = 2,
    ) -> list[Coalition]:
        """Detect coalitions using interactions up to (and including) the given step."""
        graph = self._build_graph(up_to_step=step)
        communities = self._greedy_modularity(graph, min_size=min_size)

        coalitions: list[Coalition] = []
        for comm in communities:
            c = Coalition(
                id=str(uuid.uuid4()),
                members=comm,
                formed_at_step=step,
                strength=self._coalition_strength(comm, graph),
                leader=self._find_leader(comm, graph),
            )
            coalitions.append(c)

        self._snapshots[step] = coalitions
        return coalitions

    def detect_coalitions(self, min_size: int = 2) -> CoalitionReport:
        """Run full coalition detection on all data collected so far.

        Combines greedy modularity for partition and clique detection for
        fully-connected subgroups. Builds temporal timeline if snapshots exist.
        """
        graph = self._build_graph()
        communities = self._greedy_modularity(graph, min_size=min_size)

        # Build Coalition objects
        coalitions: list[Coalition] = []
        members_in_coalitions: set[str] = set()

        for comm in communities:
            c = Coalition(
                id=str(uuid.uuid4()),
                members=comm,
                formed_at_step=0,
                strength=self._coalition_strength(comm, graph),
                leader=self._find_leader(comm, graph),
            )
            coalitions.append(c)
            members_in_coalitions.update(comm)

        # Isolated agents
        isolated = sorted(self._agents - members_in_coalitions)

        # Modularity
        mod = self._modularity(graph, [c.members for c in coalitions]) if coalitions else 0.0

        # Build temporal timeline from snapshots
        timeline = self._build_timeline()

        # Update stability scores
        if self._current_step > 0 and self._snapshots:
            self._compute_stability(coalitions)

        return CoalitionReport(
            coalitions=coalitions,
            isolated_agents=isolated,
            modularity=mod,
            timeline=timeline,
        )

    def get_agent_coalition(self, agent_id: str) -> Coalition | None:
        """Get the current coalition for an agent (from the latest detection)."""
        graph = self._build_graph()
        communities = self._greedy_modularity(graph, min_size=2)

        for comm in communities:
            if agent_id in comm:
                return Coalition(
                    id=str(uuid.uuid4()),
                    members=comm,
                    formed_at_step=0,
                    strength=self._coalition_strength(comm, graph),
                    leader=self._find_leader(comm, graph),
                )
        return None

    def get_coalition_timeline(self) -> list[tuple[int, str, Coalition]]:
        """Return the full temporal timeline of coalition events."""
        return self._build_timeline()

    def find_cliques(self, min_size: int = 3) -> list[Coalition]:
        """Find fully-connected cliques in the cooperation graph."""
        graph = self._build_graph()
        cliques = self._find_cliques(graph, min_size=min_size)

        result: list[Coalition] = []
        for clique in cliques:
            c = Coalition(
                id=str(uuid.uuid4()),
                members=clique,
                formed_at_step=0,
                strength=self._coalition_strength(clique, graph),
                leader=self._find_leader(clique, graph),
            )
            result.append(c)
        return result

    # ------------------------------------------------------------------
    # Temporal analysis helpers
    # ------------------------------------------------------------------

    def _build_timeline(self) -> list[tuple[int, str, Coalition]]:
        """Compare consecutive snapshots to detect formation, dissolution, merger, split."""
        if len(self._snapshots) < 2:
            return list(self._timeline)

        steps = sorted(self._snapshots.keys())
        timeline: list[tuple[int, str, Coalition]] = []

        for i in range(1, len(steps)):
            prev_step = steps[i - 1]
            curr_step = steps[i]
            prev_coalitions = self._snapshots[prev_step]
            curr_coalitions = self._snapshots[curr_step]

            prev_sets = [c.members for c in prev_coalitions]
            curr_sets = [c.members for c in curr_coalitions]

            # Detect formations: current coalitions not substantially in any previous
            for cc in curr_coalitions:
                found_overlap = False
                for ps in prev_sets:
                    overlap = len(cc.members & ps) / max(len(cc.members), 1)
                    if overlap >= 0.5:
                        found_overlap = True
                        break
                if not found_overlap:
                    cc.formed_at_step = curr_step
                    timeline.append((curr_step, "formed", cc))

            # Detect dissolutions: previous coalitions not in any current
            for pc in prev_coalitions:
                found_overlap = False
                for cs in curr_sets:
                    overlap = len(pc.members & cs) / max(len(pc.members), 1)
                    if overlap >= 0.5:
                        found_overlap = True
                        break
                if not found_overlap:
                    pc.dissolved_at_step = curr_step
                    timeline.append((curr_step, "dissolved", pc))

            # Detect mergers: two previous coalitions now in one current
            for cc in curr_coalitions:
                sources = [
                    ps for ps in prev_sets
                    if len(cc.members & ps) / max(len(ps), 1) >= 0.5
                ]
                if len(sources) >= 2:
                    timeline.append((curr_step, "merged", cc))

            # Detect splits: one previous coalition now in two current
            for ps in prev_sets:
                targets = [
                    cc for cc in curr_coalitions
                    if len(cc.members & ps) / max(len(cc.members), 1) >= 0.5
                ]
                if len(targets) >= 2:
                    for t in targets:
                        timeline.append((curr_step, "split", t))

        self._timeline = timeline
        return timeline

    def _compute_stability(self, coalitions: list[Coalition]) -> None:
        """Compute stability: fraction of snapshot steps each coalition persisted."""
        if not self._snapshots:
            return
        total_snapshots = len(self._snapshots)
        steps = sorted(self._snapshots.keys())

        for c in coalitions:
            present_count = 0
            for step in steps:
                snap_coalitions = self._snapshots[step]
                for sc in snap_coalitions:
                    # Same coalition if >= 50% member overlap
                    overlap = len(c.members & sc.members) / max(len(c.members), 1)
                    if overlap >= 0.5:
                        present_count += 1
                        break
            c.stability = present_count / total_snapshots if total_snapshots > 0 else 0.0

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize detector state."""
        report = self.detect_coalitions()
        return {
            "agents": sorted(self._agents),
            "current_step": self._current_step,
            "interaction_count": sum(len(v) for v in self._interactions.values()),
            "report": report.to_dict(),
        }
