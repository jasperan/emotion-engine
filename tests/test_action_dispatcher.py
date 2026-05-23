from types import SimpleNamespace

import pytest

from emotionsim.simulation.action_dispatcher import AgentActionDispatcher
from emotionsim.simulation.engine import SimulationEngine


class StubAction:
    def __init__(
        self,
        action_type: str,
        target: str | None = None,
        parameters: dict | None = None,
    ) -> None:
        self.action_type = action_type
        self.target = target
        self.parameters = parameters or {}

    def model_dump(self) -> dict:
        return {
            "action_type": self.action_type,
            "target": self.target,
            "parameters": self.parameters,
        }


class StubCoordinator:
    def __init__(self) -> None:
        self.tracked_actions: list[tuple[str, str, str | None]] = []

    def track_action(self, agent_id: str, action_type: str, target: str | None) -> None:
        self.tracked_actions.append((agent_id, action_type, target))


class StubDiffTracker:
    def __init__(self) -> None:
        self.movements: list[tuple[str, str, str]] = []

    def record_movement(self, agent_id: str, old_loc: str, new_loc: str) -> None:
        self.movements.append((agent_id, old_loc, new_loc))


class StubRuntime:
    def __init__(self, movement_result: bool = True) -> None:
        self.coordinator = StubCoordinator()
        self.diff_tracker = StubDiffTracker()
        self._agent_locations = {"agent-1": "bridge"}
        self.movement_result = movement_result
        self.movement_calls: list[tuple[str, str | None, dict]] = []
        self.propose_task_calls: list[tuple[str, dict]] = []

    async def _handle_movement(
        self,
        agent_id: str,
        target: str | None,
        parameters: dict,
    ) -> bool:
        self.movement_calls.append((agent_id, target, parameters))
        return self.movement_result

    def _handle_propose_task(self, agent_id: str, params: dict) -> None:
        self.propose_task_calls.append((agent_id, params))


@pytest.mark.asyncio
async def test_successful_move_records_movement_then_logs_action() -> None:
    runtime = StubRuntime(movement_result=True)
    dispatcher = AgentActionDispatcher(runtime)
    action = StubAction("move", target="shelter", parameters={"speed": "careful"})
    agent = SimpleNamespace(name="Avery")
    step_actions: list[dict] = []

    await dispatcher.process("agent-1", agent, action, step_actions, [], False, None)

    assert runtime.movement_calls == [("agent-1", "shelter", {"speed": "careful"})]
    assert runtime.diff_tracker.movements == [("agent-1", "bridge", "shelter")]
    assert step_actions == [
        {
            "agent_id": "agent-1",
            "agent_name": "Avery",
            "action_type": "move",
            "target": "shelter",
            "parameters": {"speed": "careful"},
        }
    ]
    assert runtime.coordinator.tracked_actions == [("agent-1", "move", "shelter")]


@pytest.mark.asyncio
async def test_failed_move_is_not_logged_or_tracked() -> None:
    runtime = StubRuntime(movement_result=False)
    dispatcher = AgentActionDispatcher(runtime)
    action = StubAction("move", target="unknown")
    step_actions: list[dict] = []

    await dispatcher.process(
        "agent-1",
        SimpleNamespace(name="Avery"),
        action,
        step_actions,
        [],
        False,
        None,
    )

    assert runtime.movement_calls == [("agent-1", "unknown", {})]
    assert runtime.diff_tracker.movements == []
    assert step_actions == []
    assert runtime.coordinator.tracked_actions == []


@pytest.mark.asyncio
async def test_unknown_action_still_logs_and_tracks_action() -> None:
    runtime = StubRuntime()
    dispatcher = AgentActionDispatcher(runtime)
    action = StubAction("wait", parameters={"reason": "listening"})
    step_actions: list[dict] = []

    await dispatcher.process(
        "agent-1",
        SimpleNamespace(name="Avery"),
        action,
        step_actions,
        [],
        False,
        None,
    )

    assert step_actions == [
        {
            "agent_id": "agent-1",
            "agent_name": "Avery",
            "action_type": "wait",
            "target": None,
            "parameters": {"reason": "listening"},
        }
    ]
    assert runtime.coordinator.tracked_actions == [("agent-1", "wait", None)]


@pytest.mark.asyncio
async def test_sync_handler_invoked_before_logging() -> None:
    runtime = StubRuntime()
    dispatcher = AgentActionDispatcher(runtime)
    action = StubAction("propose_task", parameters={"task_id": "clear-hall"})
    step_actions: list[dict] = []

    await dispatcher.process(
        "agent-1",
        SimpleNamespace(name="Avery"),
        action,
        step_actions,
        [],
        False,
        None,
    )

    assert runtime.propose_task_calls == [("agent-1", {"task_id": "clear-hall"})]
    assert step_actions[0]["action_type"] == "propose_task"
    assert runtime.coordinator.tracked_actions == [("agent-1", "propose_task", None)]


@pytest.mark.asyncio
async def test_engine_process_action_lazily_creates_dispatcher() -> None:
    engine = SimulationEngine.__new__(SimulationEngine)
    engine.coordinator = StubCoordinator()
    engine.diff_tracker = StubDiffTracker()
    engine._agent_locations = {"agent-1": "bridge"}
    engine._handle_movement = StubRuntime()._handle_movement

    action = StubAction("move", target="shelter")
    step_actions: list[dict] = []

    await SimulationEngine._process_agent_action(
        engine,
        "agent-1",
        SimpleNamespace(name="Avery"),
        action,
        step_actions,
        [],
        False,
        None,
    )

    assert isinstance(engine.action_dispatcher, AgentActionDispatcher)
    assert step_actions[0]["action_type"] == "move"
    assert engine.coordinator.tracked_actions == [("agent-1", "move", "shelter")]
