"""Eval metrics: cooperation score, emergence metrics, determinism fingerprint.

Aggregates run outcomes from the engine + captured step events so the eval
harness can score simulations and detect regressions (Step 8).
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from emotionsim.simulation.determinism import DeterminismTracker


def _normalize_world(world_state: dict[str, Any]) -> dict[str, Any]:
    """Replace random agent UUIDs with names so fingerprints are reproducible."""
    agents = world_state.get("agents", {})
    name_by_id = {
        aid: info.get("name", aid)
        for aid, info in agents.items()
    }
    norm = dict(world_state)
    norm["agents"] = {
        name_by_id.get(aid, aid): dict(info) for aid, info in agents.items()
    }
    # UUID-keyed bookkeeping is not part of the deterministic signature
    if "agent_plans" in norm:
        norm["agent_plans"] = {
            name_by_id.get(aid, aid): value
            for aid, value in norm["agent_plans"].items()
        }
    if "agent_trust" in norm:
        norm["agent_trust"] = {
            name_by_id.get(aid, aid): {
                name_by_id.get(rel, rel): trust
                for rel, trust in trust_map.items()
            }
            for aid, trust_map in norm["agent_trust"].items()
        }
    norm.pop("_graph_entity_ids", None)
    return norm


def compute_run_metrics(
    engine: Any,
    step_payloads: list[dict[str, Any]],
) -> dict[str, Any]:
    """Cooperation + emergence metrics for one finished run."""
    cooperation = engine.coordinator.get_cooperation_context().get("cooperation_score", 0.0)

    speakers: set[str] = set()
    action_types: Counter = Counter()
    total_messages = 0
    for payload in step_payloads:
        for action in payload.get("actions", []):
            action_types[action.get("action_type", "unknown")] += 1
        for msg in payload.get("messages", []):
            total_messages += 1
            name = msg.get("from_agent_name")
            if name:
                speakers.add(name)

    try:
        super_spreaders = engine.social_dynamics.get_super_spreaders()
        opinion_anchors = engine.social_dynamics.get_opinion_anchors()
    except Exception:
        super_spreaders = []
        opinion_anchors = []

    try:
        topics = engine.social_dynamics.sentiment_tracker.get_summary().get("topics", {})
        opinion_topics = len(topics)
        opinion_std_mean = (
            sum(t.get("current_std", 0.0) for t in topics.values()) / max(len(topics), 1)
        )
    except Exception:
        opinion_topics = 0
        opinion_std_mean = 0.0

    return {
        "cooperation_score": round(cooperation, 4),
        "emergence": {
            "super_spreaders": len(super_spreaders),
            "opinion_anchors": len(opinion_anchors),
            "opinion_topics": opinion_topics,
            "opinion_std_mean": round(opinion_std_mean, 4),
            "distinct_speakers": len(speakers),
            "distinct_action_types": len(action_types),
            "total_actions": sum(action_types.values()),
            "total_messages": total_messages,
            "steps": len(step_payloads),
        },
    }


def run_fingerprint(step_payloads: list[dict[str, Any]]) -> str:
    """Determinism fingerprint over a run's step events.

    Two runs with the same seed + config must produce identical fingerprints
    (agent UUIDs are normalized out of world snapshots).
    """
    tracker = DeterminismTracker()
    for payload in step_payloads:
        step = payload.get("step", 0)
        tracker.record_world_state(step, _normalize_world(payload.get("world_state", {})))
        for action in payload.get("actions", []):
            tracker.record_event("action", {
                "agent": action.get("agent_name"),
                "type": action.get("action_type"),
                "target": action.get("target"),
            })
        for msg in payload.get("messages", []):
            tracker.record_event("message", {
                "from": msg.get("from_agent_name"),
                "type": msg.get("message_type"),
                "content": msg.get("content", "")[:200],
            })
    return tracker.fingerprint()
