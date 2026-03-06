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
    ollama_default_model: str = "qwen3.5:27b"
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

    # Simulation defaults
    default_max_steps: int | None = None  # None means infinite until consensus
    default_tick_delay: float = 0.5  # seconds between ticks
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

