"""
Extract structured analytics from benchmark runs for downstream analysis.

Pulls data from Oracle DB tables:
- steps.actions: [{agent_id, agent_name, action_type, target, parameters}]
- messages: speech content with sender/target/type/step
- agents: persona (Big Five), dynamic_state (stress, health, location)
- steps.state_snapshot: world state per step
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

from emotionsim.core.config import get_settings
from emotionsim.models.run import Run
from emotionsim.models.agent import AgentModel
from emotionsim.models.step import Step
from emotionsim.models.message import Message


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
    """Parse step actions from DB format: {action_type, target, parameters}."""
    actions = step.actions or []
    parsed = []
    for act in actions:
        if not isinstance(act, dict):
            continue
        params = act.get("parameters", {}) or {}
        parsed.append({
            "agent_id": act.get("agent_id"),
            "agent_name": act.get("agent_name"),
            "action_type": act.get("action_type"),
            "target": act.get("target"),
            "parameters": params,
            "step": step.step_index,
        })
    return parsed


def build_message_timeline(messages: list[Message], agent_map: dict) -> list[dict]:
    """Build a timeline of speech/communication from messages table."""
    timeline = []
    for msg in messages:
        sender_name = agent_map.get(msg.from_agent_id, msg.from_agent_id or "system")
        timeline.append({
            "step": msg.step_index,
            "from_agent": sender_name,
            "from_id": msg.from_agent_id,
            "to": msg.to_target,
            "type": msg.message_type.value if msg.message_type else "unknown",
            "content": msg.content,
        })
    return timeline


def classify_critical_decisions(
    messages: list[dict],
    actions: list[dict],
    agents: list[dict],
) -> list[dict]:
    """Identify critical decisions from messages and actions."""
    critical = []

    # Analyze messages for cooperative/leadership/panic speech
    for msg in messages:
        if msg["type"] == "system":
            continue
        reasons = []
        content = (msg.get("content") or "").lower()

        if any(w in content for w in ["help", "save", "rescue", "protect", "everyone", "together"]):
            reasons.append("cooperative_speech")
        if any(w in content for w in ["run", "leave", "abandon", "forget it", "give up"]):
            reasons.append("self_preservation")
        if any(w in content for w in ["follow me", "with me", "let's go", "i'll lead", "listen to me", "move now"]):
            reasons.append("leadership")
        if any(w in content for w in ["oh god", "we're going to die", "no!", "damn", "help!"]):
            reasons.append("panic_speech")

        if reasons:
            critical.append({
                "step": msg["step"],
                "agent": msg["from_agent"],
                "type": "speech",
                "content": msg["content"][:200],
                "tags": reasons,
                "score": len(reasons),
            })

    # Analyze cinematic records for rich behavioral data
    for act in actions:
        if act.get("action_type") == "cinematic":
            params = act.get("parameters", {})
            reasons = []
            agent_name = act.get("agent_name", "?")

            stress = params.get("stress_level")
            if stress and stress >= 8:
                reasons.append("high_stress")

            speech = (params.get("speech") or "").lower()
            if any(w in speech for w in ["help", "save", "rescue", "protect", "everyone", "together"]):
                reasons.append("cooperative_speech")
            if any(w in speech for w in ["run", "leave", "abandon", "forget it", "give up"]):
                reasons.append("self_preservation")
            if any(w in speech for w in ["follow me", "with me", "let's go", "i'll lead", "listen to me"]):
                reasons.append("leadership")
            if any(w in speech for w in ["oh god", "we're going to die", "damn", "help!"]):
                reasons.append("panic_speech")

            action_desc = (params.get("action") or "").lower()
            if any(w in action_desc for w in ["shield", "protect", "carry", "drag", "rescue", "bandage"]):
                reasons.append("heroic_action")

            emotion = (params.get("emotion") or "").lower()
            if any(w in emotion for w in ["panic", "terror", "despair", "fear"]):
                reasons.append("extreme_emotion")

            if reasons:
                critical.append({
                    "step": act.get("step"),
                    "agent": agent_name,
                    "type": "cinematic",
                    "action": params.get("action", "")[:150],
                    "speech": params.get("speech", "")[:150] if params.get("speech") else None,
                    "emotion": params.get("emotion"),
                    "stress": stress,
                    "tags": reasons,
                    "score": len(reasons),
                })
            continue

    # Analyze structured actions for heroic/movement decisions
    for act in actions:
        reasons = []
        action_type = act.get("action_type", "")
        params = act.get("parameters", {})

        if action_type == "cinematic":
            continue  # Already handled above
        if action_type == "move":
            reasons.append("relocation")
        if action_type in ("help", "rescue", "share"):
            reasons.append("heroic_action")
        if action_type == "environment_update":
            continue  # Skip env agent updates

        # Check parameters for cooperation signals
        param_str = json.dumps(params).lower()
        if any(w in param_str for w in ["shield", "protect", "carry", "drag", "rescue", "bandage"]):
            reasons.append("heroic_action")

        if reasons:
            critical.append({
                "step": act["step"],
                "agent": act["agent_name"],
                "type": "action",
                "action_type": action_type,
                "tags": reasons,
                "score": len(reasons),
            })

    # Check agent final states for high stress
    for agent in agents:
        stress = agent.get("final_stress")
        if stress and stress >= 8:
            critical.append({
                "agent": agent["name"],
                "type": "final_state",
                "tags": ["high_stress"],
                "score": 1,
                "final_stress": stress,
                "final_health": agent.get("final_health"),
            })

    return sorted(critical, key=lambda x: x.get("score", 0), reverse=True)


def build_communication_graph(messages: list[dict]) -> dict:
    """Build directed communication graph from message timeline."""
    edges = defaultdict(lambda: {"count": 0, "types": []})
    broadcasts = 0
    direct_count = 0

    for msg in messages:
        sender = msg["from_agent"]
        target = msg["to"]
        mtype = msg["type"]

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
        "unique_speakers": len({m["from_agent"] for m in messages}),
        "edges": [
            {"from": k.split("->")[0], "to": k.split("->")[1], **v}
            for k, v in edges.items()
        ],
    }


def extract_world_state_progression(steps: list[Step]) -> list[dict]:
    """Track world state changes across steps."""
    progression = []
    for step in steps:
        snapshot = step.state_snapshot or {}
        progression.append({
            "step": step.step_index,
            "hazard_level": snapshot.get("hazard_level"),
            "weather": snapshot.get("weather"),
            "time_of_day": snapshot.get("time_of_day"),
            "events": snapshot.get("events", []),
            "resources": snapshot.get("resources", []),
        })
    return progression


async def extract_run(run_id: str, session_factory) -> dict:
    """Extract full analytics for a single run."""
    async with session_factory() as db:
        result = await db.execute(select(Run).where(Run.id == run_id))
        run = result.scalars().first()
        if not run:
            return {"error": f"Run {run_id} not found"}

        # Load scenario name
        from emotionsim.models.scenario import Scenario
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
        agent_profiles = [extract_agent_profile(a) for a in agents if a.role == "human"]

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

        # Build structured data
        all_actions = []
        for step in steps:
            all_actions.extend(extract_step_actions(step))

        msg_timeline = build_message_timeline(messages, agent_map)

        # Build cinematic timeline (agent experience per tick)
        cinematic_timeline = []
        stress_trajectories = defaultdict(list)
        for act in all_actions:
            if act.get("action_type") == "cinematic":
                params = act.get("parameters", {})
                entry = {
                    "step": act["step"],
                    "agent": act["agent_name"],
                    "action": params.get("action"),
                    "speech": params.get("speech"),
                    "thought": params.get("thought"),
                    "emotion": params.get("emotion"),
                    "stress": params.get("stress_level"),
                    "health": params.get("health"),
                    "location": params.get("location"),
                }
                cinematic_timeline.append(entry)
                if params.get("stress_level") is not None:
                    stress_trajectories[act["agent_name"]].append({
                        "step": act["step"],
                        "stress": params["stress_level"],
                        "emotion": params.get("emotion"),
                        "health": params.get("health"),
                    })

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

            "agents": agent_profiles,
            "agent_count": len(agent_profiles),

            "total_actions": len(all_actions),
            "total_messages": len(msg_timeline),

            "critical_decisions": classify_critical_decisions(
                msg_timeline, all_actions, agent_profiles
            ),
            "communication_graph": build_communication_graph(msg_timeline),
            "stress_trajectories": dict(stress_trajectories),
            "world_state_progression": extract_world_state_progression(steps),
            "cinematic_timeline": cinematic_timeline,
            "action_timeline": all_actions,
            "message_timeline": msg_timeline,
        }

        return analytics


async def main():
    manifests = sorted(RESULTS_DIR.glob("benchmark_*.json"), reverse=True)
    if not manifests:
        print("No benchmark manifests found. Run run_benchmark.py first.")
        return

    manifest_path = manifests[0]
    print(f"Loading manifest: {manifest_path.name}")
    manifest = json.loads(manifest_path.read_text())

    settings = get_settings()
    db_engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(
        db_engine, class_=AsyncSession, expire_on_commit=False
    )

    run_ids = [r["run_id"] for r in manifest["runs"] if "run_id" in r]
    print(f"Extracting analytics for {len(run_ids)} runs...\n")

    for run_id in run_ids:
        analytics = await extract_run(run_id, session_factory)
        if "error" in analytics:
            print(f"  SKIP: {analytics['error']}")
            continue

        out_path = RESULTS_DIR / f"analytics_{run_id[:8]}.json"
        out_path.write_text(json.dumps(analytics, indent=2, default=str))

        n_critical = len(analytics["critical_decisions"])
        n_msgs = analytics["total_messages"]
        n_acts = analytics["total_actions"]
        scenario = analytics["scenario"][:40]
        print(
            f"  {scenario:<42} steps={analytics['total_steps']:<4} "
            f"actions={n_acts:<5} msgs={n_msgs:<5} critical={n_critical}"
        )

    summary_path = RESULTS_DIR / f"summary_{manifest['benchmark_id']}.json"
    summary = {
        "benchmark_id": manifest["benchmark_id"],
        "models": manifest.get("models"),
        "backend": manifest.get("backend"),
        "total_time": manifest.get("total_time_seconds"),
        "run_ids": run_ids,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
    }
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"\nSummary saved: {summary_path}")

    await db_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
