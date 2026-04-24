import random
from collections import defaultdict
from .message import AgentIdentity


class CoordinationController:
    LEVELS = {
        "none": {"probability": 0.0, "max_messages": 0},
        "minimal": {"probability": 0.3, "max_messages": 2},
        "moderate": {"probability": 0.6, "max_messages": 5},
        "chatty": {"probability": 0.9, "max_messages": 10},
    }

    def __init__(self, level: str = "moderate"):
        if level not in self.LEVELS:
            raise ValueError(f"Invalid level: {level}")
        self.level = level
        self._message_counts: dict[tuple[str, str], int] = defaultdict(int)

    def should_communicate(self, agent: AgentIdentity, context: dict) -> bool:
        base_prob = self.LEVELS[self.level]["probability"]
        if base_prob == 0.0:
            return False
        if agent.personality:
            modifier = agent.personality.extraversion / 5.0
            base_prob = min(1.0, base_prob * modifier)
        return random.random() < base_prob

    def can_send_more(self, agent_name: str, round_id: str) -> bool:
        sent = self._message_counts[(agent_name, round_id)]
        return sent < self.LEVELS[self.level]["max_messages"]

    def record_message(self, agent_name: str, round_id: str) -> None:
        self._message_counts[(agent_name, round_id)] += 1

    def get_max_messages(self) -> int:
        return self.LEVELS[self.level]["max_messages"]

    def reset_round(self, round_id: str) -> None:
        keys_to_remove = [k for k in self._message_counts if k[1] == round_id]
        for k in keys_to_remove:
            del self._message_counts[k]
