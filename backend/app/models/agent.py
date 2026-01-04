"""Agent database model"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.run import Run


class AgentModel(Base):
    """Agent instance within a run"""
    
    __tablename__ = "agents"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("runs.id"),
        nullable=False
    )
    
    # Agent identity
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # environment, human, designer
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # LLM configuration
    model_id: Mapped[str] = mapped_column(String(100), default="gemma3:270m")
    provider: Mapped[str] = mapped_column(String(50), default="ollama")
    
    # Persona configuration (for HumanAgent)
    persona: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Dynamic state that changes during simulation
    dynamic_state: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Memory snapshot (episodic memories, relationships)
    memory_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Relationship memory (tracked relationships with other agents)
    relationship_memory: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Agent status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )
    
    # Relationships
    run: Mapped["Run"] = relationship(
        "Run",
        back_populates="agents"
    )

