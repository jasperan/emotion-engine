"""
SimulationStore: high-level interface for persisting simulation data to Oracle 26ai Free.

Provides CRUD operations over simulation runs, steps, agent events, plans,
and metrics via SQLAlchemy + python-oracledb.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from app.datalake.config import DatabaseConfig, get_db_config
from app.datalake.models import (
    DatalakeBase,
    AgentEvent,
    AgentPlan,
    SimulationMetric,
    SimulationRun,
    SimulationStep,
)

logger = logging.getLogger(__name__)


def _serialize(data: Any) -> str:
    """Serialize data to JSON string."""
    if data is None:
        return json.dumps(None)
    if isinstance(data, str):
        return json.dumps({"text": data})
    if isinstance(data, dict):
        return json.dumps(data, default=str)
    try:
        return json.dumps(data, default=str)
    except (TypeError, ValueError):
        return json.dumps({"raw": str(data)})


class SimulationStore:
    """
    High-level storage interface for simulation data in Oracle 26ai Free.

    Wraps SQLAlchemy sessions and provides domain-specific operations
    for logging simulation runs, steps, agent events, plans, and metrics.
    """

    def __init__(self, config: Optional[DatabaseConfig] = None):
        if config is None:
            config = get_db_config()
        self.config = config

        self.engine = create_engine(
            config.connection_url,
            echo=config.echo,
            pool_size=config.pool_min,
            max_overflow=config.pool_max - config.pool_min,
            pool_pre_ping=True,
        )
        self.SessionFactory = sessionmaker(bind=self.engine)

    def init_db(self) -> None:
        """Create all tables if they do not exist."""
        DatalakeBase.metadata.create_all(self.engine)
        logger.info("Datalake tables created/verified.")

    def drop_db(self) -> None:
        """Drop all tables. Use with caution."""
        DatalakeBase.metadata.drop_all(self.engine)
        logger.warning("All datalake tables dropped.")

    # -------------------------------------------------------------------------
    # Run CRUD
    # -------------------------------------------------------------------------

    def create_run(
        self,
        run_id: str,
        scenario_name: str,
        model: str,
        scenario_id: Optional[str] = None,
        fallback_model: Optional[str] = None,
        agent_count: Optional[int] = None,
        seed: Optional[int] = None,
        run_config: Optional[Dict] = None,
    ) -> str:
        """Create a new simulation run record."""
        with self.SessionFactory() as db:
            run = SimulationRun(
                id=run_id,
                scenario_name=scenario_name,
                scenario_id=scenario_id,
                model=model,
                fallback_model=fallback_model,
                agent_count=agent_count,
                seed=seed,
                run_config=json.dumps(run_config) if run_config else None,
            )
            db.add(run)
            db.commit()
            logger.info("Created datalake run %s (%s)", run_id, scenario_name)
        return run_id

    def complete_run(
        self,
        run_id: str,
        total_steps: Optional[int] = None,
        final_metrics: Optional[Dict] = None,
        status: str = "completed",
    ) -> None:
        """Finalize a simulation run."""
        with self.SessionFactory() as db:
            run = db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
            if run is None:
                logger.warning("Run %s not found in datalake", run_id)
                return
            run.status = status
            run.completed_at = datetime.now(timezone.utc)
            if total_steps is not None:
                run.total_steps = total_steps
            if final_metrics is not None:
                run.final_metrics = json.dumps(final_metrics, default=str)
            db.commit()
            logger.info("Completed datalake run %s (status=%s)", run_id, status)

    # -------------------------------------------------------------------------
    # Step logging
    # -------------------------------------------------------------------------

    def log_step(
        self,
        run_id: str,
        step_number: int,
        world_state: Optional[Dict] = None,
        active_agents: Optional[int] = None,
        messages_count: Optional[int] = None,
    ) -> str:
        """Log a simulation step."""
        step_id = str(uuid.uuid4())
        with self.SessionFactory() as db:
            step = SimulationStep(
                id=step_id,
                run_id=run_id,
                step_number=step_number,
                world_state=json.dumps(world_state, default=str) if world_state else None,
                active_agents=active_agents,
                messages_count=messages_count,
            )
            db.add(step)
            db.commit()
        return step_id

    # -------------------------------------------------------------------------
    # Agent event logging
    # -------------------------------------------------------------------------

    def log_event(
        self,
        run_id: str,
        step_number: int,
        agent_name: str,
        event_type: str,
        data: Any,
    ) -> str:
        """Log a single agent event."""
        event_id = str(uuid.uuid4())
        with self.SessionFactory() as db:
            event = AgentEvent(
                id=event_id,
                run_id=run_id,
                step_number=step_number,
                agent_name=agent_name,
                event_type=event_type,
                data=_serialize(data),
            )
            db.add(event)
            db.commit()
        return event_id

    def log_events_batch(
        self,
        run_id: str,
        events: List[Dict[str, Any]],
    ) -> List[str]:
        """Log multiple agent events in a single transaction."""
        event_ids = []
        with self.SessionFactory() as db:
            for evt in events:
                event_id = str(uuid.uuid4())
                event = AgentEvent(
                    id=event_id,
                    run_id=run_id,
                    step_number=evt["step_number"],
                    agent_name=evt["agent_name"],
                    event_type=evt["event_type"],
                    data=_serialize(evt["data"]),
                )
                db.add(event)
                event_ids.append(event_id)
            db.commit()
        return event_ids

    # -------------------------------------------------------------------------
    # Plan logging
    # -------------------------------------------------------------------------

    def log_plan(
        self,
        run_id: str,
        step_number: int,
        agent_name: str,
        goal: str,
        steps: List[str],
        current_step: int,
        status: str = "active",
    ) -> str:
        """Log an agent's cognitive plan snapshot."""
        plan_id = str(uuid.uuid4())
        with self.SessionFactory() as db:
            plan = AgentPlan(
                id=plan_id,
                run_id=run_id,
                step_number=step_number,
                agent_name=agent_name,
                goal=goal,
                steps=json.dumps(steps),
                current_step=current_step,
                total_steps=len(steps),
                status=status,
            )
            db.add(plan)
            db.commit()
        return plan_id

    # -------------------------------------------------------------------------
    # Metrics logging
    # -------------------------------------------------------------------------

    def log_metric(
        self,
        run_id: str,
        metric_name: str,
        metric_value: float,
        step_number: Optional[int] = None,
    ) -> str:
        """Log a single metric (per-step or per-run)."""
        metric_id = str(uuid.uuid4())
        with self.SessionFactory() as db:
            metric = SimulationMetric(
                id=metric_id,
                run_id=run_id,
                step_number=step_number,
                metric_name=metric_name,
                metric_value=metric_value,
            )
            db.add(metric)
            db.commit()
        return metric_id

    def log_metrics_batch(
        self,
        run_id: str,
        metrics: List[Dict[str, Any]],
    ) -> List[str]:
        """Log multiple metrics in a single transaction."""
        metric_ids = []
        with self.SessionFactory() as db:
            for m in metrics:
                metric_id = str(uuid.uuid4())
                metric = SimulationMetric(
                    id=metric_id,
                    run_id=run_id,
                    step_number=m.get("step_number"),
                    metric_name=m["metric_name"],
                    metric_value=m["metric_value"],
                )
                db.add(metric)
                metric_ids.append(metric_id)
            db.commit()
        return metric_ids

    # -------------------------------------------------------------------------
    # Querying
    # -------------------------------------------------------------------------

    def get_run(self, run_id: str) -> Optional[Dict]:
        """Get a full run with step and event counts."""
        with self.SessionFactory() as db:
            run = db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
            if run is None:
                return None
            result = run.to_dict()
            result["step_count"] = (
                db.query(func.count(SimulationStep.id))
                .filter(SimulationStep.run_id == run_id)
                .scalar() or 0
            )
            result["event_count"] = (
                db.query(func.count(AgentEvent.id))
                .filter(AgentEvent.run_id == run_id)
                .scalar() or 0
            )
            return result

    def list_runs(
        self,
        scenario_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List runs with optional filtering and pagination."""
        with self.SessionFactory() as db:
            query = db.query(SimulationRun)
            if scenario_name:
                query = query.filter(SimulationRun.scenario_name == scenario_name)
            if status:
                query = query.filter(SimulationRun.status == status)
            total = query.count()
            runs = (
                query.order_by(SimulationRun.created_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )
            return {
                "runs": [r.to_dict() for r in runs],
                "total": total,
                "limit": limit,
                "offset": offset,
            }

    def get_run_events(
        self,
        run_id: str,
        event_type: Optional[str] = None,
        agent_name: Optional[str] = None,
        limit: int = 500,
    ) -> List[Dict]:
        """Get events for a run, optionally filtered."""
        with self.SessionFactory() as db:
            query = db.query(AgentEvent).filter(AgentEvent.run_id == run_id)
            if event_type:
                query = query.filter(AgentEvent.event_type == event_type)
            if agent_name:
                query = query.filter(AgentEvent.agent_name == agent_name)
            events = (
                query.order_by(AgentEvent.step_number, AgentEvent.created_at)
                .limit(limit)
                .all()
            )
            return [e.to_dict() for e in events]

    def get_run_plans(self, run_id: str, agent_name: Optional[str] = None) -> List[Dict]:
        """Get plan snapshots for a run."""
        with self.SessionFactory() as db:
            query = db.query(AgentPlan).filter(AgentPlan.run_id == run_id)
            if agent_name:
                query = query.filter(AgentPlan.agent_name == agent_name)
            plans = query.order_by(AgentPlan.step_number).all()
            return [p.to_dict() for p in plans]

    def get_run_metrics(self, run_id: str) -> List[Dict]:
        """Get all metrics for a run."""
        with self.SessionFactory() as db:
            metrics = (
                db.query(SimulationMetric)
                .filter(SimulationMetric.run_id == run_id)
                .order_by(SimulationMetric.step_number, SimulationMetric.metric_name)
                .all()
            )
            return [m.to_dict() for m in metrics]

    def replay_run(self, run_id: str) -> Generator[Dict, None, None]:
        """Replay a run's events in chronological order."""
        with self.SessionFactory() as db:
            events = (
                db.query(AgentEvent)
                .filter(AgentEvent.run_id == run_id)
                .order_by(AgentEvent.step_number, AgentEvent.created_at)
                .all()
            )
            for event in events:
                yield event.to_dict()

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregate statistics across all runs."""
        with self.SessionFactory() as db:
            total_runs = db.query(func.count(SimulationRun.id)).scalar() or 0
            total_events = db.query(func.count(AgentEvent.id)).scalar() or 0
            total_steps = db.query(func.count(SimulationStep.id)).scalar() or 0

            status_rows = (
                db.query(SimulationRun.status, func.count(SimulationRun.id))
                .group_by(SimulationRun.status)
                .all()
            )

            scenario_rows = (
                db.query(SimulationRun.scenario_name, func.count(SimulationRun.id))
                .group_by(SimulationRun.scenario_name)
                .all()
            )

            event_type_rows = (
                db.query(AgentEvent.event_type, func.count(AgentEvent.id))
                .group_by(AgentEvent.event_type)
                .all()
            )

            return {
                "total_runs": total_runs,
                "total_events": total_events,
                "total_steps": total_steps,
                "by_status": {row[0]: row[1] for row in status_rows},
                "by_scenario": {row[0]: row[1] for row in scenario_rows},
                "by_event_type": {row[0]: row[1] for row in event_type_rows},
            }

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------

    def delete_run(self, run_id: str) -> bool:
        """Delete a run and all its data (cascade)."""
        with self.SessionFactory() as db:
            run = db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
            if run is None:
                return False
            db.delete(run)
            db.commit()
            logger.info("Deleted datalake run %s", run_id)
            return True

    def close(self) -> None:
        """Dispose of the engine and connection pool."""
        self.engine.dispose()
        logger.info("Datalake connections closed.")
