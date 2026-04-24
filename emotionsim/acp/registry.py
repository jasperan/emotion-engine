import time
from .message import AgentIdentity, AgentStatus


class AgentRegistry:
    def __init__(self):
        self.agents: dict[str, AgentIdentity] = {}

    def register(self, agent: AgentIdentity) -> None:
        self.agents[agent.name] = agent

    def deregister(self, name: str) -> None:
        self.agents.pop(name, None)

    def get_active(self) -> list[AgentIdentity]:
        return [a for a in self.agents.values() if a.status == AgentStatus.ACTIVE]

    def get_by_role(self, role: str) -> list[AgentIdentity]:
        return [a for a in self.agents.values() if a.role == role]

    def get_by_capability(self, capability: str) -> list[AgentIdentity]:
        return [a for a in self.agents.values() if capability in a.capabilities]

    def update_status(self, name: str, status: str) -> None:
        if name in self.agents:
            self.agents[name].status = status

    def touch(self, name: str) -> None:
        if name in self.agents:
            self.agents[name].last_active = time.time()

    def detect_stuck(self, threshold_seconds: int = 900) -> list[str]:
        now = time.time()
        return [
            name for name, agent in self.agents.items()
            if (now - agent.last_active) > threshold_seconds
        ]
