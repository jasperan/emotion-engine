"""Action dispatch for simulation agents."""

from collections.abc import Awaitable, Callable
from typing import Any


AsyncActionHandler = Callable[[str, Any], Awaitable[bool]]
SyncActionHandler = Callable[[str, Any], bool]


class AgentActionDispatcher:
    """Dispatch agent actions to the simulation runtime handlers."""

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime
        self._async_handlers: dict[str, AsyncActionHandler] = {
            "move": self._handle_move,
            "take": self._handle_take,
            "drop": self._handle_drop,
            "use": self._handle_use,
            "interact": self._handle_interact,
            "search": self._handle_search,
        }
        self._sync_handlers: dict[str, SyncActionHandler] = {
            "propose_task": self._handle_propose_task,
            "accept_task": self._handle_accept_task,
            "report_progress": self._handle_report_progress,
            "call_for_vote": self._handle_call_for_vote,
            "propose": self._handle_propose,
            "accept_proposal": self._handle_accept_proposal,
            "reject_proposal": self._handle_reject_proposal,
            "counter_propose": self._handle_counter_propose,
            "withdraw_proposal": self._handle_withdraw_proposal,
            "vouch_for": self._handle_vouch_for,
            "share_plan": self._handle_share_plan,
            "coordinate": self._handle_coordinate,
            "delegate_task": self._handle_delegate_task,
            "explore": self._handle_explore,
        }

    async def process(
        self,
        agent_id: str,
        agent: Any,
        action: Any,
        step_actions: list[dict[str, Any]],
        step_messages: list[dict[str, Any]],
        in_conversation: bool,
        conversation: Any,
    ) -> None:
        """Process an agent action and append it to the step action log."""
        del step_messages, in_conversation, conversation

        should_log = await self._dispatch(agent_id, action)
        if not should_log:
            return

        action_dict = {
            "agent_id": agent_id,
            "agent_name": agent.name,
            **action.model_dump(),
        }
        step_actions.append(action_dict)
        self.runtime.coordinator.track_action(agent_id, action.action_type, action.target)

    async def _dispatch(self, agent_id: str, action: Any) -> bool:
        async_handler = self._async_handlers.get(action.action_type)
        if async_handler is not None:
            return await async_handler(agent_id, action)

        sync_handler = self._sync_handlers.get(action.action_type)
        if sync_handler is not None:
            return sync_handler(agent_id, action)

        return True

    async def _handle_move(self, agent_id: str, action: Any) -> bool:
        success = await self.runtime._handle_movement(
            agent_id,
            action.target,
            action.parameters,
        )
        if success and action.target:
            old_loc = self.runtime._agent_locations.get(agent_id, "unknown")
            self.runtime.diff_tracker.record_movement(agent_id, old_loc, action.target)
        return bool(success)

    async def _handle_take(self, agent_id: str, action: Any) -> bool:
        await self.runtime._handle_take(agent_id, action.target)
        return True

    async def _handle_drop(self, agent_id: str, action: Any) -> bool:
        await self.runtime._handle_drop(agent_id, action.target)
        return True

    async def _handle_use(self, agent_id: str, action: Any) -> bool:
        await self.runtime._handle_use(agent_id, action.target)
        return True

    async def _handle_interact(self, agent_id: str, action: Any) -> bool:
        await self.runtime._handle_interact(agent_id, action.target, action.parameters)
        return True

    async def _handle_search(self, agent_id: str, action: Any) -> bool:
        del action
        await self.runtime._handle_search(agent_id)
        return True

    def _handle_propose_task(self, agent_id: str, action: Any) -> bool:
        self.runtime._handle_propose_task(agent_id, action.parameters)
        return True

    def _handle_accept_task(self, agent_id: str, action: Any) -> bool:
        self.runtime._handle_accept_task(agent_id, action.target, action.parameters)
        return True

    def _handle_report_progress(self, agent_id: str, action: Any) -> bool:
        self.runtime._handle_report_progress(agent_id, action.parameters)
        return True

    def _handle_call_for_vote(self, agent_id: str, action: Any) -> bool:
        self.runtime._handle_call_for_vote(agent_id, action.parameters)
        return True

    def _handle_propose(self, agent_id: str, action: Any) -> bool:
        self.runtime._handle_propose(agent_id, action.target, action.parameters)
        return True

    def _handle_accept_proposal(self, agent_id: str, action: Any) -> bool:
        self.runtime._handle_accept_proposal(agent_id, action.target, action.parameters)
        return True

    def _handle_reject_proposal(self, agent_id: str, action: Any) -> bool:
        self.runtime._handle_reject_proposal(agent_id, action.target, action.parameters)
        return True

    def _handle_counter_propose(self, agent_id: str, action: Any) -> bool:
        self.runtime._handle_counter_propose(agent_id, action.target, action.parameters)
        return True

    def _handle_withdraw_proposal(self, agent_id: str, action: Any) -> bool:
        self.runtime._handle_withdraw_proposal(agent_id, action.target)
        return True

    def _handle_vouch_for(self, agent_id: str, action: Any) -> bool:
        self.runtime._handle_vouch_for(agent_id, action.target, action.parameters)
        return True

    def _handle_share_plan(self, agent_id: str, action: Any) -> bool:
        self.runtime._handle_share_plan(agent_id, action.target)
        return True

    def _handle_coordinate(self, agent_id: str, action: Any) -> bool:
        self.runtime._handle_coordinate(agent_id, action.parameters)
        return True

    def _handle_delegate_task(self, agent_id: str, action: Any) -> bool:
        self.runtime._handle_delegate_task(agent_id, action.target, action.parameters)
        return True

    def _handle_explore(self, agent_id: str, action: Any) -> bool:
        self.runtime._handle_explore(agent_id, action.parameters)
        return True
