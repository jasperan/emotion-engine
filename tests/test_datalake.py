"""Tests for the datalake module — config, models, store, and logger.

Uses SQLite in-memory as a stand-in for Oracle (same SQLAlchemy ORM).
The Oracle-specific features (JSON constraints, sequences, views) are
tested in integration tests against a real Oracle container.
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from emotionsim.datalake.config import DatabaseConfig, get_db_config
from emotionsim.datalake.models import (
    DatalakeBase,
    AgentEvent,
    AgentPlan,
    SimulationMetric,
    SimulationRun,
    SimulationStep,
    generate_uuid,
)
from emotionsim.datalake.store import SimulationStore, _serialize
from emotionsim.datalake.logger import DatalakeLogger


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sqlite_store():
    """Create a SimulationStore backed by SQLite in-memory."""
    config = DatabaseConfig(
        host="localhost",
        port=1522,
        service_name="FREEPDB1",
        user="test",
        password="test",  # pragma: allowlist secret
    )
    # Override to use SQLite
    store = SimulationStore.__new__(SimulationStore)
    store.config = config
    store.engine = create_engine("sqlite:///:memory:", echo=False)
    store.SessionFactory = sessionmaker(bind=store.engine)
    DatalakeBase.metadata.create_all(store.engine)
    return store


@pytest.fixture
def sample_run_id():
    return generate_uuid()


# ---------------------------------------------------------------------------
# Config Tests
# ---------------------------------------------------------------------------

class TestDatabaseConfig:
    def test_defaults(self):
        config = DatabaseConfig()
        assert config.host == "localhost"
        assert config.port == 1522
        assert config.service_name == "FREEPDB1"
        assert config.user == "emotionsim"
        assert config.password == "emotionsim"  # pragma: allowlist secret

    def test_connection_url(self):
        config = DatabaseConfig(user="u", password="p", host="h", port=9999, service_name="SVC")
        url = config.connection_url
        assert "oracle+oracledb://u:p@h:9999/?service_name=SVC" == url

    def test_dsn(self):
        config = DatabaseConfig(host="myhost", port=1521, service_name="PDB1")
        assert config.dsn == "myhost:1521/PDB1"

    def test_repr_no_password(self):
        config = DatabaseConfig()
        r = repr(config)
        assert "emotionsim" not in r or "password" not in r

    def test_get_db_config_env(self, monkeypatch):
        monkeypatch.setenv("ORACLE_DB_HOST", "oracle.example.com")
        monkeypatch.setenv("ORACLE_DB_PORT", "2222")
        monkeypatch.setenv("ORACLE_DB_USER", "myuser")
        config = get_db_config()
        assert config.host == "oracle.example.com"
        assert config.port == 2222
        assert config.user == "myuser"


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------

class TestModels:
    def test_generate_uuid(self):
        u1 = generate_uuid()
        u2 = generate_uuid()
        assert len(u1) == 36
        assert u1 != u2

    def test_simulation_run_to_dict(self, sqlite_store, sample_run_id):
        with sqlite_store.SessionFactory() as db:
            run = SimulationRun(
                id=sample_run_id,
                scenario_name="Flood",
                model="qwen3.5:27b",
                status="running",
                agent_count=5,
                seed=42,
            )
            db.add(run)
            db.commit()

            d = run.to_dict()
            assert d["id"] == sample_run_id
            assert d["scenario_name"] == "Flood"
            assert d["model"] == "qwen3.5:27b"
            assert d["agent_count"] == 5
            assert d["seed"] == 42

    def test_simulation_step_to_dict(self, sqlite_store, sample_run_id):
        with sqlite_store.SessionFactory() as db:
            run = SimulationRun(id=sample_run_id, scenario_name="X", model="m")
            db.add(run)
            db.flush()

            step = SimulationStep(
                run_id=sample_run_id,
                step_number=1,
                world_state=json.dumps({"hazard_level": 3}),
                active_agents=4,
                messages_count=10,
            )
            db.add(step)
            db.commit()

            d = step.to_dict()
            assert d["step_number"] == 1
            assert d["world_state"]["hazard_level"] == 3
            assert d["active_agents"] == 4

    def test_agent_event_to_dict(self, sqlite_store, sample_run_id):
        with sqlite_store.SessionFactory() as db:
            run = SimulationRun(id=sample_run_id, scenario_name="X", model="m")
            db.add(run)
            db.flush()

            event = AgentEvent(
                run_id=sample_run_id,
                step_number=2,
                agent_name="Alice",
                event_type="message",
                data=json.dumps({"content": "Help!"}),
            )
            db.add(event)
            db.commit()

            d = event.to_dict()
            assert d["agent_name"] == "Alice"
            assert d["event_type"] == "message"
            assert d["data"]["content"] == "Help!"

    def test_agent_plan_to_dict(self, sqlite_store, sample_run_id):
        with sqlite_store.SessionFactory() as db:
            run = SimulationRun(id=sample_run_id, scenario_name="X", model="m")
            db.add(run)
            db.flush()

            plan = AgentPlan(
                run_id=sample_run_id,
                step_number=3,
                agent_name="Bob",
                goal="Find shelter",
                steps=json.dumps(["Go to hilltop", "Build shelter"]),
                current_step=0,
                total_steps=2,
                status="active",
            )
            db.add(plan)
            db.commit()

            d = plan.to_dict()
            assert d["goal"] == "Find shelter"
            assert d["steps"] == ["Go to hilltop", "Build shelter"]
            assert d["current_step"] == 0

    def test_simulation_metric_to_dict(self, sqlite_store, sample_run_id):
        with sqlite_store.SessionFactory() as db:
            run = SimulationRun(id=sample_run_id, scenario_name="X", model="m")
            db.add(run)
            db.flush()

            metric = SimulationMetric(
                run_id=sample_run_id,
                step_number=5,
                metric_name="cooperation_score",
                metric_value=0.85,
            )
            db.add(metric)
            db.commit()

            d = metric.to_dict()
            assert d["metric_name"] == "cooperation_score"
            assert d["metric_value"] == 0.85
            assert d["step_number"] == 5


# ---------------------------------------------------------------------------
# Serialization Tests
# ---------------------------------------------------------------------------

class TestSerialize:
    def test_serialize_none(self):
        assert json.loads(_serialize(None)) is None

    def test_serialize_string(self):
        result = json.loads(_serialize("hello"))
        assert result == {"text": "hello"}

    def test_serialize_dict(self):
        data = {"key": "value", "num": 42}
        result = json.loads(_serialize(data))
        assert result["key"] == "value"
        assert result["num"] == 42

    def test_serialize_unsupported(self):
        # object() serializes via default=str, producing a string
        result = _serialize(object())
        parsed = json.loads(result)
        assert parsed is not None


# ---------------------------------------------------------------------------
# Store Tests
# ---------------------------------------------------------------------------

class TestSimulationStore:
    def test_init_db(self, sqlite_store):
        # Already initialized by fixture, verify tables exist
        with sqlite_store.SessionFactory() as db:
            count = db.query(SimulationRun).count()
            assert count == 0

    def test_create_run(self, sqlite_store, sample_run_id):
        result = sqlite_store.create_run(
            run_id=sample_run_id,
            scenario_name="The Great Flood",
            model="qwen3.5:27b",
            fallback_model="qwen3.5:4b",
            agent_count=6,
            seed=42,
            run_config={"max_steps": 50},
        )
        assert result == sample_run_id

        run = sqlite_store.get_run(sample_run_id)
        assert run is not None
        assert run["scenario_name"] == "The Great Flood"
        assert run["model"] == "qwen3.5:27b"
        assert run["agent_count"] == 6

    def test_complete_run(self, sqlite_store, sample_run_id):
        sqlite_store.create_run(
            run_id=sample_run_id,
            scenario_name="Flood",
            model="m",
        )
        sqlite_store.complete_run(
            run_id=sample_run_id,
            total_steps=25,
            final_metrics={"cooperation": 0.9},
            status="completed",
        )

        run = sqlite_store.get_run(sample_run_id)
        assert run["status"] == "completed"
        assert run["total_steps"] == 25
        assert run["final_metrics"]["cooperation"] == 0.9

    def test_log_step(self, sqlite_store, sample_run_id):
        sqlite_store.create_run(run_id=sample_run_id, scenario_name="X", model="m")
        step_id = sqlite_store.log_step(
            run_id=sample_run_id,
            step_number=1,
            world_state={"hazard_level": 5},
            active_agents=4,
            messages_count=8,
        )
        assert len(step_id) == 36

    def test_log_event(self, sqlite_store, sample_run_id):
        sqlite_store.create_run(run_id=sample_run_id, scenario_name="X", model="m")
        event_id = sqlite_store.log_event(
            run_id=sample_run_id,
            step_number=1,
            agent_name="Alice",
            event_type="message",
            data={"content": "Help!"},
        )
        assert len(event_id) == 36

        events = sqlite_store.get_run_events(sample_run_id)
        assert len(events) == 1
        assert events[0]["agent_name"] == "Alice"

    def test_log_events_batch(self, sqlite_store, sample_run_id):
        sqlite_store.create_run(run_id=sample_run_id, scenario_name="X", model="m")
        event_ids = sqlite_store.log_events_batch(
            run_id=sample_run_id,
            events=[
                {"step_number": 1, "agent_name": "A", "event_type": "msg", "data": {"x": 1}},
                {"step_number": 1, "agent_name": "B", "event_type": "msg", "data": {"x": 2}},
                {"step_number": 2, "agent_name": "A", "event_type": "move", "data": {"y": 3}},
            ],
        )
        assert len(event_ids) == 3

        events = sqlite_store.get_run_events(sample_run_id)
        assert len(events) == 3

    def test_log_event_filtered(self, sqlite_store, sample_run_id):
        sqlite_store.create_run(run_id=sample_run_id, scenario_name="X", model="m")
        sqlite_store.log_events_batch(
            run_id=sample_run_id,
            events=[
                {"step_number": 1, "agent_name": "A", "event_type": "message", "data": {}},
                {"step_number": 1, "agent_name": "B", "event_type": "error", "data": {}},
                {"step_number": 2, "agent_name": "A", "event_type": "move", "data": {}},
            ],
        )

        messages = sqlite_store.get_run_events(sample_run_id, event_type="message")
        assert len(messages) == 1

        a_events = sqlite_store.get_run_events(sample_run_id, agent_name="A")
        assert len(a_events) == 2

    def test_log_plan(self, sqlite_store, sample_run_id):
        sqlite_store.create_run(run_id=sample_run_id, scenario_name="X", model="m")
        plan_id = sqlite_store.log_plan(
            run_id=sample_run_id,
            step_number=3,
            agent_name="Bob",
            goal="Find shelter",
            steps=["Go to hilltop", "Build shelter"],
            current_step=0,
        )
        assert len(plan_id) == 36

        plans = sqlite_store.get_run_plans(sample_run_id)
        assert len(plans) == 1
        assert plans[0]["goal"] == "Find shelter"

    def test_log_plan_filtered(self, sqlite_store, sample_run_id):
        sqlite_store.create_run(run_id=sample_run_id, scenario_name="X", model="m")
        sqlite_store.log_plan(
            run_id=sample_run_id, step_number=1, agent_name="A",
            goal="G1", steps=["s1"], current_step=0,
        )
        sqlite_store.log_plan(
            run_id=sample_run_id, step_number=2, agent_name="B",
            goal="G2", steps=["s2"], current_step=0,
        )

        a_plans = sqlite_store.get_run_plans(sample_run_id, agent_name="A")
        assert len(a_plans) == 1
        assert a_plans[0]["agent_name"] == "A"

    def test_log_metric(self, sqlite_store, sample_run_id):
        sqlite_store.create_run(run_id=sample_run_id, scenario_name="X", model="m")
        metric_id = sqlite_store.log_metric(
            run_id=sample_run_id,
            metric_name="hazard_level",
            metric_value=7.5,
            step_number=5,
        )
        assert len(metric_id) == 36

        metrics = sqlite_store.get_run_metrics(sample_run_id)
        assert len(metrics) == 1
        assert metrics[0]["metric_name"] == "hazard_level"
        assert metrics[0]["metric_value"] == 7.5

    def test_log_metrics_batch(self, sqlite_store, sample_run_id):
        sqlite_store.create_run(run_id=sample_run_id, scenario_name="X", model="m")
        ids = sqlite_store.log_metrics_batch(
            run_id=sample_run_id,
            metrics=[
                {"metric_name": "m1", "metric_value": 1.0, "step_number": 1},
                {"metric_name": "m2", "metric_value": 2.0, "step_number": 2},
            ],
        )
        assert len(ids) == 2

    def test_list_runs(self, sqlite_store):
        for i in range(5):
            sqlite_store.create_run(
                run_id=generate_uuid(),
                scenario_name=f"Scenario_{i % 2}",
                model="m",
            )

        result = sqlite_store.list_runs()
        assert result["total"] == 5
        assert len(result["runs"]) == 5

        result = sqlite_store.list_runs(scenario_name="Scenario_0")
        assert result["total"] == 3

    def test_list_runs_pagination(self, sqlite_store):
        for i in range(10):
            sqlite_store.create_run(
                run_id=generate_uuid(), scenario_name="S", model="m",
            )

        result = sqlite_store.list_runs(limit=3, offset=0)
        assert len(result["runs"]) == 3
        assert result["total"] == 10

    def test_get_stats(self, sqlite_store, sample_run_id):
        sqlite_store.create_run(
            run_id=sample_run_id, scenario_name="Flood", model="qwen3.5:27b",
        )
        sqlite_store.log_events_batch(
            run_id=sample_run_id,
            events=[
                {"step_number": 1, "agent_name": "A", "event_type": "message", "data": {}},
                {"step_number": 1, "agent_name": "B", "event_type": "move", "data": {}},
            ],
        )

        stats = sqlite_store.get_stats()
        assert stats["total_runs"] == 1
        assert stats["total_events"] == 2
        assert stats["by_scenario"]["Flood"] == 1
        assert stats["by_event_type"]["message"] == 1

    def test_delete_run(self, sqlite_store, sample_run_id):
        sqlite_store.create_run(
            run_id=sample_run_id, scenario_name="X", model="m",
        )
        sqlite_store.log_event(
            run_id=sample_run_id, step_number=1,
            agent_name="A", event_type="msg", data={},
        )

        assert sqlite_store.delete_run(sample_run_id) is True
        assert sqlite_store.get_run(sample_run_id) is None
        assert sqlite_store.delete_run(sample_run_id) is False

    def test_replay_run(self, sqlite_store, sample_run_id):
        sqlite_store.create_run(
            run_id=sample_run_id, scenario_name="X", model="m",
        )
        sqlite_store.log_events_batch(
            run_id=sample_run_id,
            events=[
                {"step_number": 1, "agent_name": "A", "event_type": "msg", "data": {"x": 1}},
                {"step_number": 2, "agent_name": "B", "event_type": "msg", "data": {"x": 2}},
                {"step_number": 3, "agent_name": "A", "event_type": "msg", "data": {"x": 3}},
            ],
        )

        events = list(sqlite_store.replay_run(sample_run_id))
        assert len(events) == 3
        assert events[0]["step_number"] == 1
        assert events[-1]["step_number"] == 3


# ---------------------------------------------------------------------------
# Logger Tests
# ---------------------------------------------------------------------------

class TestDatalakeLogger:
    @pytest.fixture
    def mock_store(self):
        store = MagicMock(spec=SimulationStore)
        store.create_run = MagicMock()
        store.log_step = MagicMock()
        store.log_event = MagicMock()
        store.log_events_batch = MagicMock()
        store.log_plan = MagicMock()
        store.log_metric = MagicMock()
        store.complete_run = MagicMock()
        store.close = MagicMock()
        return store

    def test_creates_run_on_init(self, mock_store):
        logger = DatalakeLogger(
            run_id="r1",
            scenario_name="Flood",
            model="qwen3.5:27b",
            store=mock_store,
        )
        mock_store.create_run.assert_called_once_with(
            run_id="r1",
            scenario_name="Flood",
            model="qwen3.5:27b",
            scenario_id=None,
            fallback_model=None,
            seed=None,
            run_config=None,
        )

    def test_step_completed_logs_step(self, mock_store):
        dl = DatalakeLogger(run_id="r1", scenario_name="S", model="m", store=mock_store)
        dl.on_event("step_completed", {
            "step": 5,
            "world_state": {"hazard_level": 3, "agents": {"a1": {}, "a2": {}}},
            "messages": [{"from": "A"}],
            "actions": [{"agent": "A", "type": "move"}],
        })
        mock_store.log_step.assert_called_once()
        args = mock_store.log_step.call_args
        assert args.kwargs["step_number"] == 5
        assert args.kwargs["active_agents"] == 2

    def test_message_buffers_event(self, mock_store):
        dl = DatalakeLogger(run_id="r1", scenario_name="S", model="m", store=mock_store)
        dl._buffer_size = 100  # prevent auto-flush

        dl.on_event("message", {
            "step": 3,
            "from_agent": "Alice",
            "content": "Help!",
        })

        assert len(dl._event_buffer) == 1
        assert dl._event_buffer[0]["agent_name"] == "Alice"
        assert dl._event_buffer[0]["event_type"] == "message"

    def test_buffer_flushes_on_step_completed(self, mock_store):
        dl = DatalakeLogger(run_id="r1", scenario_name="S", model="m", store=mock_store)
        dl._buffer_size = 100

        # Buffer some events
        dl.on_event("message", {"step": 1, "from_agent": "A", "content": "X"})
        dl.on_event("message", {"step": 1, "from_agent": "B", "content": "Y"})

        # Step completed should flush
        dl.on_event("step_completed", {
            "step": 1,
            "world_state": {"agents": {}},
            "messages": [],
            "actions": [],
        })

        # log_events_batch should have been called at least once
        # (may be called multiple times: once for buffered messages, once for step actions)
        assert mock_store.log_events_batch.call_count >= 1
        # Collect all events across all calls
        all_events = []
        for call in mock_store.log_events_batch.call_args_list:
            args, kwargs = call
            events = args[1] if len(args) > 1 else kwargs.get("events", [])
            all_events.extend(events)
        assert len(all_events) >= 2

    def test_buffer_auto_flushes_on_size(self, mock_store):
        dl = DatalakeLogger(run_id="r1", scenario_name="S", model="m", store=mock_store)
        dl._buffer_size = 3

        for i in range(3):
            dl.on_event("message", {"step": 1, "from_agent": f"A{i}", "content": "X"})

        mock_store.log_events_batch.assert_called_once()
        assert len(dl._event_buffer) == 0

    def test_run_completed_completes_run(self, mock_store):
        dl = DatalakeLogger(run_id="r1", scenario_name="S", model="m", store=mock_store)
        dl.on_event("run_completed", {
            "step": 25,
            "evaluation": {"cooperation": 0.9},
        })

        mock_store.complete_run.assert_called_once_with(
            run_id="r1",
            total_steps=25,
            final_metrics={"cooperation": 0.9},
            status="completed",
        )

    def test_run_stopped_cancels_run(self, mock_store):
        dl = DatalakeLogger(run_id="r1", scenario_name="S", model="m", store=mock_store)
        dl.on_event("run_stopped", {"step": 10})

        mock_store.complete_run.assert_called_once_with(
            run_id="r1",
            total_steps=10,
            final_metrics=None,
            status="cancelled",
        )

    def test_agent_moved_buffered(self, mock_store):
        dl = DatalakeLogger(run_id="r1", scenario_name="S", model="m", store=mock_store)
        dl._buffer_size = 100
        dl.on_event("agent_moved", {"step": 2, "agent": "Bob", "to": "hilltop"})
        assert len(dl._event_buffer) == 1
        assert dl._event_buffer[0]["event_type"] == "agent_moved"

    def test_consensus_logs_metric(self, mock_store):
        dl = DatalakeLogger(run_id="r1", scenario_name="S", model="m", store=mock_store)
        dl.on_event("consensus_reached", {"step": 15, "decision": "evacuate"})
        mock_store.log_metric.assert_called_once()

    def test_log_agent_plan(self, mock_store):
        dl = DatalakeLogger(run_id="r1", scenario_name="S", model="m", store=mock_store)
        dl.log_agent_plan(
            agent_name="Alice",
            step_number=5,
            goal="Find shelter",
            steps=["Go hilltop", "Build"],
            current_step=1,
        )
        mock_store.log_plan.assert_called_once_with(
            run_id="r1",
            step_number=5,
            agent_name="Alice",
            goal="Find shelter",
            steps=["Go hilltop", "Build"],
            current_step=1,
            status="active",
        )

    def test_close_flushes_and_closes(self, mock_store):
        dl = DatalakeLogger(run_id="r1", scenario_name="S", model="m", store=mock_store)
        dl._buffer_size = 100
        dl.on_event("message", {"step": 1, "from_agent": "A", "content": "X"})
        dl.close()

        mock_store.log_events_batch.assert_called_once()
        mock_store.close.assert_called_once()

    def test_error_handling_doesnt_crash(self, mock_store):
        mock_store.log_step.side_effect = Exception("DB down")
        dl = DatalakeLogger(run_id="r1", scenario_name="S", model="m", store=mock_store)
        # Should not raise
        dl.on_event("step_completed", {
            "step": 1,
            "world_state": {"agents": {}},
            "messages": [],
            "actions": [],
        })

    def test_init_error_doesnt_crash(self):
        """If Oracle is down, logger init should not crash."""
        mock_store = MagicMock(spec=SimulationStore)
        mock_store.create_run.side_effect = Exception("Connection refused")
        # Should not raise
        dl = DatalakeLogger(
            run_id="r1", scenario_name="S", model="m", store=mock_store,
        )
        assert dl.run_id == "r1"
