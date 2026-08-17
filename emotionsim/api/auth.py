"""User registration / login / key endpoints (optional multi-tenant auth)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from emotionsim.auth.deps import TenantScope, get_tenant
from emotionsim.auth.security import (
    generate_api_key,
    hash_api_key,
    hash_password,
    verify_password,
)
from emotionsim.core.database import get_db
from emotionsim.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class AuthResponse(BaseModel):
    user_id: str
    username: str
    api_key: str  # shown once; login rotates it


class MeResponse(BaseModel):
    user_id: str
    username: str


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Create a user; returns the API key (shown once)."""
    existing = (
        await db.execute(select(User).where(User.username == data.username))
    ).scalars().first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")

    api_key = generate_api_key()
    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        api_key=hash_api_key(api_key),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return AuthResponse(user_id=user.id, username=user.username, api_key=api_key)


@router.post("/login", response_model=AuthResponse)
async def login(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate with username/password; returns a fresh API key (rotates)."""
    user = (
        await db.execute(select(User).where(User.username == data.username))
    ).scalars().first()
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    api_key = generate_api_key()
    user.api_key = hash_api_key(api_key)
    await db.commit()
    return AuthResponse(user_id=user.id, username=user.username, api_key=api_key)


@router.get("/me", response_model=MeResponse)
async def me(scope: TenantScope = Depends(get_tenant)):
    """Identity of the caller (401 without a valid API key)."""
    if not scope.is_authenticated:
        raise HTTPException(status_code=401, detail="API key required")
    return MeResponse(user_id=scope.tenant, username=scope.username or "")


@router.get("/health")
async def auth_health():
    return {"auth_enabled": True, "time": datetime.now(timezone.utc).isoformat()}
