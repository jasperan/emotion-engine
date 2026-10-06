"""Tests for optional multi-tenant auth (users, API keys, tenant scoping)."""
import os

import pytest
from fastapi.testclient import TestClient

from emotionsim.auth.security import (
    generate_api_key,
    hash_api_key,
    hash_password,
    verify_password,
)


@pytest.fixture(scope="module", autouse=True)
def _isolated_db(tmp_path_factory):
    """Point the app's auto-detected SQLite at a fresh temp file for this module.

    The full app (TestClient lifespan) writes to the runtime DB; auth tests need
    isolation so usernames don't accumulate across runs.
    """
    db_path = tmp_path_factory.mktemp("authdb") / "auth.db"
    os.environ["SQLITE_DB_PATH"] = str(db_path)
    from emotionsim.core.config import get_settings

    get_settings.cache_clear()
    yield
    os.environ.pop("SQLITE_DB_PATH", None)
    get_settings.cache_clear()


class TestSecurity:
    def test_password_hash_verify_roundtrip(self):
        h = hash_password("correct horse battery staple")
        assert h.startswith("pbkdf2$")
        assert verify_password("correct horse battery staple", h)
        assert not verify_password("wrong", h)

    def test_hash_is_salted(self):
        assert hash_password("same") != hash_password("same")

    def test_verify_rejects_garbage(self):
        assert not verify_password("x", "not-a-hash")
        assert not verify_password("x", "")

    def test_api_key_roundtrip(self):
        key = generate_api_key()
        assert len(key) >= 60
        assert hash_api_key(key) != key
        assert hash_api_key(key) == hash_api_key(key)


def _app_client():
    """TestClient with the app lifespan active (auto-detect DB)."""
    from emotionsim.main import app

    return TestClient(app)


class TestAuthAPI:
    def test_register_login_me_flow(self):
        with _app_client() as client:
            resp = client.post(
                "/api/auth/register",
                json={"username": "alice", "password": "secret123"},
            )
            assert resp.status_code == 201, resp.text
            data = resp.json()
            assert data["username"] == "alice"
            api_key = data["api_key"]

            me = client.get("/api/auth/me", headers={"X-API-Key": api_key})
            assert me.status_code == 200
            assert me.json()["username"] == "alice"

            login = client.post(
                "/api/auth/login", json={"username": "alice", "password": "secret123"}
            )
            assert login.status_code == 200
            new_key = login.json()["api_key"]
            assert new_key != api_key
            assert client.get("/api/auth/me", headers={"X-API-Key": api_key}).status_code == 401
            assert client.get("/api/auth/me", headers={"X-API-Key": new_key}).status_code == 200

    def test_duplicate_username_rejected(self):
        with _app_client() as client:
            body = {"username": "bob", "password": "secret123"}
            assert client.post("/api/auth/register", json=body).status_code == 201
            assert client.post("/api/auth/register", json=body).status_code == 409

    def test_bad_credentials_rejected(self):
        with _app_client() as client:
            assert client.post(
                "/api/auth/login", json={"username": "nobody", "password": "wrongpass"}
            ).status_code == 401

    def test_me_requires_key(self):
        with _app_client() as client:
            assert client.get("/api/auth/me").status_code == 401

    def test_invalid_key_rejected(self):
        with _app_client() as client:
            resp = client.get("/api/auth/me", headers={"X-API-Key": "deadbeef" * 8})
            assert resp.status_code == 401


