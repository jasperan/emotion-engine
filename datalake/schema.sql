-- =============================================================================
-- EmotionSim Datalake Schema for Oracle 26ai Free
-- =============================================================================
-- Target: Oracle Database 26ai Free (container-registry.oracle.com/database/free:latest-lite)
-- Service: FREEPDB1
--
-- Run as SYSDBA first to create the user:
--   CREATE USER emotionsim IDENTIFIED BY emotionsim;
--   GRANT CONNECT, RESOURCE, UNLIMITED TABLESPACE TO emotionsim;
--   GRANT CREATE SESSION, CREATE TABLE, CREATE SEQUENCE, CREATE VIEW TO emotionsim;
-- Then connect as emotionsim to run this script.
-- =============================================================================


-- ---------------------------------------------------------------------------
-- Table: SIMULATION_RUNS
-- ---------------------------------------------------------------------------
-- One row per simulation run. Captures scenario, config, status, and metrics.

CREATE TABLE simulation_runs (
    id              VARCHAR2(36)    DEFAULT SYS_GUID() PRIMARY KEY,
    scenario_name   VARCHAR2(256)   NOT NULL,
    scenario_id     VARCHAR2(36)    NULL,
    model           VARCHAR2(128)   NOT NULL,
    fallback_model  VARCHAR2(128)   NULL,
    status          VARCHAR2(20)    DEFAULT 'running' NOT NULL,
    created_at      TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    completed_at    TIMESTAMP       NULL,
    total_steps     NUMBER(10)      NULL,
    agent_count     NUMBER(5)       NULL,
    seed            NUMBER(10)      NULL,
    run_config      CLOB            NULL,   -- JSON: full scenario config
    final_metrics   CLOB            NULL    -- JSON: cooperation scores, etc.
);

CREATE INDEX ix_runs_scenario    ON simulation_runs (scenario_name);
CREATE INDEX ix_runs_status      ON simulation_runs (status);
CREATE INDEX ix_runs_created     ON simulation_runs (created_at);
CREATE INDEX ix_runs_model       ON simulation_runs (model);

ALTER TABLE simulation_runs ADD CONSTRAINT chk_runs_config_json
    CHECK (run_config IS NULL OR run_config IS JSON);
ALTER TABLE simulation_runs ADD CONSTRAINT chk_runs_metrics_json
    CHECK (final_metrics IS NULL OR final_metrics IS JSON);


-- ---------------------------------------------------------------------------
-- Table: SIMULATION_STEPS
-- ---------------------------------------------------------------------------
-- One row per tick/step in a simulation run.

CREATE TABLE simulation_steps (
    id              VARCHAR2(36)    DEFAULT SYS_GUID() PRIMARY KEY,
    run_id          VARCHAR2(36)    NOT NULL,
    step_number     NUMBER(10)      NOT NULL,
    created_at      TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    world_state     CLOB            NULL,   -- JSON: hazard level, locations, etc.
    active_agents   NUMBER(5)       NULL,
    messages_count  NUMBER(10)      NULL,

    CONSTRAINT fk_steps_run
        FOREIGN KEY (run_id)
        REFERENCES simulation_runs (id)
        ON DELETE CASCADE
);

CREATE INDEX ix_steps_run_id     ON simulation_steps (run_id);
CREATE INDEX ix_steps_run_step   ON simulation_steps (run_id, step_number);

ALTER TABLE simulation_steps ADD CONSTRAINT chk_steps_world_json
    CHECK (world_state IS NULL OR world_state IS JSON);


-- ---------------------------------------------------------------------------
-- Table: AGENT_EVENTS
-- ---------------------------------------------------------------------------
-- Every agent action, message, movement, error — the full event stream.

CREATE TABLE agent_events (
    id              VARCHAR2(36)    DEFAULT SYS_GUID() PRIMARY KEY,
    run_id          VARCHAR2(36)    NOT NULL,
    step_number     NUMBER(10)      NOT NULL,
    agent_name      VARCHAR2(128)   NOT NULL,
    event_type      VARCHAR2(64)    NOT NULL,
    created_at      TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,
    data            CLOB            NOT NULL,   -- JSON payload

    CONSTRAINT fk_events_run
        FOREIGN KEY (run_id)
        REFERENCES simulation_runs (id)
        ON DELETE CASCADE
);

