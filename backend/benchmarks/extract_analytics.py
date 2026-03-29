"""
Extract structured analytics from benchmark runs for downstream analysis.

Produces per-run JSON files with:
- Agent decision timelines (action, speech, emotion, stress per step)
- Cooperation events (who helped whom, shared resources)
- Critical decision points (high-stress pivots, leadership emergence)
- Movement patterns (where agents went, failed moves)
- Communication graph (who talked to whom, broadcast vs direct)
- Stress/emotion trajectories
"""
import asyncio
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.run import Run, RunStatus
from app.models.agent import AgentModel
from app.models.step import Step
from app.models.message import Message, MessageType
from app.models.scenario import Scenario


RESULTS_DIR = Path(__file__).parent / "results"


def extract_agent_profile(agent: AgentModel) -> dict:
    persona = agent.persona or {}
    dynamic = agent.dynamic_state or {}
    return {
        "id": agent.id,
        "name": agent.name,
        "role": agent.role,
        "occupation": persona.get("occupation", "unknown"),
        "age": persona.get("age"),
        "big_five": {
            "openness": persona.get("openness"),
            "conscientiousness": persona.get("conscientiousness"),
            "extraversion": persona.get("extraversion"),
            "agreeableness": persona.get("agreeableness"),
            "neuroticism": persona.get("neuroticism"),
        },
        "final_stress": dynamic.get("stress_level"),
        "final_health": dynamic.get("health"),
        "final_location": dynamic.get("location"),
        "is_active": agent.is_active,
    }


def extract_step_actions(step: Step) -> list[dict]:
    """Parse step actions into structured records."""
    actions = step.actions or []
    parsed = []
    for act in actions:
        if isinstance(act, dict):
            parsed.append({
                "agent_id": act.get("agent_id"),
                "agent_name": act.get("agent_name"),
                "action": act.get("action"),
                "speech": act.get("speech"),
                "emotion": act.get("emotion"),
                "thought": act.get("thought"),
                "move_to": act.get("move_to"),
                "stress_level": act.get("stress_level"),
                "step": step.step_index,
            })
    return parsed


def classify_critical_decisions(all_actions: list[dict]) -> list[dict]:
    """Identify critical decision points based on heuristics."""
    critical = []
    for act in all_actions:
        reasons = []
        stress = act.get("stress_level")
        if stress and stress >= 8:
            reasons.append("high_stress")

        speech = (act.get("speech") or "").lower()
        if any(w in speech for w in ["help", "save", "rescue", "protect", "everyone"]):
            reasons.append("cooperative_speech")
        if any(w in speech for w in ["run", "leave", "abandon", "forget"]):
            reasons.append("self_preservation")
        if any(w in speech for w in ["follow me", "with me", "let's go", "i'll lead"]):
            reasons.append("leadership")

        action = (act.get("action") or "").lower()
        if any(w in action for w in ["shield", "protect", "carry", "drag", "rescue"]):
            reasons.append("heroic_action")
        if act.get("move_to"):
            reasons.append("relocation")

        emotion = (act.get("emotion") or "").lower()
        if any(w in emotion for w in ["panic", "terror", "despair"]):
            reasons.append("extreme_emotion")

        if len(reasons) >= 2:
            critical.append({
                **act,
                "decision_tags": reasons,
                "criticality_score": len(reasons),
            })

    return sorted(critical, key=lambda x: x["criticality_score"], reverse=True)


def build_communication_graph(messages: list[Message]) -> dict:
    """Build directed communication graph from messages."""
    edges = defaultdict(lambda: {"count": 0, "types": []})
    broadcasts = 0
    direct_count = 0

    for msg in messages:
        sender = msg.from_agent_id or "system"
        target = msg.to_target
        mtype = msg.message_type.value if msg.message_type else "unknown"

        if mtype == "broadcast":
            broadcasts += 1
        else:
            direct_count += 1

        key = f"{sender}->{target}"
        edges[key]["count"] += 1
        if mtype not in edges[key]["types"]:
            edges[key]["types"].append(mtype)

    return {
        "total_messages": len(messages),
        "broadcasts": broadcasts,
        "direct_messages": direct_count,
        "edges": [
            {"from": k.split("->")[0], "to": k.split("->")[1], **v}
            for k, v in edges.items()
        ],
    }


def compute_stress_trajectories(all_actions: list[dict], agents: dict[str, str]) -> dict:
    """Compute per-agent stress over time."""
    trajectories = defaultdict(list)
    for act in all_actions:
        agent_name = act.get("agent_name") or agents.get(act.get("agent_id"), "?")
        stress = act.get("stress_level")
        if stress is not None:
            trajectories[agent_name].append({
                "step": act["step"],
                "stress": stress,
                "emotion": act.get("emotion"),
            })
    return dict(trajectories)