class TestTenantScoping:
    def _register(self, client, username):
        resp = client.post(
            "/api/auth/register", json={"username": username, "password": "secret123"}
        )
        return resp.json()["api_key"]

    def _scenario_body(self, name):
        return {
            "name": name,
            "description": "",
            "config": {"name": "world", "max_steps": 5},
            "agent_templates": [],
        }

    def test_tenant_sees_own_and_public_scenarios(self):
        with _app_client() as client:
            pub = client.post("/api/scenarios/", json=self._scenario_body("Public Scenario"))
            assert pub.status_code == 200

            key_a = self._register(client, "user_a")
            priv_a = client.post(
                "/api/scenarios/",
                headers={"X-API-Key": key_a},
                json=self._scenario_body("A's Private"),
            )
            assert priv_a.status_code == 200

            key_b = self._register(client, "user_b")
            names_b = {s["name"] for s in client.get("/api/scenarios/", headers={"X-API-Key": key_b}).json()}
            assert "Public Scenario" in names_b
            assert "A's Private" not in names_b

            names_a = {s["name"] for s in client.get("/api/scenarios/", headers={"X-API-Key": key_a}).json()}
            assert "A's Private" in names_a
            assert "Public Scenario" in names_a

            names_anon = {s["name"] for s in client.get("/api/scenarios/").json()}
            assert "Public Scenario" in names_anon
            assert "A's Private" not in names_anon

    def test_run_creation_is_tenant_tagged(self):
        with _app_client() as client:
            sc = client.post("/api/scenarios/", json=self._scenario_body("Runable")).json()
            key_a = self._register(client, "user_run")
            run = client.post(
                "/api/runs/",
                headers={"X-API-Key": key_a},
                json={"scenario_id": sc["id"], "seed": 1, "max_steps": 2},
            )
            assert run.status_code == 200, run.text
            run_id = run.json()["id"]

            key_b = self._register(client, "user_run_b")
            runs_b = client.get("/api/runs/", headers={"X-API-Key": key_b}).json()
            assert all(r["id"] != run_id for r in runs_b)

            # anonymous list also excludes the private run
            runs_anon = client.get("/api/runs/").json()
            assert all(r["id"] != run_id for r in runs_anon)

            # the owner sees it
            runs_a = client.get("/api/runs/", headers={"X-API-Key": key_a}).json()
            assert any(r["id"] == run_id for r in runs_a)

class TestTenantByIdIsolation:
    def _body(self, name):
        return {"name": name, "description": "", "config": {"name": "w", "max_steps": 5}, "agent_templates": []}

    def test_private_rows_hidden_from_other_callers_by_id(self):
        with _app_client() as client:
            def reg(u):
                return client.post("/api/auth/register", json={"username": u, "password": "secret123"}).json()["api_key"]

            ka, kb = reg("iso_a"), reg("iso_b")
            ha, hb = {"X-API-Key": ka}, {"X-API-Key": kb}
            sc = client.post("/api/scenarios/", headers=ha, json=self._body("iso private")).json()
            run = client.post("/api/runs/", headers=ha, json={"scenario_id": sc["id"], "seed": 1, "max_steps": 2}).json()

            # owner can reach both
            assert client.get(f"/api/scenarios/{sc['id']}", headers=ha).status_code == 200
            assert client.get(f"/api/runs/{run['id']}", headers=ha).status_code == 200
            assert client.get(f"/api/runs/{run['id']}/status", headers=ha).status_code == 200

            # other tenant and anonymous get 404 on every by-id route
            for h in (hb, {}):
                assert client.get(f"/api/scenarios/{sc['id']}", headers=h).status_code == 404
                assert client.put(f"/api/scenarios/{sc['id']}", headers=h, json={"name": "x"}).status_code == 404
                assert client.post("/api/runs/", headers=h, json={"scenario_id": sc["id"], "seed": 1, "max_steps": 2}).status_code == 404
                for suffix in ("", "/status", "/metrics", "/agents", "/steps", "/messages"):
                    assert client.get(f"/api/runs/{run['id']}{suffix}", headers=h).status_code == 404, suffix
                assert client.post(f"/api/runs/{run['id']}/control", headers=h, json={"action": "stop"}).status_code == 404
                assert client.delete(f"/api/runs/{run['id']}", headers=h).status_code == 404
                assert client.delete(f"/api/scenarios/{sc['id']}", headers=h).status_code == 404

            # still intact for owner
            assert client.get(f"/api/runs/{run['id']}", headers=ha).status_code == 200
            assert client.delete(f"/api/runs/{run['id']}", headers=ha).status_code == 200

    def test_chat_and_report_routes_mounted_and_scoped(self):
        with _app_client() as client:
            key = client.post("/api/auth/register", json={"username": "iso_c", "password": "secret123"}).json()["api_key"]
            other = client.post("/api/auth/register", json={"username": "iso_d", "password": "secret123"}).json()["api_key"]
            ha, hb = {"X-API-Key": key}, {"X-API-Key": other}
            sc = client.post("/api/scenarios/", headers=ha, json=self._body("iso c")).json()
            run = client.post("/api/runs/", headers=ha, json={"scenario_id": sc["id"], "seed": 1, "max_steps": 2}).json()
            rid = run["id"]

            paths = {r.path for r in client.app.routes}
            assert "/api/runs/{run_id}/report" in paths
            assert "/api/runs/{run_id}/agents/{agent_id}/chat" in paths
            assert "/api/documents/" in paths
            assert not any(p.startswith("/api/api/") for p in paths)

            # other tenant cannot reach the private run through these routes
            assert client.post(f"/api/runs/{rid}/report", headers=hb).status_code == 404
            assert client.post(
                f"/api/runs/{rid}/agents/a1/chat", headers=hb, json={"message": "hi"}
            ).status_code == 404


