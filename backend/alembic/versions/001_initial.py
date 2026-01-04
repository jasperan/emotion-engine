"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create scenarios table
    op.create_table(
        "scenarios",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("config", sa.JSON, default=dict),
        sa.Column("agent_templates", sa.JSON, default=list),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    
    # Create runs table
    op.create_table(
        "runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scenario_id", sa.String(36), sa.ForeignKey("scenarios.id"), nullable=False),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("current_step", sa.Integer, default=0),
        sa.Column("max_steps", sa.Integer, default=100),
        sa.Column("seed", sa.Integer, nullable=True),
        sa.Column("world_state", sa.JSON, default=dict),
        sa.Column("metrics", sa.JSON, default=dict),
        sa.Column("evaluation", sa.JSON, default=dict),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
    )
    
    # Create agents table
    op.create_table(
        "agents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("model_id", sa.String(100), default="llama3.2"),
        sa.Column("provider", sa.String(50), default="ollama"),
        sa.Column("persona", sa.JSON, default=dict),
        sa.Column("dynamic_state", sa.JSON, default=dict),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    
    # Create steps table
    op.create_table(
        "steps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("step_index", sa.Integer, nullable=False),
        sa.Column("state_snapshot", sa.JSON, default=dict),
        sa.Column("actions", sa.JSON, default=list),
        sa.Column("step_metrics", sa.JSON, default=dict),
        sa.Column("timestamp", sa.DateTime, nullable=False),
    )
    
    # Create messages table
    op.create_table(
        "messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("from_agent_id", sa.String(36), nullable=True),
        sa.Column("to_target", sa.String(255), nullable=False),
        sa.Column("message_type", sa.String(20), default="direct"),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("msg_metadata", sa.JSON, default=dict),
        sa.Column("step_index", sa.Integer, nullable=False),
        sa.Column("timestamp", sa.DateTime, nullable=False),
    )
    
    # Create indexes
    op.create_index("ix_runs_scenario_id", "runs", ["scenario_id"])
    op.create_index("ix_agents_run_id", "agents", ["run_id"])
    op.create_index("ix_steps_run_id", "steps", ["run_id"])
    op.create_index("ix_messages_run_id", "messages", ["run_id"])
    op.create_index("ix_messages_from_agent_id", "messages", ["from_agent_id"])


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("steps")
    op.drop_table("agents")
    op.drop_table("runs")
    op.drop_table("scenarios")

