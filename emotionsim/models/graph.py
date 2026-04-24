"""SQLAlchemy models for graph-based knowledge and memory storage."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from emotionsim.core.database import Base, OracleJSON


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GraphModel(Base):
    """A named knowledge graph container."""

    __tablename__ = "graphs"

    graph_id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False)
    ontology_json = Column(OracleJSON, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    entities = relationship("EntityModel", back_populates="graph", cascade="all, delete-orphan")
    edges = relationship("EdgeModel", back_populates="graph", cascade="all, delete-orphan")


class EntityModel(Base):
    """A node in a knowledge graph (person, place, concept, etc.)."""

    __tablename__ = "graph_entities"
    __table_args__ = (
        Index("ix_graph_entities_graph_type", "graph_id", "type"),
        Index("ix_graph_entities_name", "name"),
    )

    entity_id = Column(String(36), primary_key=True, default=_uuid)
    graph_id = Column(String(36), ForeignKey("graphs.graph_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    type = Column(String(100), nullable=False)
    summary = Column(Text, nullable=True, default="")
    attributes_json = Column(OracleJSON, nullable=True)
    embedding_json = Column(OracleJSON, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    graph = relationship("GraphModel", back_populates="entities")
    outgoing_edges = relationship(
        "EdgeModel", foreign_keys="EdgeModel.source_id", back_populates="source_entity"
    )
    incoming_edges = relationship(
        "EdgeModel", foreign_keys="EdgeModel.target_id", back_populates="target_entity"
    )


class EdgeModel(Base):
    """A directed edge between two entities in a knowledge graph."""

    __tablename__ = "graph_edges"
    __table_args__ = (
        Index("ix_graph_edges_graph_type", "graph_id", "type"),
        Index("ix_graph_edges_source", "source_id"),
        Index("ix_graph_edges_target", "target_id"),
    )

    edge_id = Column(String(36), primary_key=True, default=_uuid)
    graph_id = Column(String(36), ForeignKey("graphs.graph_id", ondelete="CASCADE"), nullable=False)
    source_id = Column(
        String(36), ForeignKey("graph_entities.entity_id", ondelete="CASCADE"), nullable=False
    )
    target_id = Column(
        String(36), ForeignKey("graph_entities.entity_id", ondelete="CASCADE"), nullable=False
    )
    type = Column(String(100), nullable=False)
    fact = Column(Text, nullable=True, default="")
    weight = Column(Float, default=1.0, nullable=False)
    embedding_json = Column(OracleJSON, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    graph = relationship("GraphModel", back_populates="edges")
    source_entity = relationship("EntityModel", foreign_keys=[source_id], back_populates="outgoing_edges")
    target_entity = relationship("EntityModel", foreign_keys=[target_id], back_populates="incoming_edges")


class MemoryNodeModel(Base):
    """An episodic memory node for an agent within a simulation run."""

    __tablename__ = "graph_memories"
    __table_args__ = (
        Index("ix_graph_memories_run_agent", "run_id", "agent_id"),
        Index("ix_graph_memories_run_step", "run_id", "step_number"),
    )

    memory_id = Column(String(36), primary_key=True, default=_uuid)
    run_id = Column(String(36), nullable=False)
    agent_id = Column(String(36), nullable=False)
    memory_type = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    importance = Column(Integer, default=0, nullable=False)
    emotional_valence = Column(Float, default=0.0, nullable=False)
    step_number = Column(Integer, default=0, nullable=False)
    embedding_json = Column(OracleJSON, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class MemoryEdgeModel(Base):
    """A link between two memory nodes or between a memory and a graph entity."""

    __tablename__ = "graph_memory_edges"
    __table_args__ = (
        Index("ix_graph_memory_edges_source", "source_id"),
        Index("ix_graph_memory_edges_target", "target_id"),
    )

    edge_id = Column(String(36), primary_key=True, default=_uuid)
    source_id = Column(String(36), nullable=False)
    target_id = Column(String(36), nullable=False)
    type = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
