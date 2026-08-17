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