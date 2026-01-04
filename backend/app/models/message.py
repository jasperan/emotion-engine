"""Message database model"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from enum import Enum

from sqlalchemy import String, Integer, Text, DateTime, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.run import Run


class MessageType(str, Enum):
    """Message type enumeration"""
    DIRECT = "direct"          # Agent to agent
    ROOM = "room"              # To a room/group
    BROADCAST = "broadcast"    # To all agents
    SYSTEM = "system"          # System/environment message
    CONVERSATION = "conversation"  # To conversation participants


class Message(Base):
    """Message exchanged between agents"""
    
    __tablename__ = "messages"
    
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
    
    # Message routing
    from_agent_id: Mapped[str] = mapped_column(String(36), nullable=True)  # Null for system
    to_target: Mapped[str] = mapped_column(String(255), nullable=False)  # Agent ID, room name, or "broadcast"
    message_type: Mapped[MessageType] = mapped_column(
        SQLEnum(MessageType),
        default=MessageType.DIRECT
    )
    
    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Additional metadata (using msg_metadata to avoid SQLAlchemy reserved name)
    msg_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Step context
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Timestamp
    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )
    
    # Relationships
    run: Mapped["Run"] = relationship(
        "Run",
        back_populates="messages"
    )

