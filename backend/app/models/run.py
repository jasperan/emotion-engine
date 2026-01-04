"""Run database model"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from enum import Enum

from sqlalchemy import String, Integer, DateTime, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.scenario import Scenario
    from app.models.agent import AgentModel
    from app.models.step import Step
    from app.models.message import Message
    from app.models.conversation import ConversationModel


class RunStatus(str, Enum):
    """Run status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Run(Base):
    """A single simulation run of a scenario"""
    
    __tablename__ = "runs"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    scenario_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("scenarios.id"),
        nullable=False
    )
    
    # Run state
    status: Mapped[RunStatus] = mapped_column(
        SQLEnum(RunStatus),
        default=RunStatus.PENDING
    )
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    max_steps: Mapped[int] = mapped_column(Integer, default=100)
    
    # Random seed for reproducibility
    seed: Mapped[int] = mapped_column(Integer, nullable=True)
    
    # World state JSON
    world_state: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Metrics and evaluation results
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    evaluation: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    scenario: Mapped["Scenario"] = relationship(
        "Scenario",
        back_populates="runs"
    )
    agents: Mapped[list["AgentModel"]] = relationship(
        "AgentModel",
        back_populates="run",
        cascade="all, delete-orphan"
    )
    steps: Mapped[list["Step"]] = relationship(
        "Step",
        back_populates="run",
        cascade="all, delete-orphan"
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="run",
        cascade="all, delete-orphan"
    )
    conversations: Mapped[list["ConversationModel"]] = relationship(
        "ConversationModel",
        back_populates="run",
        cascade="all, delete-orphan"
    )

