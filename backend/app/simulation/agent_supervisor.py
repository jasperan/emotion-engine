"""Agent Supervisor - Symphony-inspired per-agent fault isolation with exponential backoff"""
import asyncio
import logging
from typing import Any, Callable, Awaitable
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.schemas.agent import AgentResponse, AgentAction, AgentMessage

logger = logging.getLogger(__name__)


@dataclass
class AgentTelemetry:
    """Per-agent telemetry data for observability"""
    agent_id: str
    agent_name: str = ""
    tick_count: int = 0
    total_tick_duration_ms: float = 0.0
    last_tick_duration_ms: float = 0.0
    llm_tokens_used: int = 0
    actions_taken: Counter = field(default_factory=Counter)
    messages_sent: int = 0
    messages_received: int = 0
    conversations_active: int = 0
    staleness_score: float = 0.0
    retry_count: int = 0
    consecutive_failures: int = 0
    last_error: str | None = None
    last_error_time: datetime | None = None
    status: str = "healthy"  # healthy, recovering, degraded, failed

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "tick_count": self.tick_count,
            "avg_tick_duration_ms": (
                self.total_tick_duration_ms / max(self.tick_count, 1)
            ),
            "last_tick_duration_ms": self.last_tick_duration_ms,
            "llm_tokens_used": self.llm_tokens_used,
            "actions_taken": dict(self.actions_taken),
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "conversations_active": self.conversations_active,
            "staleness_score": self.staleness_score,
            "retry_count": self.retry_count,
            "consecutive_failures": self.consecutive_failures,
            "last_error": self.last_error,
            "status": self.status,
        }


class AgentSupervisor:
    """
    Symphony-inspired supervisor that wraps each agent tick with:
    - Timeout protection
    - Exponential backoff on failure
    - Per-agent telemetry
    - Graceful degradation (failed agents get "recovering" state)
    """

    def __init__(
        self,
        tick_timeout: float = 90.0,
        max_backoff: float = 300.0,
        initial_backoff: float = 10.0,
        max_consecutive_failures: int = 5,
    ):
        self.tick_timeout = tick_timeout
        self.max_backoff = max_backoff
        self.initial_backoff = initial_backoff
        self.max_consecutive_failures = max_consecutive_failures

        # Per-agent state
        self._telemetry: dict[str, AgentTelemetry] = {}
        self._retry_counts: dict[str, int] = {}
        self._backoff_until: dict[str, float] = {}  # agent_id -> asyncio time

    def register_agent(self, agent_id: str, agent_name: str = "") -> None:
        """Register an agent for supervision"""
        self._telemetry[agent_id] = AgentTelemetry(
            agent_id=agent_id, agent_name=agent_name
        )
        self._retry_counts[agent_id] = 0

    def get_telemetry(self, agent_id: str) -> AgentTelemetry | None:
        return self._telemetry.get(agent_id)

    def get_all_telemetry(self) -> dict[str, dict[str, Any]]:
        return {aid: t.to_dict() for aid, t in self._telemetry.items()}

    def is_agent_available(self, agent_id: str) -> bool:
        """Check if agent is available (not in backoff or permanently failed)"""
        telemetry = self._telemetry.get(agent_id)
        if not telemetry:
            return True

        if telemetry.status == "failed":
            return False

        # Check backoff timer
        backoff_until = self._backoff_until.get(agent_id, 0)
        if backoff_until > 0:
            loop = asyncio.get_event_loop()
            if loop.time() < backoff_until:
                return False
            # Backoff expired, clear it
            self._backoff_until.pop(agent_id, None)

        return True

    async def supervised_tick(
        self,
        agent: Any,
        world_state: dict[str, Any],
        messages: list[dict[str, Any]],
        step_actions: list[dict[str, Any]] | None = None,
        step_messages: list[dict[str, Any]] | None = None,
        step_events: list[str] | None = None,
        stream_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> AgentResponse:
        """
        Execute an agent tick with supervision: timeout, retry tracking,
        and graceful degradation.
        """
        agent_id = agent.id
        telemetry = self._telemetry.get(agent_id)
        if not telemetry:
            self.register_agent(agent_id, getattr(agent, "name", agent_id))
            telemetry = self._telemetry[agent_id]

        # Track message count
        telemetry.messages_received += len(messages)

        start_time = asyncio.get_event_loop().time()

        try:
            response = await asyncio.wait_for(
                agent.tick(
                    world_state,
                    messages,
                    step_actions,
                    step_messages,
                    step_events,
                    stream_callback=stream_callback,
                ),
                timeout=self.tick_timeout,
            )

            # Success — update telemetry
            elapsed_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            telemetry.tick_count += 1
            telemetry.last_tick_duration_ms = elapsed_ms
            telemetry.total_tick_duration_ms += elapsed_ms
            telemetry.consecutive_failures = 0
            telemetry.status = "healthy"
            self._retry_counts[agent_id] = 0

            # Track actions
            for action in response.actions:
                telemetry.actions_taken[action.action_type] += 1
            if response.message:
                telemetry.messages_sent += 1

            # Track token usage from message metadata
            if response.message and response.message.metadata:
                tokens = response.message.metadata.get("context_size", 0)
                telemetry.llm_tokens_used += tokens

            return response

        except asyncio.TimeoutError:
            return self._handle_failure(
                agent_id, telemetry, f"Tick timed out after {self.tick_timeout}s"
            )
        except Exception as e:
            return self._handle_failure(agent_id, telemetry, str(e))

    def _handle_failure(
        self, agent_id: str, telemetry: AgentTelemetry, error: str
    ) -> AgentResponse:
        """Handle agent failure with exponential backoff"""
        self._retry_counts[agent_id] = self._retry_counts.get(agent_id, 0) + 1
        retries = self._retry_counts[agent_id]
        telemetry.consecutive_failures += 1
        telemetry.retry_count += 1
        telemetry.last_error = error
        telemetry.last_error_time = datetime.now(timezone.utc)

        # Calculate backoff
        backoff = min(
            self.initial_backoff * (2 ** (retries - 1)),
            self.max_backoff,
        )

        logger.warning(
            "Agent %s failed (attempt %d): %s. Backoff: %.1fs",
            agent_id, retries, error, backoff,
        )

        if telemetry.consecutive_failures >= self.max_consecutive_failures:
            telemetry.status = "failed"
            logger.error("Agent %s marked as failed after %d consecutive failures", agent_id, retries)
        else:
            telemetry.status = "recovering"

        return AgentResponse(
            actions=[AgentAction(action_type="wait", target=None, parameters={})],
            message=None,
            state_changes={"_supervisor_status": telemetry.status},
            reasoning=f"Agent recovering from error: {error} (attempt {retries})",
        )

    def reset_agent(self, agent_id: str) -> None:
        """Reset an agent's failure state (e.g., after manual intervention)"""
        self._retry_counts[agent_id] = 0
        self._backoff_until.pop(agent_id, None)
        telemetry = self._telemetry.get(agent_id)
        if telemetry:
            telemetry.consecutive_failures = 0
            telemetry.status = "healthy"
