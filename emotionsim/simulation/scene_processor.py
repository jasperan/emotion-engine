"""SceneProcessor: location-scene orchestration (Step 7 refactor).

Moved verbatim from the engine monolith so ``SimulationEngine`` stays focused
on the tick loop. Uses the same "runtime back-reference" pattern as
AgentActionDispatcher.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


class SceneProcessor:
    """Groups co-located human agents into dramatic scenes each tick."""

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    async def run_single_scene(
        self,
        location: str,
        available: list[str],
        local_actions: list[dict[str, Any]],
        local_messages: list[dict[str, Any]],
        local_events: list[str],
        stream_callback: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> None:
        """Run a single scene at a location. Turns within are sequential."""
        rt = self.runtime
        if len(available) == 1:
            aid = available[0]
            agent = rt.agents[aid]
            await rt._tick_single_agent(aid, agent, local_actions, local_messages, local_events, stream_callback)
            return

        # Multi-agent scene: pick initiator by extraversion, order turns
        try:
            initiator_id = rt.scene_director.pick_initiator(available, rt.agents)
        except ValueError:
            return
        ordered = [initiator_id] + [a for a in available if a != initiator_id]
        turn_ids = ordered[:rt.scene_director.max_turns]

        # Inject scene context into world state so agents know who is present
        try:
            rt.world_state["_scene_location"] = location
            rt.world_state["_scene_participants"] = [
                rt.agents[aid].name for aid in available if aid in rt.agents
            ]

            for agent_id in turn_ids:
                agent = rt.agents[agent_id]
                msg_count_before = len(local_messages)

                await rt._tick_single_agent(
                    agent_id, agent, local_actions, local_messages, local_events, stream_callback
                )

                # Capture speech from any message sent during this turn
                speech: str | None = None
                if len(local_messages) > msg_count_before:
                    newest = local_messages[-1]
                    speech = newest.get("content")

                # Emit per-turn scene event
                rt.on_event("scene_turn", {
                    "location": location,
                    "agent_id": agent_id,
                    "agent_name": agent.name,
                    "action": getattr(agent, '_last_cinematic', {}).get("action", ""),
                    "speech": speech,
                    "thought": getattr(agent, '_last_cinematic', {}).get("thought", ""),
                    "emotion": getattr(agent, '_last_cinematic', {}).get("emotion", ""),
                    "step": rt.current_step,
                })

                # Update world state after each turn so next agent sees latest position
                rt._update_agents_in_world_state()

            # Emit scene_completed event
            rt.on_event("scene_completed", {
                "location": location,
                "participants": [rt.agents[aid].name for aid in available if aid in rt.agents],
                "turn_count": len(turn_ids),
                "step": rt.current_step,
            })
        finally:
            rt.world_state.pop("_scene_location", None)
            rt.world_state.pop("_scene_participants", None)

    async def _run_scene_isolated(
        self,
        location: str,
        available: list[str],
        local_actions: list[dict[str, Any]],
        local_messages: list[dict[str, Any]],
        local_events: list[str],
        stream_callback: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> tuple[list, list, list]:
        rt = self.runtime
        try:
            await self.run_single_scene(
                location, available, local_actions, local_messages, local_events, stream_callback
            )
        except Exception as e:
            logger.error(f"Scene at {location} failed: {e}")
            rt.on_event("agent_error", {
                "error": f"Scene at {location} failed: {e}",
                "step": rt.current_step,
                "context": "parallel_scene",
            })
        return local_actions, local_messages, local_events

    async def process_agents_as_scenes(
        self,
        step_actions: list[dict[str, Any]],
        step_messages: list[dict[str, Any]],
        step_events: list[str],
        stream_callback: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> None:
        """Process human agents as dramatic scenes grouped by location.

        Independent scenes at different locations run in parallel via
        asyncio.gather, leveraging vLLM's continuous batching for higher
        throughput. Within each scene, turns remain sequential so agents
        can react to prior speech.
        """
        rt = self.runtime
        settings = rt._settings

        # Build agent_locations dict from current tracking
        agent_locations = {
            agent_id: rt._agent_locations.get(agent_id, agent.dynamic_state.get("location", "unknown"))
            for agent_id, agent in rt.agents.items()
            if hasattr(agent, 'dynamic_state')
        }

        groups = rt.scene_director.group_agents_by_location(rt.agents, agent_locations)

        # Collect scenes to process
        scenes: list[tuple[str, list[str]]] = []
        for location, agent_ids in groups.items():
            available = [
                aid for aid in agent_ids
                if rt.supervisor.is_agent_available(aid)
            ]
            if available:
                scenes.append((location, available))

        if not scenes:
            return

        # Decide: parallel scenes if vLLM backend, sequential otherwise
        parallel_scenes = settings.llm_backend == "vllm" and len(scenes) > 1

        if parallel_scenes:
            tasks = [
                self._run_scene_isolated(loc, avail, [], [], [], stream_callback)
                for loc, avail in scenes
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Parallel scene raised: {result}")
                    continue
                local_actions, local_messages, local_events = result
                step_actions.extend(local_actions)
                step_messages.extend(local_messages)
                step_events.extend(local_events)
        else:
            # Sequential fallback (Ollama or single scene)
            for location, available in scenes:
                await self.run_single_scene(
                    location, available, step_actions, step_messages, step_events, stream_callback
                )