class TestDatalakeTenantIsolation:
    def test_datalake_by_id_routes_respect_run_ownership(self, monkeypatch):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        from emotionsim.api import datalake as dl_api
        from emotionsim.datalake.models import DatalakeBase
        from emotionsim.datalake.store import SimulationStore

        store = SimulationStore.__new__(SimulationStore)
        store.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        store.SessionFactory = sessionmaker(bind=store.engine)
        DatalakeBase.metadata.create_all(store.engine)
        store.close = lambda: None  # shared across requests in this test
        monkeypatch.setattr(dl_api, "_get_store", lambda: store)

        body = {"name": "dl", "description": "", "config": {"name": "w", "max_steps": 5}, "agent_templates": []}
        with _app_client() as client:
            def reg(u):
                return client.post("/api/auth/register", json={"username": u, "password": "secret123"}).json()["api_key"]

            ha, hb = {"X-API-Key": reg("dl_a")}, {"X-API-Key": reg("dl_b")}
            sc = client.post("/api/scenarios/", headers=ha, json=body).json()
            priv = client.post("/api/runs/", headers=ha, json={"scenario_id": sc["id"], "seed": 1, "max_steps": 2}).json()["id"]
            pub_sc = client.post("/api/scenarios/", json=body).json()
            pub = client.post("/api/runs/", json={"scenario_id": pub_sc["id"], "seed": 1, "max_steps": 2}).json()["id"]
            for rid in (priv, pub):
                store.create_run(run_id=rid, scenario_name="dl", model="m")

            # owner sees both, others only the public one
            ids = lambda h: {r["id"] for r in client.get("/api/datalake/runs", headers=h).json()["runs"]}
            assert ids(ha) == {priv, pub}
            assert ids(hb) == {pub}
            assert ids({}) == {pub}

            for h in (hb, {}):
                for suffix in ("", "/events", "/plans", "/metrics"):
                    assert client.get(f"/api/datalake/runs/{priv}{suffix}", headers=h).status_code == 404, suffix
                    assert client.get(f"/api/datalake/runs/{pub}{suffix}", headers=h).status_code == 200, suffix
                assert client.get(f"/api/datalake/compare?run_ids={pub},{priv}", headers=h).status_code == 404
                assert client.delete(f"/api/datalake/runs/{priv}", headers=h).status_code == 404

            assert client.get(f"/api/datalake/compare?run_ids={pub},{priv}", headers=ha).status_code == 200
            assert client.delete(f"/api/datalake/runs/{priv}", headers=ha).status_code == 200


