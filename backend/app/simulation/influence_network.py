"""Influence Network Model: tracks directed influence relationships between agents."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class InfluenceEdge:
    """A directed influence relationship."""

    source_id: str  # influencer
    target_id: str  # influenced
    topic: str
    total_delta: float  # cumulative opinion shift caused
    interaction_count: int
    last_step: int


@dataclass
class AgentInfluenceProfile:
    """Summary of an agent's influence characteristics."""

    agent_id: str
    total_influence_exerted: float  # sum of abs(delta) on others
    total_influence_received: float  # sum of abs(delta) from others
    topics_influenced: set[str]  # topics where this agent changed others
    influenced_agents: set[str]  # agents this one changed
    influenced_by_agents: set[str]  # agents that changed this one
    is_super_spreader: bool  # top 10% by influence_exerted
    is_opinion_anchor: bool  # low influence_received despite interactions


class InfluenceNetwork:
    """Tracks directed influence relationships between agents.

    Edges are keyed by (source, target, topic). Each edge accumulates
    the total opinion delta and interaction count over the simulation.
    """

    def __init__(self) -> None:
        self._edges: dict[tuple[str, str, str], InfluenceEdge] = {}
        self._agent_ids: set[str] = set()

    def record_influence(
        self,
        source_id: str,
        target_id: str,
        topic: str,
        delta: float,
        step: int,
    ) -> None:
        """Record that source influenced target on topic by delta at step."""
        key = (source_id, target_id, topic)
        if key in self._edges:
            edge = self._edges[key]
            edge.total_delta += delta
            edge.interaction_count += 1
            edge.last_step = step
        else:
            self._edges[key] = InfluenceEdge(
                source_id=source_id,
                target_id=target_id,
                topic=topic,
                total_delta=delta,
                interaction_count=1,
                last_step=step,
            )
        self._agent_ids.add(source_id)
        self._agent_ids.add(target_id)

    def get_profile(self, agent_id: str) -> AgentInfluenceProfile:
        """Get influence profile for an agent."""
        exerted: float = 0.0
        received: float = 0.0
        topics_influenced: set[str] = set()
        influenced_agents: set[str] = set()
        influenced_by_agents: set[str] = set()
        interaction_count_as_target = 0

        for (src, tgt, topic), edge in self._edges.items():
            if src == agent_id:
                exerted += abs(edge.total_delta)
                topics_influenced.add(topic)
                influenced_agents.add(tgt)
            if tgt == agent_id:
                received += abs(edge.total_delta)
                influenced_by_agents.add(src)
                interaction_count_as_target += edge.interaction_count

        # Determine super_spreader status: top 10% by exerted influence
        super_spreaders = set(self.get_super_spreaders())
        is_super_spreader = agent_id in super_spreaders

        # Determine opinion_anchor: low received despite having interactions
        is_opinion_anchor = self._is_opinion_anchor(
            agent_id, received, interaction_count_as_target
        )

        return AgentInfluenceProfile(
            agent_id=agent_id,
            total_influence_exerted=exerted,
            total_influence_received=received,
            topics_influenced=topics_influenced,
            influenced_agents=influenced_agents,
            influenced_by_agents=influenced_by_agents,
            is_super_spreader=is_super_spreader,
            is_opinion_anchor=is_opinion_anchor,
        )

    def get_edges(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        topic: str | None = None,
    ) -> list[InfluenceEdge]:
        """Get edges, optionally filtered by source, target, and/or topic."""
        results: list[InfluenceEdge] = []
        for (src, tgt, t), edge in self._edges.items():
            if source_id is not None and src != source_id:
                continue
            if target_id is not None and tgt != target_id:
                continue
            if topic is not None and t != topic:
                continue
            results.append(edge)
        return results

    def get_super_spreaders(self, top_pct: float = 0.1) -> list[str]:
        """Get agent IDs of top influencers by exerted influence."""
        if not self._agent_ids:
            return []

        exerted_by_agent: dict[str, float] = {aid: 0.0 for aid in self._agent_ids}
        for (src, _tgt, _topic), edge in self._edges.items():
            exerted_by_agent[src] = exerted_by_agent.get(src, 0.0) + abs(
                edge.total_delta
            )

        # Sort descending by exerted influence
        sorted_agents = sorted(
            exerted_by_agent.items(), key=lambda x: x[1], reverse=True
        )

        # Top N% (at least 1 agent if any have nonzero influence)
        n = max(1, math.ceil(len(sorted_agents) * top_pct))
        return [aid for aid, val in sorted_agents[:n] if val > 0]

    def get_opinion_anchors(self, max_received_ratio: float = 0.2) -> list[str]:
        """Get agents who resist influence (low received relative to interactions)."""
        anchors: list[str] = []
        for agent_id in self._agent_ids:
            received = 0.0
            interaction_count = 0
            for (src, tgt, _topic), edge in self._edges.items():
                if tgt == agent_id:
                    received += abs(edge.total_delta)
                    interaction_count += edge.interaction_count

            if interaction_count > 0 and received / interaction_count <= max_received_ratio:
                anchors.append(agent_id)
        return anchors

    def get_influence_matrix(
        self, topic: str | None = None
    ) -> dict[str, dict[str, float]]:
        """Get source -> target -> total_delta matrix.

        If topic is provided, filter to that topic only.
        """
        matrix: dict[str, dict[str, float]] = {}
        for (src, tgt, t), edge in self._edges.items():
            if topic is not None and t != topic:
                continue
            if src not in matrix:
                matrix[src] = {}
            matrix[src][tgt] = matrix[src].get(tgt, 0.0) + edge.total_delta
        return matrix

    def to_visualization_data(self) -> dict[str, Any]:
        """Export network as nodes + edges for frontend visualization."""
        # Build per-agent summaries
        exerted: dict[str, float] = {aid: 0.0 for aid in self._agent_ids}
        received: dict[str, float] = {aid: 0.0 for aid in self._agent_ids}

        for (src, tgt, _topic), edge in self._edges.items():
            exerted[src] = exerted.get(src, 0.0) + abs(edge.total_delta)
            received[tgt] = received.get(tgt, 0.0) + abs(edge.total_delta)

        nodes = [
            {
                "id": aid,
                "influence_exerted": exerted.get(aid, 0.0),
                "influence_received": received.get(aid, 0.0),
            }
            for aid in sorted(self._agent_ids)
        ]

        edges = [
            {
                "source": edge.source_id,
                "target": edge.target_id,
                "topic": edge.topic,
                "weight": edge.total_delta,
                "interaction_count": edge.interaction_count,
                "last_step": edge.last_step,
            }
            for edge in self._edges.values()
        ]

        return {"nodes": nodes, "edges": edges}

    def _is_opinion_anchor(
        self, agent_id: str, received: float, interaction_count: int
    ) -> bool:
        """Check if an agent qualifies as an opinion anchor.

        An opinion anchor has many interactions as a target but very low
        cumulative influence received (i.e., they resist changing).
        """
        if interaction_count == 0:
            return False
        avg_received = received / interaction_count
        return avg_received <= 0.2