CREATE INDEX ix_events_run_id    ON agent_events (run_id);
CREATE INDEX ix_events_run_step  ON agent_events (run_id, step_number);
CREATE INDEX ix_events_agent     ON agent_events (agent_name);
CREATE INDEX ix_events_type      ON agent_events (event_type);

ALTER TABLE agent_events ADD CONSTRAINT chk_events_data_json
    CHECK (data IS JSON);


-- ---------------------------------------------------------------------------
-- Table: AGENT_PLANS
-- ---------------------------------------------------------------------------
-- Cognitive architecture plan snapshots (from intent memory).

CREATE TABLE agent_plans (
    id              VARCHAR2(36)    DEFAULT SYS_GUID() PRIMARY KEY,
    run_id          VARCHAR2(36)    NOT NULL,
    step_number     NUMBER(10)      NOT NULL,
    agent_name      VARCHAR2(128)   NOT NULL,
    goal            VARCHAR2(512)   NOT NULL,
    steps           CLOB            NOT NULL,   -- JSON array of plan steps
    current_step    NUMBER(5)       NOT NULL,
    total_steps     NUMBER(5)       NOT NULL,
    status          VARCHAR2(20)    DEFAULT 'active' NOT NULL,
    created_at      TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,

    CONSTRAINT fk_plans_run
        FOREIGN KEY (run_id)
        REFERENCES simulation_runs (id)
        ON DELETE CASCADE
);

CREATE INDEX ix_plans_run_id     ON agent_plans (run_id);
CREATE INDEX ix_plans_agent      ON agent_plans (agent_name);
CREATE INDEX ix_plans_run_step   ON agent_plans (run_id, step_number);

ALTER TABLE agent_plans ADD CONSTRAINT chk_plans_steps_json
    CHECK (steps IS JSON);


-- ---------------------------------------------------------------------------
-- Table: SIMULATION_METRICS
-- ---------------------------------------------------------------------------
-- Per-step or per-run aggregate metrics for analysis.

CREATE TABLE simulation_metrics (
    id              VARCHAR2(36)    DEFAULT SYS_GUID() PRIMARY KEY,
    run_id          VARCHAR2(36)    NOT NULL,
    step_number     NUMBER(10)      NULL,       -- NULL = run-level metric
    metric_name     VARCHAR2(128)   NOT NULL,
    metric_value    NUMBER(12,4)    NOT NULL,
    created_at      TIMESTAMP       DEFAULT SYSTIMESTAMP NOT NULL,

    CONSTRAINT fk_metrics_run
        FOREIGN KEY (run_id)
        REFERENCES simulation_runs (id)
        ON DELETE CASCADE
);

CREATE INDEX ix_metrics_run_id   ON simulation_metrics (run_id);
CREATE INDEX ix_metrics_name     ON simulation_metrics (metric_name);
CREATE INDEX ix_metrics_run_step ON simulation_metrics (run_id, step_number);


-- ---------------------------------------------------------------------------
-- Views
-- ---------------------------------------------------------------------------

-- Run summary with event and step counts
CREATE OR REPLACE VIEW v_run_summary AS
SELECT
    r.id,
    r.scenario_name,
    r.model,
    r.status,
    r.created_at,
    r.completed_at,
    r.total_steps,
    r.agent_count,
    (SELECT COUNT(*) FROM simulation_steps s WHERE s.run_id = r.id) AS step_count,
    (SELECT COUNT(*) FROM agent_events e WHERE e.run_id = r.id) AS event_count
FROM simulation_runs r;


-- Agent activity summary per run
CREATE OR REPLACE VIEW v_agent_activity AS
SELECT
    e.run_id,
    e.agent_name,
    e.event_type,
    COUNT(*)            AS event_count,
    MIN(e.created_at)   AS first_event,
    MAX(e.created_at)   AS last_event
FROM agent_events e
GROUP BY e.run_id, e.agent_name, e.event_type;


-- =============================================================================
-- End of schema
-- =============================================================================
