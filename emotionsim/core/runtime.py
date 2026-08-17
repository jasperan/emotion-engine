"""Runtime environment detection for the pi/local dev experience.

EmotionSim can run against several service stacks:
- **LLM**: vLLM (parallel, GPU), Ollama (single-slot, CPU/GPU), or the
  deterministic offline stub (no network).
- **Database**: Oracle DB 26ai Free, or a SQLite file fallback.

`llm_backend=auto` (the default) probes each service in order and picks the
first one that responds, so the exact same codebase runs on a developer's
GPU box (vLLM + qwen), a laptop with Ollama, or a container without either.
Explicit configuration always wins over detection.
"""
from __future__ import annotations

import asyncio
import logging
import socket
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level caches so detection runs at most once per process.
_llm_backend: Optional[str] = None
_ollama_model: Optional[str] = None


def probe_tcp(host: str, port: int, timeout: float = 1.0) -> bool:
    """Quick TCP connectivity probe. Returns True when the port accepts a connection."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def probe_http(base_url: str, path: str, timeout: float = 1.0) -> bool:
    """HTTP probe for OpenAI-compatible endpoints (vLLM /v1/models, Ollama /api/tags)."""
    import httpx

    url = base_url.rstrip("/") + path
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url)
            return resp.status_code < 500
    except Exception:
        return False


def probe_ollama(base_url: str, timeout: float = 1.0) -> bool:
    """Probe an Ollama server via its native /api/tags endpoint."""
    native = base_url.rstrip("/")
    if native.endswith("/v1"):
        native = native[: -len("/v1")]
    return probe_http(native, "/api/tags", timeout=timeout)


def probe_vllm(base_url: str, timeout: float = 1.0) -> bool:
    """Probe a vLLM server via /v1/models (OpenAI-compatible)."""
    return probe_http(base_url, "/v1/models", timeout=timeout)


def probe_oracle(settings, timeout: float = 1.0) -> bool:
    """True when an actual EmotionSim Oracle connection succeeds.

    A plain TCP probe is not enough: other projects frequently publish Oracle
    containers on the same host. We authenticate with the configured
    credentials so auto-detection only picks Oracle when it is actually usable.
    """
    try:
        import oracledb

        conn = oracledb.connect(
            user=settings.oracle_db_user,
            password=settings.oracle_db_password,
            dsn=f"{settings.oracle_db_host}:{settings.oracle_db_port}/{settings.oracle_db_service}",
            timeout=timeout,
        )
        conn.close()
        return True
    except Exception:
        return False


def detect_llm_backend(preferred: str | None = None, timeout: float = 1.0) -> str:
    """Resolve the LLM backend to use.

    Resolution order: explicit preference → vLLM → Ollama → stub (offline).
    The result is cached per process; call :func:`reset_detection` in tests.
    """
    global _llm_backend

    from emotionsim.core.config import get_settings

    settings = get_settings()
    preferred = preferred or settings.llm_backend

    if preferred not in ("auto", ""):
        # Explicit preference: deterministic, no probing, never cached.
        return preferred

    if _llm_backend is not None:
        return _llm_backend

    vllm_url = settings.vllm_base_url
    if probe_vllm(vllm_url, timeout=timeout):
        logger.info("Runtime detect: vLLM reachable at %s", vllm_url)
        _llm_backend = "vllm"
        return "vllm"

    if probe_ollama(settings.ollama_base_url, timeout=timeout):
        logger.info("Runtime detect: Ollama reachable at %s", settings.ollama_base_url)
        _llm_backend = "ollama"
        return "ollama"

    logger.warning(
        "Runtime detect: no vLLM/Ollama reachable; falling back to the "
        "deterministic offline stub backend (no network)."
    )
    _llm_backend = "stub"
    return "stub"


def reset_detection() -> None:
    """Clear cached detection results (used by tests)."""
    global _llm_backend, _ollama_model
    _llm_backend = None
    _ollama_model = None


def list_ollama_models(base_url: str, timeout: float = 1.0) -> list[str]:
    """List model names available on an Ollama server (empty when unreachable)."""
    native = base_url.rstrip("/")
    if native.endswith("/v1"):
        native = native[: -len("/v1")]
    try:
        import httpx

        with httpx.Client(timeout=timeout) as client:
            resp = client.get(native + "/api/tags")
            if resp.status_code >= 400:
                return []
            data = resp.json()
            return [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        return []


def pick_ollama_model(preferred: str, base_url: str, timeout: float = 1.0) -> str:
    """Pick the best available Ollama model.

    Priority: the configured model → any model in the configured model's
    family (e.g. preferred `qwen3.5:4b` → any available `qwen3.5:*`) → any
    qwen3.x → any non-cloud model → the preferred name (let Ollama 404
    rather than guess). Cloud models are always skipped.
    """
    global _ollama_model
    if _ollama_model is not None:
        return _ollama_model

    family = preferred.split(":", 1)[0] if ":" in preferred else preferred
    available = list_ollama_models(base_url, timeout=timeout)
    local = [n for n in available if ":" in n and not n.endswith(":cloud")]
    if not available:
        _ollama_model = preferred
        return preferred
    if preferred in local:
        _ollama_model = preferred
        return preferred
    for name in local:
        if name.startswith(family + ":"):
            _ollama_model = name
            return name
    for name in local:
        if name.startswith("qwen3."):
            _ollama_model = name
            return name
    if local:
        _ollama_model = local[0]
        return local[0]
    _ollama_model = preferred
    return preferred


@dataclass
class RuntimeReport:
    """Full environment health snapshot for `emotionsim doctor`."""

    llm_backend: str = "auto"
    vllm_url: str = ""
    vllm_reachable: bool = False
    ollama_url: str = ""
    ollama_reachable: bool = False
    ollama_models: list[str] = field(default_factory=list)
    ollama_chosen_model: str = ""
    gpu_present: bool = False
    gpu_name: str = ""
    oracle_url: str = ""
    oracle_db_host: str = "localhost"
    oracle_db_port: int = 1522
    oracle_reachable: bool = False
    database_backend: str = "oracle"
    sqlite_path: str = ""
    embedder_present: bool = False
    frontend_ready: bool = False
    ollama_uses_gpu: bool = True

    @property
    def effective_llm_backend(self) -> str:
        return self.llm_backend if self.llm_backend != "auto" else self.resolved_backend

    @property
    def resolved_backend(self) -> str:
        if self.vllm_reachable:
            return "vllm"
        if self.ollama_reachable:
            return "ollama"
        return "stub"


def probe_ollama_gpu(native_url: str, timeout: float = 1.0) -> bool:
    """True when Ollama loads models into VRAM (size_vram > 0 on /api/ps).

    Ollama silently falls back to CPU inference when its bundled CUDA runtime
    cannot initialize on the installed driver — common with very new drivers.
    A running-but-CPU Ollama makes every tick take minutes, so `doctor`
    surfaces it explicitly.
    """
    url = native_url.rstrip("/")
    if url.endswith("/v1"):
        url = url[: -len("/v1")]
    try:
        import httpx

        with httpx.Client(timeout=timeout) as client:
            resp = client.get(url + "/api/ps")
            if resp.status_code >= 400:
                return True  # no loaded models — nothing to say
            models = resp.json().get("models", [])
        if not models:
            return True
        sizes = [int(m.get("size_vram", 0) or 0) for m in models]
        return any(s > 0 for s in sizes)
    except Exception:
        return True


def collect_runtime_report(timeout: float = 1.0) -> RuntimeReport:
    """Gather the full environment snapshot (used by `doctor` and `dev`)."""
    from emotionsim.core.config import get_settings

    settings = get_settings()
    report = RuntimeReport(
        llm_backend=settings.llm_backend,
        vllm_url=settings.vllm_base_url,
        ollama_url=settings.ollama_base_url,
        oracle_url=settings.database_url,
    )

    report.vllm_reachable = probe_vllm(settings.vllm_base_url, timeout=timeout)
    report.ollama_reachable = probe_ollama(settings.ollama_base_url, timeout=timeout)
    if report.ollama_reachable:
        report.ollama_models = [
            n for n in list_ollama_models(settings.ollama_base_url, timeout=timeout)
        ]
        report.ollama_chosen_model = pick_ollama_model(
            settings.ollama_default_model, settings.ollama_base_url, timeout=timeout
        )
        report.ollama_uses_gpu = probe_ollama_gpu(settings.ollama_base_url, timeout=timeout)

    try:
        import subprocess

        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if out.returncode == 0 and out.stdout.strip():
            report.gpu_present = True
            report.gpu_name = out.stdout.strip().splitlines()[0]
    except Exception:
        pass

    host, port = settings.oracle_db_host, settings.oracle_db_port
    report.oracle_reachable = probe_oracle(settings, timeout=timeout)
    report.database_backend = "oracle" if report.oracle_reachable else "sqlite"
    report.sqlite_path = settings.sqlite_db_path

    # Embeddings: is nomic-embed-text available via Ollama (when present)?
    report.embedder_present = any(
        "nomic-embed" in m for m in report.ollama_models
    )

    import os

    report.frontend_ready = os.path.isdir("frontend/node_modules")
    return report


def detect_database_url(preferred: str | None = None, timeout: float = 1.0) -> str:
    """Resolve the database URL: Oracle when reachable, else SQLite file.

    Explicit override via the returned-vs-configured check: if the configured
    Oracle host is reachable we keep the Oracle URL; otherwise we return a
    SQLite file URL so the whole stack still boots without Oracle.
    """
    from emotionsim.core.config import get_settings

    settings = get_settings()
    if settings.database_backend == "oracle_forced":
        return settings.database_url

    if probe_oracle(settings, timeout=timeout):
        return settings.database_url

    logger.warning(
        "Runtime detect: Oracle %s:%s unreachable/unusable; falling back to SQLite (%s).",
        settings.oracle_db_host,
        settings.oracle_db_port,
        settings.sqlite_db_path,
    )
    return f"sqlite+aiosqlite:///{settings.sqlite_db_path}"
