"""a stored score for each ended training session

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("training_sessions") as batch:
        batch.add_column(sa.Column("score", sa.Text, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("training_sessions") as batch:
        batch.drop_column("score")
