"""
DatalakeLogger: hooks into SimulationEngine's on_event callback to log
everything to Oracle 26ai Free.

Usage:
    from app.datalake.logger import DatalakeLogger

    dl_logger = DatalakeLogger(run_id, scenario_name, model)
    # Pass dl_logger.on_event as the engine's on_event callback,
    # or chain it with the existing callback.
"""

import logging
from typing import Any, Dict, Optional

from app.datalake.store import SimulationStore

logger = logging.getLogger(__name__)


class DatalakeLogger:
    """
    Translates SimulationEngine on_event calls into datalake writes.

    Designed to be used as a decorator/wrapper around the engine's
    existing on_event callback so both WebSocket events and datalake
    writes happen together.
    """

    def __init__(
        self,
        run_id: str,
        scenario_name: str,
        model: str,
        scenario_id: Optional[str] = None,
        fallback_model: Optional[str] = None,
        seed: Optional[int] = None,
        run_config: Optional[Dict] = None,
        store: Optional[SimulationStore] = None,
    ):
        self.run_id = run_id
        self.store = store or SimulationStore()
        self._current_step = 0
        self._event_buffer: list[Dict[str, Any]] = []
        self._buffer_size = 20

        try:
            self.store.create_run(
                run_id=run_id,
                scenario_name=scenario_name,
                model=model,
                scenario_id=scenario_id,
                fallback_model=fallback_model,
                seed=seed,
                run_config=run_config,
            )
        except Exception as e:
            logger.warning("Failed to create datalake run: %s", e)

    def on_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Handle an engine event. Call this from the engine's on_event.

        Maps engine event types to datalake operations:
        - step_completed -> log_step + flush buffered events
        - message -> buffer agent event
        - agent_error -> buffer agent event
        - agent_moved/travel_started/movement_failed -> buffer agent event
        - run_completed/run_stopped -> complete_run + flush
        - consensus_reached -> buffer + log metric
        - task_proposed/task_accepted -> buffer agent event
        """
        try:
            self._dispatch(event_type, data)
        except Exception as e:
            logger.warning("Datalake log error for %s: %s", event_type, e)

    def _dispatch(self, event_type: str, data: Dict[str, Any]) -> None:
        step = data.get("step", self._current_step)

        if event_type == "initialized":
            agent_count = data.get("agent_count", 0)
            try:
                self.store.log_metric(self.run_id, "agent_count", float(agent_count))
            except Exception:
                pass

        elif event_type == "step_completed":
            self._current_step = step
            # Log step
            world_state = data.get("world_state", {})
            messages = data.get("messages", [])
            actions = data.get("actions", [])
            active_agents = len(world_state.get("agents", {}))

            self.store.log_step(
                run_id=self.run_id,
                step_number=step,
                world_state=world_state,
                active_agents=active_agents,
                messages_count=len(messages),
            )

            # Log any actions as events
            for action in actions:
                self._buffer_event(
                    step_number=step,
                    agent_name=action.get("agent", "unknown"),
                    event_type="action",
                    data=action,
                )

            # Flush buffered events
            self._flush_buffer()

        elif event_type == "message":
            self._buffer_event(
                step_number=step,
                agent_name=data.get("from_agent", data.get("agent", "unknown")),
                event_type="message",
                data=data,
            )

        elif event_type in ("agent_error",):
            self._buffer_event(
                step_number=step,
                agent_name=data.get("agent", "unknown"),
                event_type="agent_error",
                data=data,
            )

        elif event_type in ("agent_moved", "travel_started", "agent_travelling",
                            "movement_failed", "agent_rerouted", "location_created"):
            self._buffer_event(
                step_number=step,
                agent_name=data.get("agent", "unknown"),
                event_type=event_type,
                data=data,
            )

        elif event_type in ("task_proposed", "task_accepted"):
            self._buffer_event(
                step_number=step,
                agent_name=data.get("agent", data.get("proposed_by", "unknown")),
                event_type=event_type,
                data=data,
            )

        elif event_type == "consensus_reached":
            self._buffer_event(
                step_number=step,
                agent_name="system",
                event_type="consensus_reached",
                data=data,
            )
            try:
                self.store.log_metric(
                    self.run_id, "consensus_step", float(step), step_number=step
                )
            except Exception:
                pass

        elif event_type in ("run_completed", "run_stopped"):
            self._flush_buffer()
            status = "completed" if event_type == "run_completed" else "cancelled"
            final_metrics = data.get("evaluation") or data.get("metrics")
            self.store.complete_run(
                run_id=self.run_id,
                total_steps=step,
                final_metrics=final_metrics,
                status=status,
            )

        elif event_type == "run_started":
            self._current_step = step

    def _buffer_event(
        self,
        step_number: int,
        agent_name: str,
        event_type: str,
        data: Any,
    ) -> None:
        """Buffer an event for batch write."""
        self._event_buffer.append({
            "step_number": step_number,
            "agent_name": agent_name,
            "event_type": event_type,
            "data": data,
        })
        if len(self._event_buffer) >= self._buffer_size:
            self._flush_buffer()

    def _flush_buffer(self) -> None:
        """Write all buffered events to the datalake."""
        if not self._event_buffer:
            return
        batch = list(self._event_buffer)
        self._event_buffer.clear()
        try:
            self.store.log_events_batch(self.run_id, batch)
        except Exception as e:
            logger.warning("Failed to flush %d events: %s", len(batch), e)

    def log_agent_plan(
        self,
        agent_name: str,
        step_number: int,
        goal: str,
        steps: list[str],
        current_step: int,
        status: str = "active",
    ) -> None:
        """Log a cognitive plan snapshot (called externally by engine)."""
        try:
            self.store.log_plan(
                run_id=self.run_id,
                step_number=step_number,
                agent_name=agent_name,
                goal=goal,
                steps=steps,
                current_step=current_step,
                status=status,
            )
        except Exception as e:
            logger.warning("Failed to log plan for %s: %s", agent_name, e)

    def close(self) -> None:
        """Flush remaining events and close store."""
        self._flush_buffer()
        self.store.close()
