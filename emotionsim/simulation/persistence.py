"""RunPersistence: extracted persistence service for the simulation engine.

Removes Step / Run / Message writes and commits from the engine monolith so
``SimulationEngine`` stays focused on orchestration. Behavior is identical to
the inline logic it replaces (Step 7 refactor).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from emotionsim.models.message import Message, MessageType
from emotionsim.models.run import Run, RunStatus
from emotionsim.models.step import Step


class RunPersistence:
    """Persists simulation state: steps, run progress, messages, completion."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def save_step(
        self,
        run_id: str,
        step_index: int,
        world_state: dict[str, Any],
        actions: list[dict[str, Any]],
        step_metrics: dict[str, Any],
    ) -> None:
        """Queue a Step row for the given step."""
        self.db.add(Step(
            run_id=run_id,
            step_index=step_index,
            state_snapshot=world_state.copy(),
            actions=actions,
            step_metrics=step_metrics,
        ))

    async def update_run_progress(
        self,
        run_id: str,
        current_step: int,
        world_state: dict[str, Any],
    ) -> None:
        """Update the run's current step + world state snapshot."""
        run = await self.db.get(Run, run_id)
        if run:
            run.current_step = current_step
            run.world_state = world_state.copy()

    async def save_message(
        self,
        run_id: str,
        agent_id: str,
        msg: Any,
        step_index: int,
        conversation_id: str | None = None,
    ) -> None:
        """Persist a message row (equivalent to the engine's _persist_message)."""
        msg_type = msg.message_type if hasattr(msg, "message_type") else "broadcast"
        if conversation_id:
            msg_type = "conversation"

        try:
            db_msg_type = MessageType(msg_type)
        except ValueError:
            db_msg_type = MessageType.BROADCAST

        self.db.add(Message(
            run_id=run_id,
            from_agent_id=agent_id,
            to_target=conversation_id or msg.to_target,
            message_type=db_msg_type,
            content=msg.content,
            step_index=step_index,
            msg_metadata={"conversation_id": conversation_id} if conversation_id else {},
        ))

    async def complete_run(
        self,
        run_id: str,
        metrics: dict[str, Any],
        evaluation: dict[str, Any],
    ) -> None:
        """Mark the run completed and persist metrics + evaluation."""
        run = await self.db.get(Run, run_id)
        if run:
            run.status = RunStatus.COMPLETED
            run.completed_at = datetime.now(timezone.utc)
            run.metrics = metrics
            run.evaluation = evaluation
            await self.db.commit()

    async def commit(self) -> None:
        """Commit pending changes."""
        await self.db.commit()
