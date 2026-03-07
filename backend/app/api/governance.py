"""REST and WebSocket endpoints for governance gate management."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.governance import (
    GateEventResponse,
    GateResolutionRequest,
    GovernanceConfigUpdate,
)

router = APIRouter(prefix="/governance", tags=["governance"])


@router.get("/pending")
async def get_pending_gates() -> list[dict]:
    """Get all pending governance gate decisions.
    Connected to engine in Task 8.
    """
    return []


@router.post("/resolve")
async def resolve_gate(request: GateResolutionRequest) -> dict:
    """Resolve a pending governance gate decision.
    Connected to engine in Task 8.
    """
    return {"status": "resolved", "decision_id": request.decision_id}


@router.get("/audit")
async def get_audit_log() -> list[dict]:
    """Get the immutable governance audit log.
    Connected to engine in Task 8.
    """
    return []


@router.put("/config")
async def update_governance_config(config: GovernanceConfigUpdate) -> dict:
    """Update governance configuration for current run.
    Connected to engine in Task 8.
    """
    return {"status": "updated"}