def compute_movement_patterns(all_actions: list[dict]) -> dict:
    """Track movement successes and common destinations."""
    moves = []
    destinations = defaultdict(int)
    for act in all_actions:
        if act.get("move_to"):
            moves.append({
                "agent": act.get("agent_name"),
                "step": act["step"],
                "destination": act["move_to"],
            })
            destinations[act["move_to"]] += 1
    return {
        "total_moves": len(moves),
        "moves": moves,
        "popular_destinations": dict(sorted(destinations.items(), key=lambda x: -x[1])),
    }


async def extract_run(run_id: str, session_factory) -> dict:
    """Extract full analytics for a single run."""
    async with session_factory() as db:
        # Load run with relationships
        result = await db.execute(
            select(Run).where(Run.id == run_id)
        )
        run = result.scalars().first()
        if not run:
            return {"error": f"Run {run_id} not found"}

        # Load scenario
        scenario_result = await db.execute(
            select(Scenario).where(Scenario.id == run.scenario_id)
        )
        scenario = scenario_result.scalars().first()

        # Load agents
        agents_result = await db.execute(
            select(AgentModel).where(AgentModel.run_id == run_id)
        )
        agents = agents_result.scalars().all()
        agent_map = {a.id: a.name for a in agents}

        # Load steps
        steps_result = await db.execute(
            select(Step).where(Step.run_id == run_id).order_by(Step.step_index)
        )
        steps = steps_result.scalars().all()

        # Load messages
        msgs_result = await db.execute(
            select(Message).where(Message.run_id == run_id).order_by(Message.step_index)
        )
        messages = msgs_result.scalars().all()

        # Extract all actions across steps
        all_actions = []
        for step in steps:
            all_actions.extend(extract_step_actions(step))

        # Build analytics
        analytics = {
            "run_id": run_id,
            "scenario": scenario.name if scenario else "unknown",
            "scenario_description": (scenario.description[:200] if scenario else ""),
            "status": run.status.value,
            "total_steps": run.current_step,
            "max_steps": run.max_steps,
            "seed": run.seed,
            "metrics": run.metrics or {},
            "evaluation": run.evaluation or {},

            "agents": [extract_agent_profile(a) for a in agents if a.role == "human"],
            "agent_count": len([a for a in agents if a.role == "human"]),

            "total_actions": len(all_actions),
            "total_messages": len(messages),

            "critical_decisions": classify_critical_decisions(all_actions),
            "communication_graph": build_communication_graph(messages),
            "stress_trajectories": compute_stress_trajectories(all_actions, agent_map),
            "movement_patterns": compute_movement_patterns(all_actions),

            "action_timeline": all_actions,
        }

        return analytics


async def main():
    """Extract analytics for all runs in the latest benchmark manifest."""
    # Find latest manifest
    manifests = sorted(RESULTS_DIR.glob("benchmark_*.json"), reverse=True)
    if not manifests:
        print("No benchmark manifests found. Run run_benchmark.py first.")
        return

    manifest_path = manifests[0]
    print(f"Loading manifest: {manifest_path.name}")
    manifest = json.loads(manifest_path.read_text())

    settings = get_settings()
    db_engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    run_ids = [r["run_id"] for r in manifest["runs"] if "run_id" in r]
    print(f"Extracting analytics for {len(run_ids)} runs...\n")

    for run_id in run_ids:
        analytics = await extract_run(run_id, session_factory)
        if "error" in analytics:
            print(f"  SKIP: {analytics['error']}")
            continue

        # Save per-run analytics
        out_path = RESULTS_DIR / f"analytics_{run_id[:8]}.json"
        out_path.write_text(json.dumps(analytics, indent=2, default=str))

        # Print summary
        n_critical = len(analytics["critical_decisions"])
        n_msgs = analytics["total_messages"]
        n_acts = analytics["total_actions"]
        scenario = analytics["scenario"][:40]
        print(f"  {scenario:<42} steps={analytics['total_steps']:<4} actions={n_acts:<5} msgs={n_msgs:<5} critical={n_critical}")

    # Save combined summary
    summary_path = RESULTS_DIR / f"summary_{manifest['benchmark_id']}.json"
    summary = {
        "benchmark_id": manifest["benchmark_id"],
        "model": manifest.get("model"),
        "backend": manifest.get("backend"),
        "run_ids": run_ids,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
    }
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"\nSummary saved: {summary_path}")

    await db_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
