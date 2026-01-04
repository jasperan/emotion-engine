"""Conversation database model"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime, JSON, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.run import Run


class ConversationModel(Base):
    """Persisted conversation record"""
    
    __tablename__ = "conversations"
    
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
    
    # Conversation location and type
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    conversation_type: Mapped[str] = mapped_column(String(50), default="location")
    
    # Participants (list of agent IDs)
    participants: Mapped[list] = mapped_column(JSON, default=list)
    
    # State
    state: Mapped[str] = mapped_column(String(50), default="active")
    
    # Summary (for long-term memory)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Key facts extracted from conversation
    key_facts: Mapped[list] = mapped_column(JSON, default=list)
    
    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )
    
    # Step range
    start_step: Mapped[int | None] = mapped_column(nullable=True)
    end_step: Mapped[int | None] = mapped_column(nullable=True)
    
    # Metadata (using conv_metadata to avoid SQLAlchemy reserved name)
    conv_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Relationships
    run: Mapped["Run"] = relationship(
        "Run",
        back_populates="conversations"
    )

