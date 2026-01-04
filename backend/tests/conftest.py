"""Pytest configuration and fixtures"""
import pytest
import asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.database import Base
from app.llm.base import LLMClient, LLMMessage, LLMResponse


# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
def mock_llm_client() -> LLMClient:
    """Create a mock LLM client for testing"""
    client = MagicMock(spec=LLMClient)
    
    async def mock_generate(
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        system: str | None = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        # Return a mock structured response
        return LLMResponse(
            content='{"actions": [], "message": {"content": "Test message", "to_target": "broadcast", "message_type": "broadcast"}, "state_changes": {}, "reasoning": "Test reasoning"}',
            raw_response={"choices": [{"message": {"content": "test"}}]},
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        )
    
    client.generate = AsyncMock(side_effect=mock_generate)
    client.health_check = AsyncMock(return_value=True)
    
    return client


@pytest.fixture
def sample_persona():
    """Create a sample persona for testing"""
    from app.schemas.persona import Persona
    
    return Persona(
        name="Test Agent",
        age=30,
        sex="non-binary",
        occupation="Tester",
        openness=5,
        conscientiousness=5,
        extraversion=5,
        agreeableness=5,
        neuroticism=5,
        risk_tolerance=5,
        empathy_level=5,
        leadership=5,
        backstory="A test agent for unit testing",
        skills=["testing"],
        stress_level=3,
        health=10,
        location="test_location",
    )

