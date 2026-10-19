"""scenarios kept beyond the shipped packs (authored in the editor or generated and saved)

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scenario_records",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.Column("spec", sa.Text, nullable=False),
        sa.Column("spec_sha256", sa.String(64), nullable=False),
        sa.Column("yaml", sa.Text, nullable=True),
        sa.Column("request", sa.Text, nullable=True),
        sa.Column("code", sa.String(96), nullable=True),
        sa.Column("checks", sa.Text, nullable=True),
        sa.Column("features", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scenario_records_owner_id", "scenario_records", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_scenario_records_owner_id", table_name="scenario_records")
    op.drop_table("scenario_records")
