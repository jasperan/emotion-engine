"""Regression tests: datalake scoping and lifecycle (2026-11 security audit)."""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BODY = {
    "name": "w",
    "description": "",
    "config": {"name": "w", "max_steps": 2},
    "agent_templates": [],
}


@pytest.fixture(scope="module", autouse=True)
def _isolated_db(tmp_path_factory):
    os.environ["SQLITE_DB_PATH"] = str(tmp_path_factory.mktemp("secfix") / "db.sqlite")
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


@pytest.fixture
def dl_store(monkeypatch):
    """Dummy in-memory datalake wired into the datalake API."""
    import emotionsim.api.datalake as dl_api
    from emotionsim.core.config import get_settings
    from emotionsim.datalake.models import DatalakeBase
    from emotionsim.datalake.store import SimulationStore

    store = SimulationStore.__new__(SimulationStore)
    store.engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    store.SessionFactory = sessionmaker(bind=store.engine)
    DatalakeBase.metadata.create_all(store.engine)
    store.close = lambda: None
    monkeypatch.setattr(dl_api, "_get_store", lambda: store)
    monkeypatch.setattr(get_settings(), "datalake_enabled", True)
    return store


def _register(client, name):
    key = client.post(
        "/api/auth/register", json={"username": name, "password": "secret123"}
    ).json()["api_key"]
    return {"X-API-Key": key}


def test_datalake_stats_excludes_hidden_runs(dl_store):
    dl_store.create_run(run_id="pub", scenario_name="Public", model="m")
    dl_store.create_run(run_id="priv", scenario_name="Private plan", model="m")
    dl_store.log_event("priv", 0, "a", "secret", {})
    stats = dl_store.get_stats(exclude_ids=["priv"])
    assert stats["total_runs"] == 1
    assert stats["by_scenario"] == {"Public": 1}
    assert stats["total_events"] == 0
    assert "secret" not in stats["by_event_type"]


def test_datalake_stats_endpoint_hides_other_tenants(client, dl_store):
    owner = _register(client, "sec_owner")
    sc = client.post("/api/scenarios/", headers=owner, json=BODY).json()
    rid = client.post(
        "/api/runs/", headers=owner, json={"scenario_id": sc["id"]}
    ).json()["id"]
    dl_store.create_run(run_id=rid, scenario_name="Owner secret", model="m")
    anon = client.get("/api/datalake/stats").json()
    assert "Owner secret" not in anon["by_scenario"]
    mine = client.get("/api/datalake/stats", headers=owner).json()
    assert mine["by_scenario"].get("Owner secret") == 1


def test_deleting_run_purges_datalake_copy(client, dl_store):
    owner = _register(client, "sec_owner2")
    sc = client.post("/api/scenarios/", headers=owner, json=BODY).json()
    rid = client.post(
        "/api/runs/", headers=owner, json={"scenario_id": sc["id"]}
    ).json()["id"]
    dl_store.create_run(run_id=rid, scenario_name="Doomed", model="m")
    assert client.delete(f"/api/runs/{rid}", headers=owner).status_code == 200
    assert client.get(f"/api/datalake/runs/{rid}").status_code == 404
    assert dl_store.get_run(rid) is None


def test_deleting_scenario_purges_datalake_copies(client, dl_store):
    owner = _register(client, "sec_owner3")
    sc = client.post("/api/scenarios/", headers=owner, json=BODY).json()
    rid = client.post(
        "/api/runs/", headers=owner, json={"scenario_id": sc["id"]}
    ).json()["id"]
    dl_store.create_run(run_id=rid, scenario_name="Doomed2", model="m")
    assert client.delete(f"/api/scenarios/{sc['id']}", headers=owner).status_code == 200
    assert dl_store.get_run(rid) is None
    assert client.get(f"/api/datalake/runs/{rid}").status_code == 404
