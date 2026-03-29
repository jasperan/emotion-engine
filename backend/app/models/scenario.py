"""Scenario database model"""
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, OracleJSON

if TYPE_CHECKING:
    from app.models.run import Run


class Scenario(Base):
    """Scenario configuration for simulations"""

    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # Configuration JSON containing world parameters
    config: Mapped[dict] = mapped_column(OracleJSON, default=dict)

    # Agent templates for this scenario
    agent_templates: Mapped[list] = mapped_column(OracleJSON, default=list)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Knowledge graph reference
    graph_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Relationships
    runs: Mapped[list["Run"]] = relationship(
        "Run",
        back_populates="scenario",
        cascade="all, delete-orphan"
    )
