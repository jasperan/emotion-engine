"""Tests for ACP Wave Controller."""
import pytest
from emotionsim.acp.wave_controller import WaveController, Task, WaveResult


class SimTask(Task):
    def __init__(self, task_id: str, result: str = "ok"):
        super().__init__(task_id=task_id)
        self._result = result

    async def execute(self):
        return self._result


@pytest.mark.asyncio
async def test_simulation_waves():
    """Tasks should execute in dependency order across waves."""
    ctrl = WaveController(max_waves=10)
    tasks = [
        SimTask("env_tick"),
        SimTask("human_a"),
        SimTask("human_b"),
        SimTask("evaluator"),
    ]

    ctrl.add_dependency("human_a", "env_tick")
    ctrl.add_dependency("human_b", "env_tick")
    ctrl.add_dependency("evaluator", "human_a")
    ctrl.add_dependency("evaluator", "human_b")

    waves = []
    async for wave in ctrl.execute_waves(tasks):
        waves.append(wave)

    assert len(waves) == 3

    # Wave 1: env_tick (no deps)
    assert waves[0].tasks[0].task_id == "env_tick"

    # Wave 2: human_a and human_b (depend on env_tick)
    wave2_ids = {t.task_id for t in waves[1].tasks}
    assert wave2_ids == {"human_a", "human_b"}

    # Wave 3: evaluator (depends on both humans)
    assert waves[2].tasks[0].task_id == "evaluator"


@pytest.mark.asyncio
async def test_empty_tasks():
    """Empty task list should produce no waves."""
    ctrl = WaveController()
    waves = []
    async for wave in ctrl.execute_waves([]):
        waves.append(wave)
    assert len(waves) == 0


@pytest.mark.asyncio
async def test_max_waves_limit():
    """Wave controller should respect max_waves limit."""
    ctrl = WaveController(max_waves=2)
    # Create a chain of 5 dependent tasks
    tasks = [SimTask(f"t{i}") for i in range(5)]
    for i in range(1, 5):
        ctrl.add_dependency(f"t{i}", f"t{i-1}")

    waves = []
    async for wave in ctrl.execute_waves(tasks):
        waves.append(wave)

    # Should stop at 2 waves even though more tasks remain
    assert len(waves) == 2


@pytest.mark.asyncio
async def test_clear_dependencies():
    """Clearing dependencies should allow all tasks in a single wave."""
    ctrl = WaveController()
    tasks = [SimTask("a"), SimTask("b"), SimTask("c")]
    ctrl.add_dependency("b", "a")
    ctrl.add_dependency("c", "b")

    ctrl.clear_dependencies()

    waves = []
    async for wave in ctrl.execute_waves(tasks):
        waves.append(wave)

    # All tasks should run in one wave since deps were cleared
    assert len(waves) == 1
    assert len(waves[0].tasks) == 3
