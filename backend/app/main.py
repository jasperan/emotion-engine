"""FastAPI application entry point"""
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.database import init_db
from app.api.routes import router as api_router


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    print(f"Starting {settings.app_name}...")
    await init_db() # Keep database initialization

    # Auto-seed default scenarios if none exist
    from app.core.database import async_session_maker as AsyncSessionLocal
    from app.models.scenario import Scenario
    from sqlalchemy import select, func

    async with AsyncSessionLocal() as db:
        count = (await db.execute(select(func.count()).select_from(Scenario))).scalar()
        if count == 0:
            print("No scenarios found. Seeding built-in scenarios...")
            from app.scenarios.defaults import DEFAULT_SCENARIOS
            for name, creator in DEFAULT_SCENARIOS.items():
                sc = creator()
                scenario = Scenario(
                    name=sc.name,
                    description=sc.description,
                    config=sc.config.model_dump(),
                    agent_templates=[t.model_dump() for t in sc.agent_templates],
                )
                db.add(scenario)
            await db.commit()
            print(f"Seeded {len(DEFAULT_SCENARIOS)} built-in scenarios.")
        else:
            print(f"Found {count} existing scenarios.")

    # Auto-resume simulations
    async with AsyncSessionLocal() as db:
        from app.simulation.manager import SimulationManager
        manager = SimulationManager.get_instance()
        resumed_count = await manager.resume_all_active_runs(db)
        if resumed_count > 0:
            print(f"Resumed {resumed_count} simulations.")

    yield
    # Shutdown
    print(f"Shutting down {settings.app_name}...")
    # Shutdown (cleanup if needed)


app = FastAPI(
    title=settings.app_name,
    description="Multi-Agent Simulation System inspired by The Great Flood",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for frontend; origins loaded from settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Simple in-memory rate limiter for mutation endpoints (POST/DELETE)
# ---------------------------------------------------------------------------
class RateLimitMiddleware(BaseHTTPMiddleware):
    """Limits POST/DELETE requests to RATE_LIMIT per IP per 60-second window."""

    RATE_LIMIT = 100
    WINDOW_SECONDS = 60

    def __init__(self, app):
        super().__init__(app)
        # ip -> (count, window_start)
        self._hits: dict[str, tuple[int, float]] = {}

    async def dispatch(self, request: Request, call_next):
        if request.method not in ("POST", "DELETE"):
            return await call_next(request)

        now = time.time()
        ip = request.client.host if request.client else "unknown"

        count, window_start = self._hits.get(ip, (0, now))
        if now - window_start >= self.WINDOW_SECONDS:
            # Reset window
            count = 0
            window_start = now

        count += 1
        self._hits[ip] = (count, window_start)

        if count > self.RATE_LIMIT:
            return Response(
                content="Rate limit exceeded",
                status_code=429,
                media_type="text/plain",
            )

        return await call_next(request)


app.add_middleware(RateLimitMiddleware)

# Include API routes
app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "app": settings.app_name}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
