"""Datalake API endpoints for querying Oracle 26ai Free logged data."""
import asyncio
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from emotionsim.core.config import get_settings

router = APIRouter(prefix="/datalake", tags=["datalake"])


def _get_store():
    """Get a SimulationStore instance, raising 503 if datalake is not enabled."""
    settings = get_settings()
    if not settings.datalake_enabled:
        raise HTTPException(
            status_code=503,
            detail="Datalake is not enabled. Set DATALAKE_ENABLED=true",
        )

    from emotionsim.datalake.config import DatabaseConfig
    from emotionsim.datalake.store import SimulationStore

    config = DatabaseConfig(
        host=settings.oracle_db_host,
        port=settings.oracle_db_port,
        service_name=settings.oracle_db_service,
        user=settings.oracle_db_user,
        password=settings.oracle_db_password,
    )
    return SimulationStore(config)


async def _run_sync(func, *args, **kwargs):
    """Run a synchronous SimulationStore method in a thread to avoid blocking the event loop."""
    return await asyncio.to_thread(func, *args, **kwargs)


@router.get("/stats")
async def get_stats():
    """Get aggregate statistics across all logged runs."""
    store = _get_store()
    try:
        return await _run_sync(store.get_stats)
    finally:
        store.close()


@router.get("/runs")
async def list_runs(
    scenario_name: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    """List logged runs with optional filtering."""
    store = _get_store()
    try:
        return await _run_sync(
            store.list_runs,
            scenario_name=scenario_name,
            status=status,
            limit=limit,
            offset=offset,
        )
    finally:
        store.close()


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    """Get a specific logged run with counts."""
    store = _get_store()
    try:
        result = await _run_sync(store.get_run, run_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Run not found in datalake")
        return result
    finally:
        store.close()


@router.get("/runs/{run_id}/events")
async def get_run_events(
    run_id: str,
    event_type: Optional[str] = None,
    agent_name: Optional[str] = None,
    limit: int = Query(500, le=2000),
):
    """Get events for a logged run."""
    store = _get_store()
    try:
        return await _run_sync(
            store.get_run_events,
            run_id=run_id,
            event_type=event_type,
            agent_name=agent_name,
            limit=limit,
        )
    finally:
        store.close()


@router.get("/runs/{run_id}/plans")
async def get_run_plans(
    run_id: str,
    agent_name: Optional[str] = None,
):
    """Get cognitive plan snapshots for a logged run."""
    store = _get_store()
    try:
        return await _run_sync(store.get_run_plans, run_id=run_id, agent_name=agent_name)
    finally:
        store.close()


@router.get("/runs/{run_id}/metrics")
async def get_run_metrics(run_id: str):
    """Get all metrics for a logged run."""
    store = _get_store()
    try:
        return await _run_sync(store.get_run_metrics, run_id=run_id)
    finally:
        store.close()


@router.delete("/runs/{run_id}")
async def delete_run(run_id: str):
    """Delete a logged run and all its data."""
    store = _get_store()
    try:
        deleted = await _run_sync(store.delete_run, run_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Run not found in datalake")
        return {"status": "deleted", "run_id": run_id}
    finally:
        store.close()


@router.post("/init")
async def init_datalake():
    """Initialize datalake tables (create if not exist)."""
    store = _get_store()
    try:
        await _run_sync(store.init_db)
        return {"status": "initialized"}
    finally:
        store.close()
