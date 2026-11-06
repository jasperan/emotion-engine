"""Regression: a run-creation request must not change process-wide LLM routing."""
import os

import pytest
from fastapi.testclient import TestClient

BODY = {
    "name": "w",
    "description": "",
    "config": {"name": "w", "max_steps": 2},
    "agent_templates": [],
}


@pytest.fixture(scope="module", autouse=True)
def _isolated_db(tmp_path_factory):
    os.environ["SQLITE_DB_PATH"] = str(tmp_path_factory.mktemp("llmiso") / "db.sqlite")
    from emotionsim.core.config import get_settings

    get_settings.cache_clear()
    yield
    os.environ.pop("SQLITE_DB_PATH", None)
    get_settings.cache_clear()


@pytest.fixture
def client():
    from emotionsim.main import app

    with TestClient(app) as c:
        yield c


def test_run_create_does_not_mutate_process_llm_backend(client):
    from emotionsim.core.config import get_settings
    from emotionsim.llm.router import LLMRouter, effective_backend

    before = get_settings().llm_backend
    sc = client.post("/api/scenarios/", json=BODY).json()
    resp = client.post(
        "/api/runs/", json={"scenario_id": sc["id"], "llm_backend": "openai"}
    )
    assert resp.status_code == 200
    assert get_settings().llm_backend == before
    assert effective_backend() == before
    assert type(LLMRouter.get_client()).__name__ != "OpenAIClient" or before == "openai"


def test_backend_override_is_context_scoped():
    from emotionsim.core.config import get_settings
    from emotionsim.llm.router import backend_override, effective_backend

    base = get_settings().llm_backend
    with backend_override("vllm"):
        assert effective_backend() == "vllm"
    assert effective_backend() == base
