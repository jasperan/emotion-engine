"""API route aggregation"""
from fastapi import APIRouter

from app.api.scenarios import router as scenarios_router
from app.api.runs import router as runs_router
from app.api.websocket import router as websocket_router
from app.api.seed import router as seed_router
from app.api.datalake import router as datalake_router
from app.api.chat import router as chat_router
from app.api.document import router as document_router
from app.api.report import router as report_router
from app.llm.router import LLMRouter
from app.core.config import get_settings

router = APIRouter()

# Include sub-routers
router.include_router(scenarios_router)
router.include_router(runs_router)
router.include_router(websocket_router)
router.include_router(seed_router)
router.include_router(datalake_router)
router.include_router(chat_router)
router.include_router(document_router)
router.include_router(report_router)


@router.get("/")
async def root():
    """API root endpoint"""
    return {"message": "EmotionSim API", "version": "0.1.0"}


@router.get("/health/llm")
async def llm_health():
    """Check LLM provider health"""
    try:
        settings = get_settings()
        backend = settings.llm_backend
        client = LLMRouter.get_client(backend)
        is_healthy = await client.health_check()
        return {
            "provider": backend,
            "status": "healthy" if is_healthy else "unhealthy",
        }
    except Exception as e:
        settings = get_settings()
        return {
            "provider": settings.llm_backend,
            "status": "error",
            "error": str(e),
        }
