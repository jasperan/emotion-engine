"""FastAPI auth dependency: optional tenant resolution from X-API-Key.

- With a valid key → ``TenantScope(tenant=user.id)``.
- Without a key → ``TenantScope(public=True)`` (legacy anonymous access).
- With an invalid key → 401 (never silently downgrade).

Scoping rules applied by the route handlers:
- tenant: sees own rows + rows with ``tenant_id IS NULL`` (public).
- public: sees only ``tenant_id IS NULL`` rows.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from emotionsim.auth.security import hash_api_key
from emotionsim.core.database import get_db
from emotionsim.models.user import User


@dataclass
class TenantScope:
    tenant: str | None = None  # user id when authenticated
    username: str | None = None

    @property
    def is_authenticated(self) -> bool:
        return self.tenant is not None


def tenant_visibility(scope: TenantScope):
    """SQLAlchemy filter for tenant-scoped reads: own + public for tenants,
    public-only for anonymous callers."""
    from sqlalchemy.sql import column

    if scope.is_authenticated:
        return (column("tenant_id") == scope.tenant) | (column("tenant_id").is_(None))
    return column("tenant_id").is_(None)


async def get_tenant(
    x_api_key: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> TenantScope:
    """Resolve the caller's tenant scope from the API key header (optional)."""
    from emotionsim.core.config import get_settings

    if not get_settings().auth_enabled:
        return TenantScope()

    if not x_api_key:
        return TenantScope()  # anonymous/legacy

    key_hash = hash_api_key(x_api_key)
    result = await db.execute(
        select(User).where(User.api_key == key_hash, User.is_active.is_(True))
    )
    user = result.scalars().first()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return TenantScope(tenant=user.tenant_id, username=user.username)
