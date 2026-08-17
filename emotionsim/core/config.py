"""Application configuration"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    app_name: str = "EmotionSim"
    debug: bool = False

    # CORS: comma-separated origins allowed to call the API
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Database (Oracle DB 26ai Free, primary; SQLite file fallback for dev/pi)
    # NOTE: These defaults are for local dev only. In production, override via
    # ORACLE_DB_USER / ORACLE_DB_PASSWORD environment variables or .env file.
    oracle_db_host: str = "localhost"
    oracle_db_port: int = 1522
    oracle_db_service: str = "FREEPDB1"
    oracle_db_user: str = "emotionsim"
    oracle_db_password: str = "emotionsim"

    # "auto" probes Oracle and falls back to SQLite when unreachable.
    # "oracle_forced" requires Oracle (raises if unreachable).
    database_backend: str = "auto"
    sqlite_db_path: str = "emotionsim_runtime.db"

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
    ollama_timeout: int = 300  # seconds per request (long prompts + cold GPU TTFT)
    ollama_auto_fallback: bool = True
    # Hours/minutes the model stays loaded in VRAM after a request (Ollama
    # keep_alive). Long enough to avoid reload-thrash across agent ticks;
    # "-1" pins the model until explicitly unloaded.
    ollama_keep_alive: str = "30m"

    # vLLM (parallel inference backend, preferred for concurrent agent ticks)
    # "auto" (default) probes vLLM → Ollama → stub and picks the first that
    # responds, so the same code runs on a GPU box, a laptop, or a container.
    llm_backend: str = "auto"  # "auto", "ollama", "vllm", "openai", or "stub"
    vllm_base_url: str = "http://localhost:8010"
    vllm_default_model: str = "Qwen/Qwen3.5-4B"

    # Service probes for auto-detection
    runtime_probe_timeout: float = 1.0

    # Semantic LLM response caching (deferred idea). Off by default so the
    # default simulation path stays byte-identical; enable explicitly for
    # cost/latency wins on repeated prompts.
    llm_cache_enabled: bool = False
    llm_cache_threshold: float = 0.95  # cosine similarity for a cache hit
    llm_cache_max_entries: int = 1024
    llm_cache_ttl_seconds: int = 3600
    # "auto" = Ollama nomic-embed-text when reachable, offline n-gram otherwise
    llm_cache_embedding: str = "auto"

    # Continuous emotion dimensions (valence/arousal) — opt-in; off keeps the
    # default path byte-identical. When on, events + the LLM's stated emotion
    # move valence/arousal, which modulate response probability and prompt text.
    emotion_dimensions_enabled: bool = False
    emotion_decay: float = 0.3       # per-tick relaxation toward personality baseline
    emotion_lm_pull: float = 0.5     # how strongly the LLM's emotion word moves the state

    # Message distortion / rumor spread (opt-in). When on, retold stories lose
    # fidelity per hop and surface distorted in agent prompts.
    rumor_distortion_enabled: bool = False
    rumor_fidelity_drop: float = 0.15   # per-hop fidelity loss (0.15 -> 15%)
    rumor_overlap_threshold: float = 0.5  # token Jaccard needed to count as a relay

    # Dynamic agent spawning / departure (opt-in). Off keeps the default
    # path byte-identical.
    dynamic_spawning_enabled: bool = False
    spawn_interval_steps: int = 3
    spawn_max_extra_agents: int = 5
    spawn_location: str = "shelter"
    spawn_evict_health_threshold: int = 1
    spawn_evict_stress_threshold: int = 9

    # Theory of Mind (opt-in): agents model peers' goals/states/intentions
    # from observed actions + messages; beliefs surface in prompts.
    theory_of_mind_enabled: bool = False

    # Optional multi-tenant API auth (users + API keys). Always optional for
    # callers: the CLI/TUI/eval keep anonymous access to public data.
    auth_enabled: bool = True

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
    agent_tick_timeout: float = 240.0  # seconds; generous default for cold GPU warm-up (Ollama model load)
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

    # Hybrid populations (LightweightAgent scaling)
    # Background agents (scenario templates with "background": true) act via
    # rule-based decisions with zero LLM calls and are promoted to full LLM
    # agents when addressed / in an active scene / high-leadership & low-stress.
    max_llm_agents_per_step: int = 0       # per-step LLM-agent budget (0 = unlimited)
    background_demote_after_steps: int = 5 # foreground steps without activity before demotion

    # Cognitive reflection (Step 4): every N steps, foreground agents run a
    # batched LLM reflection that distills lessons into episodic memory.
    reflection_interval_steps: int = 5

    # Agent conclusion enforcement
    agent_max_tokens_per_run: int = 50000   # per-agent token budget across the run (0 = unlimited)
    agent_conclude_at_pct: float = 0.85     # inject "conclude" prompt at this % of budget
    agent_max_stagnant_steps: int = 5       # force conclusion after N consecutive stuck steps

    # Graph-backed agent memory (MiroFish)
    # When enabled, HumanAgents use GraphMemory (hybrid vector+keyword recall)
    # instead of the flat sliding-window AgentMemory for prompt context.
    # Requires a knowledge graph per run (created automatically); falls back
    # to flat memory gracefully if the graph layer is unavailable.
    graph_memory_enabled: bool = False

    # Governance gates (wired into the V1 tick loop — Step 6)
    governance_enabled: bool = True
    governance_threshold: float = 0.7
    governance_timeout_seconds: float = 60.0
    governance_timeout_action: str = "deny"
    governance_use_llm_scorer: bool = False

    # Goal tree (mission -> group -> individual, wired into V1 — Step 6)
    goal_tree_enabled: bool = True

    # Cost accounting for observability (Step 9)
    # Estimated cost per 1k streamed chars (the engine's token proxy).
    # Set > 0 to enable cost estimates in run metrics.
    llm_cost_per_1k_tokens: float = 0.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        protected_namespaces = ("settings_",)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
