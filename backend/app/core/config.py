"""Application configuration"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    app_name: str = "EmotionSim"
    debug: bool = True
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./emotionsim.db"
    
    # Ollama (default LLM provider)
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_api_key: str = "ollama"
    ollama_default_model: str = "qwen3.5:9b"
    ollama_fallback_model: str = "qwen3.5:4b"
    ollama_timeout: int = 60
    ollama_auto_fallback: bool = True
    
    # Claude (optional, for future use)
    anthropic_api_key: str = ""
    anthropic_default_model: str = "claude-3-sonnet-20240229"
    
    # Oracle Datalake (optional — logs everything to Oracle 26ai Free)
    datalake_enabled: bool = False
    oracle_db_host: str = "localhost"
    oracle_db_port: int = 1522
    oracle_db_service: str = "FREEPDB1"
    oracle_db_user: str = "emotionsim"
    oracle_db_password: str = "emotionsim"

    # Per-agent-type model routing (Pi-inspired: different models for different roles)
    model_route_environment: str | None = None  # None = use fallback model
    model_route_reactive: str | None = None  # None = use fallback model

    # Agent supervisor settings (Symphony-inspired fault isolation)
    agent_tick_timeout: float = 120.0  # seconds
    agent_max_backoff: float = 300.0  # seconds
    agent_max_consecutive_failures: int = 5

    # Negotiation settings
    negotiation_default_expiry_steps: int = 5

    # Simulation defaults
    default_max_steps: int | None = None  # None means infinite until consensus
    default_tick_delay: float = 0.5  # seconds between ticks

    # Engine V2: Heartbeat
    heartbeat_enabled: bool = False  # Use V2 engine

    # Engine V2: Governance
    governance_enabled: bool = True
    governance_threshold: float = 0.7
    governance_timeout_seconds: float = 60.0
    governance_timeout_action: str = "deny"
    governance_use_llm_scorer: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        protected_namespaces = ("settings_",)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

