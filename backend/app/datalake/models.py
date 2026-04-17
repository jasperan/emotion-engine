"""
SQLAlchemy ORM models for the EmotionSim datalake.

Uses oracledb dialect with Oracle-native types:
  - VARCHAR2, CLOB, NUMBER, TIMESTAMP for standard columns
  - JSON constraints on CLOB columns
  - UUIDs stored as VARCHAR2(36)
"""

import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class DatalakeBase(DeclarativeBase):
    """Declarative base for datalake models (separate from app Base)."""
    pass


def generate_uuid() -> str:
    return str(uuid.uuid4())


class SimulationRun(DatalakeBase):
    """One row per simulation run."""

    __tablename__ = "simulation_runs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    scenario_name = Column(String(256), nullable=False, index=True)
    scenario_id = Column(String(36), nullable=True)
    model = Column(String(128), nullable=False, index=True)
    fallback_model = Column(String(128), nullable=True)
    status = Column(String(20), nullable=False, default="running", index=True)
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)
    total_steps = Column(Integer, nullable=True)
    agent_count = Column(Integer, nullable=True)
    seed = Column(Integer, nullable=True)
    run_config = Column(Text, nullable=True)
    final_metrics = Column(Text, nullable=True)

    # Relationships
    steps = relationship(
        "SimulationStep",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="SimulationStep.step_number",
    )
    events = relationship(
        "AgentEvent",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    plans = relationship(
        "AgentPlan",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    metrics = relationship(
        "SimulationMetric",
        back_populates="run",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_runs_scenario_model", "scenario_name", "model"),
    )

    def to_dict(self) -> dict:
        import json
        return {
            "id": self.id,
            "scenario_name": self.scenario_name,
            "scenario_id": self.scenario_id,
            "model": self.model,
            "fallback_model": self.fallback_model,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_steps": self.total_steps,
            "agent_count": self.agent_count,
            "seed": self.seed,
            "run_config": json.loads(self.run_config) if self.run_config else None,
            "final_metrics": json.loads(self.final_metrics) if self.final_metrics else None,
        }


class SimulationStep(DatalakeBase):
    """One row per tick/step in a simulation."""

    __tablename__ = "simulation_steps"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(
        String(36),
        ForeignKey("simulation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_number = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    world_state = Column(Text, nullable=True)
    active_agents = Column(Integer, nullable=True)
    messages_count = Column(Integer, nullable=True)

    run = relationship("SimulationRun", back_populates="steps")

    __table_args__ = (
        Index("ix_steps_run_step", "run_id", "step_number"),
    )

    def to_dict(self) -> dict:
        import json
        return {
            "id": self.id,
            "run_id": self.run_id,
            "step_number": self.step_number,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "world_state": json.loads(self.world_state) if self.world_state else None,
            "active_agents": self.active_agents,
            "messages_count": self.messages_count,
        }


class AgentEvent(DatalakeBase):
    """Every agent action, message, movement, error: the full event stream."""

    __tablename__ = "agent_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(
        String(36),
        ForeignKey("simulation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_number = Column(Integer, nullable=False)
    agent_name = Column(String(128), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    data = Column(Text, nullable=False)

    run = relationship("SimulationRun", back_populates="events")

    __table_args__ = (
        Index("ix_events_run_step", "run_id", "step_number"),
    )

    def to_dict(self) -> dict:
        import json
        return {
            "id": self.id,
            "run_id": self.run_id,
            "step_number": self.step_number,
            "agent_name": self.agent_name,
            "event_type": self.event_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "data": json.loads(self.data) if self.data else None,
        }


class AgentPlan(DatalakeBase):
    """Cognitive architecture plan snapshots."""

    __tablename__ = "agent_plans"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(
        String(36),
        ForeignKey("simulation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_number = Column(Integer, nullable=False)
    agent_name = Column(String(128), nullable=False, index=True)
    goal = Column(String(512), nullable=False)
    steps = Column(Text, nullable=False)
    current_step = Column(Integer, nullable=False)
    total_steps = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime, default=func.now(), nullable=False)

    run = relationship("SimulationRun", back_populates="plans")

    __table_args__ = (
        Index("ix_plans_run_step", "run_id", "step_number"),
    )

    def to_dict(self) -> dict:
        import json
        return {
            "id": self.id,
            "run_id": self.run_id,
            "step_number": self.step_number,
            "agent_name": self.agent_name,
            "goal": self.goal,
            "steps": json.loads(self.steps) if self.steps else [],
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SimulationMetric(DatalakeBase):
    """Per-step or per-run aggregate metrics."""

    __tablename__ = "simulation_metrics"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(
        String(36),
        ForeignKey("simulation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_number = Column(Integer, nullable=True)
    metric_name = Column(String(128), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    run = relationship("SimulationRun", back_populates="metrics")

    __table_args__ = (
        Index("ix_metrics_run_step", "run_id", "step_number"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "step_number": self.step_number,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
