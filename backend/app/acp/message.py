from dataclasses import dataclass, field
from typing import Any
import uuid
import time


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
