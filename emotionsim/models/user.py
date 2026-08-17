"""User accounts for optional multi-tenant API access.

Auth is *optional by design*: the simulation CLI, TUI and eval harness run
without keys against public data (legacy behavior preserved). When an API key
is presented, the request is scoped to that user's tenant — they see and own
their scenarios/runs plus everything public.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from emotionsim.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # One API key per user (rotate = regenerate).
    api_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    @property
    def tenant_id(self) -> str:
        return self.id
