"""Add a created_at to notifications.

Revision ID: 20260803_0008
Revises: 20260803_0007
Create Date: 2026-08-03

Notifications were recorded without a timestamp, so the list had nothing to
be ordered by and nothing to show for when something happened. uuid ids do
not sort usefully. Existing rows get the migration's run time, which is the
best available answer for "when was this written".
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260803_0008"
down_revision: Union[str, Sequence[str], None] = "20260803_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def downgrade() -> None:
    op.drop_column("notifications", "created_at")
