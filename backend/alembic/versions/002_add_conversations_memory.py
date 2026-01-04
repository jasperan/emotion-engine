"""Add conversations table and agent memory fields

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create conversations table
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("conversation_type", sa.String(50), default="location"),
        sa.Column("participants", sa.JSON, default=list),
        sa.Column("state", sa.String(50), default="active"),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("key_facts", sa.JSON, default=list),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("ended_at", sa.DateTime, nullable=True),
        sa.Column("start_step", sa.Integer, nullable=True),
        sa.Column("end_step", sa.Integer, nullable=True),
        sa.Column("conv_metadata", sa.JSON, default=dict),
    )
    
    # Add memory fields to agents table
    op.add_column(
        "agents",
        sa.Column("memory_snapshot", sa.JSON, default=dict),
    )
    op.add_column(
        "agents",
        sa.Column("relationship_memory", sa.JSON, default=dict),
    )
    
    # Create indexes
    op.create_index("ix_conversations_run_id", "conversations", ["run_id"])
    op.create_index("ix_conversations_location", "conversations", ["location"])


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_conversations_location")
    op.drop_index("ix_conversations_run_id")
    
    # Remove columns from agents
    op.drop_column("agents", "relationship_memory")
    op.drop_column("agents", "memory_snapshot")
    
    # Drop conversations table
    op.drop_table("conversations")

