"""Application configuration"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    app_name: str = "EmotionSim"
    debug: bool = False

    # Database (Oracle DB 26ai Free — primary)
    oracle_db_host: str = "localhost"
    oracle_db_port: int = 1522
    oracle_db_service: str = "FREEPDB1"
    oracle_db_user: str = "emotionsim"
    oracle_db_password: str = "emotionsim"

    @property
    def database_url(self) -> str:
        """Build Oracle async connection URL from individual settings."""
        return (
            f"oracle+oracledb://{self.oracle_db_user}:{self.oracle_db_password}"
            f"@{self.oracle_db_host}:{self.oracle_db_port}"
            f"/?service_name={self.oracle_db_service}"
        )

    # Datalake (analytics tables in the same Oracle instance)
    datalake_enabled: bool = True

    # Ollama (default LLM provider)
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_api_key: str = "ollama"
    ollama_default_model: str = "qwen3.5:4b"
    ollama_fallback_model: str = "qwen3.5:4b"
    ollama_timeout: int = 60
    ollama_auto_fallback: bool = True

    # vLLM (parallel inference backend — preferred for concurrent agent ticks)
    llm_backend: str = "vllm"  # "ollama", "vllm", or "openai"
    vllm_base_url: str = "http://localhost:8010"
    vllm_default_model: str = "Qwen/Qwen3.5-4B"

    # OpenAI-compatible remote endpoint (OCA / litellm / OpenAI)
    # Empty strings = auto-read from ~/.codex/config.toml at runtime
    openai_base_url: str = ""
    openai_model: str = ""
    openai_api_key: str = ""  # falls back to OPENAI_API_KEY env var

    # Claude (optional, for future use)
    anthropic_api_key: str = ""
    anthropic_default_model: str = "claude-3-sonnet-20240229"

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
    default_max_steps: int = 10  # default ticks per simulation
    default_tick_delay: float = 0.5  # seconds between ticks
    default_num_agents: int = 10  # default agents per simulation

    # Context compaction
    max_context_chars: int = 3000  # max chars for agent context prompt (prevents timeout on smaller models)

    # Parallelism & VRAM control
    max_concurrent_llm_calls: int = 3    # semaphore size (3 = parallel agent ticks, GPU-gated)
    vram_aware_mode: bool = True          # poll Ollama /api/ps to gate cold starts
    # Cinematic scene model
    scene_mode: bool = True               # enable scene-based tick processing
    scene_max_turns: int = 3              # max dialogue turns per scene per tick

    # Agent conclusion enforcement
    agent_max_tokens_per_run: int = 50000   # per-agent token budget across the run (0 = unlimited)
    agent_conclude_at_pct: float = 0.85     # inject "conclude" prompt at this % of budget
    agent_max_stagnant_steps: int = 5       # force conclusion after N consecutive stuck steps

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
