import asyncio
from dataclasses import dataclass
from typing import Any, AsyncIterator
from collections import defaultdict


@dataclass
class Task:
    task_id: str

    async def execute(self) -> Any:
        raise NotImplementedError


@dataclass
class WaveResult:
    wave: int
    tasks: list[Task]
    results: list[Any]


class WaveController:
    def __init__(self, max_waves: int = 10):
        self.max_waves = max_waves
        self.current_wave = 0
        self._dependencies: dict[str, list[str]] = defaultdict(list)

    def add_dependency(self, task_id: str, depends_on: str) -> None:
        self._dependencies[task_id].append(depends_on)

    def clear_dependencies(self) -> None:
        self._dependencies.clear()
        self.current_wave = 0

    async def execute_waves(self, tasks: list[Task]) -> AsyncIterator[WaveResult]:
        if not tasks:
            return
        task_map = {t.task_id: t for t in tasks}
        remaining = set(t.task_id for t in tasks)
        completed: set[str] = set()
        self.current_wave = 0

        while remaining and self.current_wave < self.max_waves:
            ready = [
                task_map[tid] for tid in remaining
                if all(dep in completed for dep in self._dependencies.get(tid, []))
            ]
            if not ready:
                break

            self.current_wave += 1
            results = await asyncio.gather(*[t.execute() for t in ready])
            for t in ready:
                remaining.discard(t.task_id)
                completed.add(t.task_id)

            yield WaveResult(
                wave=self.current_wave,
                tasks=ready,
                results=list(results),
            )
