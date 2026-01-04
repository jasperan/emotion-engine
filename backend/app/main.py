"""FastAPI application entry point"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

    # Auto-resume simulations
    from app.database.session import AsyncSessionLocal
    from app.simulation.manager import SimulationManager
    
    async with AsyncSessionLocal() as db:
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

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for external access
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

