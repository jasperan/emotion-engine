"""API route aggregation"""
from fastapi import APIRouter

from app.api.scenarios import router as scenarios_router
from app.api.runs import router as runs_router
from app.api.websocket import router as websocket_router
from app.api.seed import router as seed_router
from app.llm.router import LLMRouter

router = APIRouter()

# Include sub-routers
router.include_router(scenarios_router)
router.include_router(runs_router)
router.include_router(websocket_router)
router.include_router(seed_router)


@router.get("/")
async def root():
    """API root endpoint"""
    return {"message": "EmotionSim API", "version": "0.1.0"}


@router.get("/health/llm")
async def llm_health():
    """Check LLM provider health"""
    try:
        client = LLMRouter.get_client("ollama")
        is_healthy = await client.health_check()
        return {
            "provider": "ollama",
            "status": "healthy" if is_healthy else "unhealthy",
        }
    except Exception as e:
        return {
            "provider": "ollama",
            "status": "error",
            "error": str(e),
        }
