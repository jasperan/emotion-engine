"""SQLAlchemy models for governance audit log persistence."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import String, Integer, Float, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from emotionsim.core.database import Base, OracleJSON


class GovernanceAuditModel(Base):
    """An audit log entry for governance decisions."""

    __tablename__ = "governance_audit"

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
    agent_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action: Mapped[str] = mapped_column(String(500), nullable=False)
    reasoning: Mapped[str] = mapped_column(String(2000), nullable=False)
    step: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    categories: Mapped[list] = mapped_column(OracleJSON, default=list)
    significance: Mapped[float] = mapped_column(Float, default=0.0)
    approved: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    researcher_note: Mapped[str] = mapped_column(String(2000), default="")