class TestWebsocketAndCreationScoping:
    def _body(self, name):
        return {"name": name, "description": "", "config": {"name": "w", "max_steps": 5}, "agent_templates": []}

    def test_websocket_checks_ownership_before_accept(self):
        from starlette.websockets import WebSocketDisconnect

        with _app_client() as client:
            def reg(u):
                return client.post("/api/auth/register", json={"username": u, "password": "secret123"}).json()["api_key"]

            ka, kb = reg("ws_a"), reg("ws_b")
            sc = client.post("/api/scenarios/", headers={"X-API-Key": ka}, json=self._body("ws")).json()
            priv = client.post("/api/runs/", headers={"X-API-Key": ka}, json={"scenario_id": sc["id"], "seed": 1, "max_steps": 2}).json()["id"]
            pub_sc = client.post("/api/scenarios/", json=self._body("wspub")).json()
            pub = client.post("/api/runs/", json={"scenario_id": pub_sc["id"], "seed": 1, "max_steps": 2}).json()["id"]

            # anonymous, wrong tenant, bad key, unknown run: handshake refused
            for url, hdr in (
                (f"/api/ws/{priv}", {}),
                (f"/api/ws/{priv}", {"X-API-Key": kb}),
                (f"/api/ws/{priv}?api_key={kb}", {}),
                (f"/api/ws/{priv}", {"X-API-Key": "nope"}),
                ("/api/ws/does-not-exist", {}),
            ):
                with pytest.raises(WebSocketDisconnect):
                    with client.websocket_connect(url, headers=hdr):
                        pass

            # owner (header or query param) and anonymous-on-public are accepted
            for url, hdr in (
                (f"/api/ws/{priv}", {"X-API-Key": ka}),
                (f"/api/ws/{priv}?api_key={ka}", {}),
                (f"/api/ws/{pub}", {}),
            ):
                with client.websocket_connect(url, headers=hdr) as ws:
                    assert ws.receive_json()["event"] == "connected"

    def test_status_does_not_distinguish_unknown_from_foreign(self):
        with _app_client() as client:
            ka = client.post("/api/auth/register", json={"username": "st_a", "password": "secret123"}).json()["api_key"]
            sc = client.post("/api/scenarios/", headers={"X-API-Key": ka}, json=self._body("st")).json()
            priv = client.post("/api/runs/", headers={"X-API-Key": ka}, json={"scenario_id": sc["id"], "seed": 1, "max_steps": 2}).json()["id"]
            assert client.get(f"/api/runs/{priv}/status").status_code == 404
            assert client.get("/api/runs/no-such-run/status").status_code == 404

    def test_datalake_init_requires_api_key(self, monkeypatch):
        from emotionsim.api import datalake as dl_api

        calls = []

        class _Store:
            def init_db(self):
                calls.append(1)

            def close(self):
                pass

        monkeypatch.setattr(dl_api, "_get_store", lambda: _Store())
        with _app_client() as client:
            key = client.post("/api/auth/register", json={"username": "init_a", "password": "secret123"}).json()["api_key"]
            assert client.post("/api/datalake/init").status_code == 401
            assert calls == []
            assert client.post("/api/datalake/init", headers={"X-API-Key": key}).status_code == 200
            assert calls == [1]

    def test_import_scenario_file_is_tenant_tagged(self, monkeypatch, tmp_path):
        import json as _json

        from emotionsim.api import scenarios as sc_api

        (tmp_path / "mine.json").write_text(_json.dumps({
            "name": "imported", "description": "d",
            "config": {"name": "w", "max_steps": 5}, "agent_templates": [],
        }))
        monkeypatch.setattr(sc_api, "SCENARIOS_DIR", tmp_path)
        with _app_client() as client:
            ka = client.post("/api/auth/register", json={"username": "imp_a", "password": "secret123"}).json()["api_key"]
            kb = client.post("/api/auth/register", json={"username": "imp_b", "password": "secret123"}).json()["api_key"]
            r = client.post("/api/scenarios/files/mine.json/import", headers={"X-API-Key": ka})
            assert r.status_code == 200, r.text
            sid = r.json()["id"]
            assert client.get(f"/api/scenarios/{sid}", headers={"X-API-Key": ka}).status_code == 200
            assert client.get(f"/api/scenarios/{sid}", headers={"X-API-Key": kb}).status_code == 404
            assert client.get(f"/api/scenarios/{sid}").status_code == 404

    def test_document_upload_scenario_is_tenant_tagged(self, monkeypatch):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, MagicMock

        import emotionsim.services.document_ingestor as di
        import emotionsim.services.persona_generator as pg
        import emotionsim.services.scenario_assembler as sa
        import emotionsim.storage.embedding_service as es
        import emotionsim.storage.ner_extractor as ne
        import emotionsim.storage.oracle_graph_storage as og

        ingested = SimpleNamespace(graph_id="g1", entity_count=1, relation_count=0)
        assembled = SimpleNamespace(
            config={"name": "doc", "max_steps": 20}, agent_templates=[]
        )
        ingestor = MagicMock(ingest=AsyncMock(return_value=ingested))
        assembler = MagicMock(assemble=AsyncMock(return_value=assembled))
        monkeypatch.setattr(di, "DocumentIngestor", lambda **kw: ingestor)
        monkeypatch.setattr(sa, "ScenarioAssembler", lambda **kw: assembler)
        for mod, name in ((pg, "PersonaGenerator"), (es, "EmbeddingService"),
                          (ne, "NERExtractor"), (og, "OracleGraphStorage")):
            monkeypatch.setattr(mod, name, lambda *a, **kw: MagicMock())

        with _app_client() as client:
            ka = client.post("/api/auth/register", json={"username": "doc_a", "password": "secret123"}).json()["api_key"]
            kb = client.post("/api/auth/register", json={"username": "doc_b", "password": "secret123"}).json()["api_key"]
            r = client.post(
                "/api/documents/",
                headers={"X-API-Key": ka},
                json={"text": "A sufficiently long document body.", "scenario_name": "from doc"},
            )
            assert r.status_code == 200, r.text
            sid = r.json()["scenario_id"]
            assert client.get(f"/api/scenarios/{sid}", headers={"X-API-Key": ka}).status_code == 200
            assert client.get(f"/api/scenarios/{sid}", headers={"X-API-Key": kb}).status_code == 404
