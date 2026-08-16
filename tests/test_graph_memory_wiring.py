"""Step 1 (MiroFish): GraphMemory wired into live agent ticks.

Covers:
- config flag default (graph memory OFF by default → determinism preserved)
- engine attaches GraphMemory to human agents when enabled (fresh + resume)
- relevance-based recall surfaces a memory from >10 steps ago (not recency)
- graceful fallback when the embedding service is down
- full engine run persists graph memory nodes linked to location entities
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from emotionsim.agents.human import HumanAgent
from emotionsim.agents.graph_memory import GraphMemory
from emotionsim.core.config import Settings, get_settings
from emotionsim.llm.base import LLMResponse
from emotionsim.models.run import Run, RunStatus
from emotionsim.models.graph import GraphModel, MemoryEdgeModel, MemoryNodeModel
from emotionsim.schemas.persona import Persona
from emotionsim.simulation.engine import SimulationEngine
from emotionsim.storage.embedding_service import EmbeddingService
from emotionsim.storage.graph_storage import Entity
from emotionsim.storage.oracle_graph_storage import OracleGraphStorage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_persona(**overrides) -> Persona:
    defaults = dict(
        name="Test Agent",
        age=30,
        sex="non-binary",
        occupation="Tester",
        openness=5,
        conscientiousness=5,
        extraversion=5,
        agreeableness=5,
        neuroticism=5,
        risk_tolerance=5,
        empathy_level=5,
        leadership=5,
        backstory="A test agent for unit testing",
        stress_level=3,
        health=10,
        location="Town Square",
    )
    defaults.update(overrides)
    return Persona(**defaults)


def _scenario_config(max_steps: int = 5) -> dict:
    return {
        "config": {
            "max_steps": max_steps,
            "tick_delay": 0.01,
            "initial_state": {
                "hazard_level": 3,
                "locations": {
                    "Town Square": {
                        "description": "A flooded town square",
                        "nearby": ["Hill"],
                        "items": [],
                    },
                    "Hill": {
                        "description": "High ground",
                        "nearby": ["Town Square"],
                        "items": [],
                    },
                },
            },
        },
        "agent_templates": [
            {
                "name": "Aria",
                "role": "human",
                "model_id": "test-model",
                "provider": "ollama",
                "persona": {
                    "name": "Aria",
                    "age": 30,
                    "sex": "female",
                    "occupation": "Nurse",
                    "location": "Town Square",
                },
            }
        ],
    }


def _act_response_json() -> str:
    return json.dumps({
        "action": "She hurries toward the hill.",
        "speech": "We need high ground!",
        "thought": "The water is rising fast.",
        "emotion": "fear",
        "move_to": "Hill",
        "stress_level": 6,
    })


def _think_response_json() -> str:
    return json.dumps({
        "urgency": "medium",
        "assessment": "Water is rising",
        "top_need": "shelter",
    })


def _plan_response_json() -> str:
    return json.dumps({
        "goal": "Reach high ground",
        "steps": ["Move to Hill"],
        "success_criteria": "Safe",
        "fallback": None,
    })


def _mock_generate(**kwargs) -> LLMResponse:
    """Route mock LLM responses by system prompt (think / plan / act)."""
    system = kwargs.get("system") or ""
    if "analyzing a situation" in system:
        content = _think_response_json()
    elif "creating an action plan" in system:
        content = _plan_response_json()
    else:
        content = _act_response_json()
    return LLMResponse(content=content, raw_response={}, usage={})


# ---------------------------------------------------------------------------
# Config flag
# ---------------------------------------------------------------------------


def test_graph_memory_disabled_by_default():
    """Default config keeps flat memory — sequential determinism unaffected."""
    assert get_settings().graph_memory_enabled is False
    assert Settings().graph_memory_enabled is False


# ---------------------------------------------------------------------------
# Engine wiring
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_engine_attaches_graph_memory_when_enabled(db_session):
    """initialize() creates a graph, seeds location entities, attaches GraphMemory."""
    run = Run(id="run-gm-init", scenario_id="scenario-gm", status=RunStatus.PENDING)
    db_session.add(run)
    await db_session.commit()

    with patch(
        "emotionsim.simulation.engine.get_settings",
        return_value=Settings(graph_memory_enabled=True),
    ):
        engine = SimulationEngine(run_id="run-gm-init", db_session=db_session)
        with patch("emotionsim.simulation.engine.LLMRouter") as mock_router:
            mock_router.get_client.return_value = MagicMock()
            await engine.initialize(_scenario_config())

    assert engine._graph_id is not None

    # Run row persisted the graph id
    refreshed = await db_session.get(Run, "run-gm-init")
    assert refreshed.graph_id == engine._graph_id

    # Graph + location entities created
    graph = (await db_session.execute(
        select(GraphModel).where(GraphModel.graph_id == engine._graph_id)
    )).scalars().first()
    assert graph is not None
    assert graph.name == f"emotionsim-run-{engine.run_id[:8]}"

    # Location entity mapping persisted in world state
    entity_ids = engine.world_state.get("_graph_entity_ids", {})
    assert "Town Square" in entity_ids
    assert "Hill" in entity_ids

    # Human agents got GraphMemory with the location mapping registered
    human = next(a for a in engine.agents.values() if a.role == "human")
    assert isinstance(human.graph_memory, GraphMemory)
    assert human.graph_memory.entity_id_for("Town Square") == entity_ids["Town Square"]


@pytest.mark.asyncio
async def test_engine_reuses_graph_on_resume(db_session):
    """load_from_db() reuses the run's existing graph and re-attaches memory."""
    run = Run(id="run-gm-resume", scenario_id="scenario-gm", status=RunStatus.PENDING)
    db_session.add(run)
    await db_session.commit()

    with patch(
        "emotionsim.simulation.engine.get_settings",
        return_value=Settings(graph_memory_enabled=True),
    ):
        engine1 = SimulationEngine(run_id="run-gm-resume", db_session=db_session)
        with patch("emotionsim.simulation.engine.LLMRouter") as mock_router:
            mock_router.get_client.return_value = MagicMock()
            await engine1.initialize(_scenario_config())

        graph_id = engine1._graph_id
        assert graph_id is not None

        # New engine instance simulating a backend restart
        engine2 = SimulationEngine(run_id="run-gm-resume", db_session=db_session)
        await engine2.load_from_db()

    assert engine2._graph_id == graph_id
    assert engine2.world_state.get("_graph_entity_ids") == engine1.world_state.get("_graph_entity_ids")
    human = next(a for a in engine2.agents.values() if a.role == "human")
    assert isinstance(human.graph_memory, GraphMemory)
    assert human.graph_memory.graph_id == graph_id


