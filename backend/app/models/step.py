"""Step database model"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.run import Run


class Step(Base):
    """A single simulation step/tick"""
    
    __tablename__ = "steps"
    
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
    
    # Step index (0-based)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Complete world state snapshot at this step
    state_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Actions taken by agents in this step
    actions: Mapped[list] = mapped_column(JSON, default=list)
    
    # Metrics computed at this step
    step_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Timestamp
    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )
    
    # Relationships
    run: Mapped["Run"] = relationship(
        "Run",
        back_populates="steps"
    )

