"""Dynamic agent spawning / departure (mid-run population change).

Disaster scenarios are not static: evacuees arrive at shelters as the hazard
worsens, and agents who are too injured or stressed leave the scene. This
module generates new human agents on triggers and identifies agents who should
depart.

Triggers (all gated behind ``DYNAMIC_SPAWNING_ENABLED``):
- **Interval**: every ``spawn_interval_steps`` steps, one new agent arrives
  (up to ``spawn_max_extra_agents``).
- **Surge**: when hazard_level >= 7, an extra evacuee arrives immediately.
- **Departure**: agents with health <= ``spawn_evict_health_threshold`` or
  stress >= ``spawn_evict_stress_threshold`` leave the simulation.

Determinism: persona/name choices come from a seeded ``random.Random``, so
the same seed produces the same arrivals. Off by default — the default path
is byte-identical to before.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

NAME_POOL = [
    "Marco", "Priya", "Jonas", "Fatima", "Omar", "Ingrid", "Diego", "Yuki",
    "Thabo", "Elena", "Ravi", "Sofia", "Kenji", "Amara", "Lucas", "Hana",
]

OCCUPATION_POOL = [
    "construction worker", "nurse", "school teacher", "fisher", "shopkeeper",
    "delivery driver", "paramedic", "volunteer", "mechanic", "farmer",
    "student", "retired firefighter", "electrician", "café owner",
]


@dataclass
class SpawnConfig:
    interval_steps: int = 3
    max_extra_agents: int = 5
    location: str = "shelter"
    evict_health_threshold: int = 1
    evict_stress_threshold: int = 9
    seed: int = 42
    surge_hazard: int = 7


class DynamicSpawner:
    """Seeded generator of mid-run agents + departure decisions."""

    def __init__(self, config: SpawnConfig | None = None) -> None:
        self.cfg = config or SpawnConfig()
        self.rng = random.Random(self.cfg.seed)
        self.spawned: list[str] = []
        self._used_names: set[str] = set()

    def _pick_name(self) -> str:
        for _ in range(20):
            name = self.rng.choice(NAME_POOL)
            if name not in self._used_names:
                self._used_names.add(name)
                return name
        return f"Evacuee {len(self.spawned) + 1}"

    def build_persona(self) -> dict[str, Any]:
        """A believable mid-crisis arrival: moderate stress, mid health."""
        return {
            "name": self._pick_name(),
            "age": self.rng.randint(20, 65),
            "occupation": self.rng.choice(OCCUPATION_POOL),
            "sex": self.rng.choice(["male", "female", "non-binary"]),
            "location": self.cfg.location,
            "extraversion": self.rng.randint(3, 8),
            "agreeableness": self.rng.randint(3, 9),
            "conscientiousness": self.rng.randint(3, 9),
            "neuroticism": self.rng.randint(4, 9),
            "openness": self.rng.randint(3, 8),
            "leadership": self.rng.randint(2, 7),
            "stress_level": self.rng.randint(4, 7),
            "health": self.rng.randint(5, 9),
            "goals": ["Find shelter", "Check on family", "Help if I can"],
        }

    def should_spawn(
        self,
        current_step: int,
        hazard: float,
        spawned_count: int,
    ) -> bool:
        """Interval + hazard-surge triggers."""
        if spawned_count >= self.cfg.max_extra_agents:
            return False
        if current_step > 0 and current_step % self.cfg.interval_steps == 0:
            return True
        return hazard >= self.cfg.surge_hazard and spawned_count < 1

    def should_evict(self, agent) -> bool:
        """Departure rule: too injured or too stressed to stay on scene."""
        state = getattr(agent, "dynamic_state", {}) or {}
        health = state.get("health", getattr(agent.persona, "health", 8))
        stress = state.get("stress_level", getattr(agent.persona, "stress_level", 5))
        return health <= self.cfg.evict_health_threshold or stress >= self.cfg.evict_stress_threshold