from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import uuid
import time


class AgentStatus(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"
    STUCK = "stuck"
    AWAY = "away"


class ChannelType(str, Enum):
    DIRECT = "direct"
    BROADCAST = "broadcast"

    @staticmethod
    def room(name: str) -> str:
        return f"room:{name}"

    @staticmethod
    def parse_room(channel: str) -> str | None:
        return channel.split(":", 1)[1] if channel.startswith("room:") else None


@dataclass
class PersonalityProfile:
    """Big Five personality traits (1-10) + emotional state."""
    openness: int = 5
    conscientiousness: int = 5
    extraversion: int = 5
    agreeableness: int = 5
    neuroticism: int = 5
    risk_tolerance: int = 5
    empathy_level: int = 5
    leadership: int = 5
    stress: int = 0
    confidence: float = 0.5
    engagement: int = 5
    communication_style: str = "balanced"

    @classmethod
    def from_persona(cls, persona) -> "PersonalityProfile":
        """Create from an emotion-engine Persona object, centralizing the field mapping."""
        return cls(
            openness=getattr(persona, 'openness', 5),
            conscientiousness=getattr(persona, 'conscientiousness', 5),
            extraversion=getattr(persona, 'extraversion', 5),
            agreeableness=getattr(persona, 'agreeableness', 5),
            neuroticism=getattr(persona, 'neuroticism', 5),
            risk_tolerance=getattr(persona, 'risk_tolerance', 5),
            empathy_level=getattr(persona, 'empathy_level', 5),
            leadership=getattr(persona, 'leadership', 5),
            stress=getattr(persona, 'stress_level', 0),
            confidence=0.5,
        )


@dataclass
class AgentIdentity:
    name: str
    role: str
    status: str = "active"
    personality: PersonalityProfile | None = None
    capabilities: list[str] = field(default_factory=list)
    last_active: float = field(default_factory=time.time)


@dataclass
class ACPMessage:
    sender: AgentIdentity
    channel: str
    msg_type: str
    payload: dict[str, Any]
    recipient: str | None = None
    coordination_level: str = "moderate"
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
