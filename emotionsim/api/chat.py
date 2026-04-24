"""Post-simulation agent chat API.

Lets users chat with agents after a run completes, using the agent's
persona, Big Five traits, and graph memories to stay in character.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from emotionsim.core.database import get_db
from emotionsim.llm.base import LLMMessage
from emotionsim.llm.router import LLMRouter
from emotionsim.models.agent import AgentModel
from emotionsim.models.run import Run

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/runs/{run_id}/agents/{agent_id}",
    tags=["chat"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1)


class AgentChatResponse(BaseModel):
    agent_name: str
    response: str
    personality_context: str = ""
    memories_referenced: list[str] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BIG_FIVE_LABELS = {
    "openness": "Openness",
    "conscientiousness": "Conscientiousness",
    "extraversion": "Extraversion",
    "agreeableness": "Agreeableness",
    "neuroticism": "Neuroticism",
}


def _build_personality_context(persona: dict) -> str:
    """Extract Big Five traits from the persona dict and return a readable string."""
    traits = persona.get("personality_traits") or persona.get("traits") or {}
    if not traits:
        return ""
    parts: list[str] = []
    for key, label in BIG_FIVE_LABELS.items():
        value = traits.get(key)
        if value is not None:
            parts.append(f"{label}: {value}")
    return ", ".join(parts)


async def _try_recall_memories(
    run_row: Run,
    agent_row: AgentModel,
    query: str,
    db: AsyncSession,
) -> list[str]:
    """Try to recall memories via GraphMemory. Returns [] on any failure."""
    graph_id: Optional[str] = getattr(run_row, "graph_id", None)
    if not graph_id:
        return []

    try:
        from emotionsim.storage.oracle_graph_storage import OracleGraphStorage
        from emotionsim.storage.embedding_service import EmbeddingService
        from emotionsim.agents.graph_memory import GraphMemory

        embedding_svc = EmbeddingService()
        storage = OracleGraphStorage(session=db, embedding_service=embedding_svc)
        mem = GraphMemory(
            agent_id=agent_row.id,
            agent_name=agent_row.name,
            run_id=agent_row.run_id,
            graph_id=graph_id,
            storage=storage,
            embedding_service=embedding_svc,
        )
        results = await mem.recall(query, limit=5)
        return [r.get("content", "") for r in results if r.get("content")]
    except Exception:
        logger.debug("Memory recall failed, continuing without memories", exc_info=True)
        return []


def _build_system_prompt(
    persona: dict,
    personality_context: str,
    memories: list[str],
) -> str:
    """Build a system prompt that puts the LLM in character."""
    name = persona.get("name", "Unknown Agent")
    backstory = persona.get("backstory", "")
    occupation = persona.get("occupation", "")

    lines = [
        f"You are {name}, responding in character after a simulation has ended.",
    ]
    if occupation:
        lines.append(f"Occupation: {occupation}.")
    if backstory:
        lines.append(f"Backstory: {backstory}")
    if personality_context:
        lines.append(f"Personality (Big Five): {personality_context}.")
    if memories:
        lines.append("Relevant memories from the simulation:")
        for m in memories:
            lines.append(f"  - {m}")
    lines.append("Stay in character. Answer from this persona's perspective.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=AgentChatResponse)
async def chat_with_agent(
    run_id: str,
    agent_id: str,
    body: AgentChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Chat with an agent using its persona and simulation memories."""

    # 1. Load agent
    result = await db.execute(
        select(AgentModel).where(
            AgentModel.id == agent_id,
            AgentModel.run_id == run_id,
        )
    )
    agent_row = result.scalar_one_or_none()
    if agent_row is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    # 2. Load run
    result = await db.execute(select(Run).where(Run.id == run_id))
    run_row = result.scalar_one_or_none()
    if run_row is None:
        raise HTTPException(status_code=404, detail="Run not found")

    # 3. Build personality context
    persona: dict = agent_row.persona or {}
    personality_context = _build_personality_context(persona)

    # 4. Recall memories (best-effort)
    memories = await _try_recall_memories(run_row, agent_row, body.message, db)

    # 5. Build system prompt
    system_prompt = _build_system_prompt(persona, personality_context, memories)

    # 6. Call LLM
    client = LLMRouter.get_client()
    llm_response = await client.generate(
        messages=[LLMMessage(role="user", content=body.message)],
        system=system_prompt,
        temperature=0.7,
        max_tokens=1024,
    )

    # 7. Return response
    return AgentChatResponse(
        agent_name=agent_row.name,
        response=llm_response.content,
        personality_context=personality_context,
        memories_referenced=memories,
    )