@pytest.mark.asyncio
async def test_engine_skips_graph_memory_when_disabled(db_session):
    """With the flag off, agents keep flat memory and no graph is created."""
    run = Run(id="run-gm-off", scenario_id="scenario-gm", status=RunStatus.PENDING)
    db_session.add(run)
    await db_session.commit()

    with patch(
        "emotionsim.simulation.engine.get_settings",
        return_value=Settings(graph_memory_enabled=False),
    ):
        engine = SimulationEngine(run_id="run-gm-off", db_session=db_session)
        with patch("emotionsim.simulation.engine.LLMRouter") as mock_router:
            mock_router.get_client.return_value = MagicMock()
            await engine.initialize(_scenario_config())

    assert engine._graph_id is None
    human = next(a for a in engine.agents.values() if a.role == "human")
    assert human.graph_memory is None
    refreshed = await db_session.get(Run, "run-gm-off")
    assert refreshed.graph_id is None


# ---------------------------------------------------------------------------
# Relevance recall (core done-criteria test)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_relevance_recall_surfaces_memory_from_ten_steps_ago(db_session):
    """A memory from step 1 surfaces at step 12 when the situation matches it —
    recall is relevance-based, not recency-based."""
    storage = OracleGraphStorage(session=db_session, embedding_service=None)
    graph_id = await storage.create_graph("recall-test")
    eid_bridge = await storage.add_entity(
        graph_id, Entity(name="Maple Street Bridge", type="location")
    )
    eid_gym = await storage.add_entity(
        graph_id, Entity(name="Gym", type="location")
    )

    agent = HumanAgent(name="Test Agent", persona=_make_persona(location="Maple Street Bridge"))
    agent.graph_memory = GraphMemory(
        agent_id=agent.id,
        agent_name=agent.name,
        run_id="run-recall",
        graph_id=graph_id,
        storage=storage,
        embedding_service=None,
    )
    agent.graph_memory.register_entity("Maple Street Bridge", eid_bridge)
    agent.graph_memory.register_entity("Gym", eid_gym)

    # Old, highly relevant observation from step 1
    await agent.graph_memory.store(
        content="The old Maple Street bridge collapsed during the flood and is impassable.",
        memory_type="observation",
        importance=8,
        step_number=1,
        linked_entity_ids=[eid_bridge],
    )
    # Recent but irrelevant decisions (steps 8-12)
    for step in range(8, 13):
        await agent.graph_memory.store(
            content=f"Step {step}: I found a flashlight in the gym and shared food with Maria.",
            memory_type="decision",
            importance=5,
            step_number=step,
            linked_entity_ids=[eid_gym],
        )

    # Agent is now AT the bridge >10 steps later
    agent.dynamic_state["location"] = "Maple Street Bridge"
    world_state = {
        "hazard_level": 7,
        "locations": {
            "Maple Street Bridge": {
                "description": "A damaged bridge",
                "nearby": ["Hill"],
            }
        },
    }
    context = await agent._recall_graph_context(world_state, messages=[])

    # The old memory surfaced because it matches the situation...
    assert "bridge collapsed" in context
    # ...and it ranks ABOVE the recent unrelated memories (relevance over recency)
    assert context.index("bridge collapsed") < context.index("flashlight")


