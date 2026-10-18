"""training sessions: live sessions and their stored records

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "training_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("scenario_id", sa.String(64), nullable=False),
        sa.Column("scenario_version", sa.String(32), nullable=False),
        sa.Column("seed", sa.BigInteger, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ticks", sa.Integer, nullable=False, server_default="0"),
        sa.Column("final_state_hash", sa.String(64), nullable=True),
        sa.Column("event_head", sa.String(64), nullable=True),
        sa.Column("event_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("record", sa.Text, nullable=True),
    )
    op.create_index("ix_training_sessions_user_id", "training_sessions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_training_sessions_user_id", table_name="training_sessions")
    op.drop_table("training_sessions")
