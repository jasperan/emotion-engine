"""SQLAlchemy models for hierarchical goal persistence."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import String, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from emotionsim.core.database import Base, OracleJSON


class GoalModel(Base):
    """A hierarchical goal within a simulation run."""

    __tablename__ = "goals"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("runs.id"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    goal_level: Mapped[str] = mapped_column(String(50), nullable=False)
    parent_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("goals.id"),
        nullable=True,
    )
    owner_ids: Mapped[list] = mapped_column(OracleJSON, default=list)
    status: Mapped[str] = mapped_column(String(50), default="active")
    priority: Mapped[int] = mapped_column(Integer, default=5)
    created_at_step: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_at_step: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    alignment_score: Mapped[float] = mapped_column(Float, default=1.0)
    conflict_with: Mapped[list] = mapped_column(OracleJSON, default=list)