@pytest.mark.asyncio
async def test_no_graph_memory_returns_empty_context():
    """Agents without GraphMemory get no graph context block (flat path)."""
    agent = HumanAgent(name="Test Agent", persona=_make_persona())
    assert agent.graph_memory is None
    context = await agent._recall_graph_context({"hazard_level": 3}, messages=[])
    assert context == ""


# ---------------------------------------------------------------------------
# Graceful fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embedding_failure_degrades_gracefully(db_session):
    """When embeddings are unavailable, store/recall still work (keyword fallback)."""
    failing_emb = MagicMock(spec=EmbeddingService)
    failing_emb.embed_text = AsyncMock(side_effect=RuntimeError("Ollama down"))
    failing_emb.embed_batch = AsyncMock(side_effect=RuntimeError("Ollama down"))

    storage = OracleGraphStorage(session=db_session, embedding_service=failing_emb)
    graph_id = await storage.create_graph("gf-test")

    agent = HumanAgent(name="Test Agent", persona=_make_persona())
    agent.graph_memory = GraphMemory(
        agent_id=agent.id,
        agent_name=agent.name,
        run_id="run-gf",
        graph_id=graph_id,
        storage=storage,
        embedding_service=failing_emb,
    )
    agent.dynamic_state["location"] = "Town Square"

    memory_id = await agent.graph_memory.store(
        content="The water reached the steps of the town hall.",
        memory_type="observation",
        importance=7,
        step_number=3,
    )
    assert memory_id is not None

    # Recall must not raise even though embeddings fail
    context = await agent._recall_graph_context(
        {"hazard_level": 5, "locations": {}}, messages=[]
    )
    assert isinstance(context, str)

    # Decision storage must not raise either
    from emotionsim.schemas.agent import AgentMessage, AgentResponse
    response = AgentResponse(
        actions=[],
        message=AgentMessage(content="Stay calm!", to_target="broadcast", message_type="broadcast"),
        state_changes={"stress_level": 6},
        reasoning="",
    )
    await agent._store_graph_memories(response, current_step=4, step_events=["A wave hits the docks"])
    assert len(agent._graph_seen_events) == 1


# ---------------------------------------------------------------------------
# Full engine run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_engine_run_persists_linked_graph_memories(db_session):
    """A full 2-step run with graph memory enabled stores decision nodes
    linked to location entities, and includes recalled context in prompts."""
    run = Run(id="run-gm-run", scenario_id="scenario-gm", status=RunStatus.PENDING)
    db_session.add(run)
    await db_session.commit()

    with patch(
        "emotionsim.simulation.engine.get_settings",
        return_value=Settings(graph_memory_enabled=True, scene_mode=False),
    ):
        engine = SimulationEngine(run_id="run-gm-run", db_session=db_session)
        with patch("emotionsim.simulation.engine.LLMRouter") as mock_router:
            mock_router.get_client.return_value = MagicMock()
            await engine.initialize(_scenario_config(max_steps=2))

    # Deterministic ticks: every agent responds every step
    for agent in engine.agents.values():
        agent.should_respond = lambda *a, **k: True

    captured_prompts: list[str] = []

    def _mock_generate_capture(**kwargs):
        captured_prompts.append(kwargs.get("system", "") + "\n" + str(kwargs.get("messages", "")))
        return _mock_generate(**kwargs)

    with patch(
        "emotionsim.agents.human.LLMRouter.generate_with_fallback",
        AsyncMock(side_effect=_mock_generate_capture),
    ), patch(
        "emotionsim.agents.base.LLMRouter.generate_with_fallback",
        AsyncMock(side_effect=_mock_generate_capture),
    ):
        await engine.start()

    assert engine.current_step == 2
    refreshed = await db_session.get(Run, "run-gm-run")
    assert refreshed.graph_id is not None

    # Graph memory nodes persisted
    result = await db_session.execute(
        select(MemoryNodeModel).where(MemoryNodeModel.run_id == "run-gm-run")
    )
    mems = result.scalars().all()
    assert len(mems) >= 2  # at least one decision per step
    assert any(m.memory_type == "decision" for m in mems)

    # Decisions linked to location entities via memory edges
    mem_ids = [m.memory_id for m in mems]
    edges = (await db_session.execute(
        select(MemoryEdgeModel).where(MemoryEdgeModel.source_id.in_(mem_ids))
    )).scalars().all()
    assert len(edges) >= 1
    assert all(e.type == "linked_entity" for e in edges)

    # Act-phase prompts include recalled graph context on later steps
    assert any("Relevant memories:" in p for p in captured_prompts)
