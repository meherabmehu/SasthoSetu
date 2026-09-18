"""Store uploaded file contents in the database.

Revision ID: 20260803_0007
Revises: 20260802_0006
Create Date: 2026-08-03

Uploads were written to an ``uploads/`` directory beside the application and
the row only kept the path. That works on a server with a persistent disk and
fails everywhere else: on a serverless host the filesystem is discarded after
the request, and with more than one instance the file lands on whichever
machine served the upload and is missing from the others.

The files are medical records - scans, reports - so losing them is not an
option. They move into the row itself, which is already backed up, already
replicated and already covered by the access rules in the service layer.

Existing rows keep their ``file_path``. The download path reads the column
first and falls back to the path, so anything already on disk stays
reachable until it is re-uploaded.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260803_0007"
down_revision: Union[str, Sequence[str], None] = "20260802_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "file_records",
        sa.Column("content", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "file_records",
        sa.Column("file_size", sa.Integer(), nullable=True),
    )
    # Rows written before this point have a path and no content; rows written
    # after have content and no path. Both are valid, so the column that was
    # required has to stop being required.
    _set_file_path_nullable(True)


def downgrade() -> None:
    _set_file_path_nullable(False)
    op.drop_column("file_records", "file_size")
    op.drop_column("file_records", "content")


def _set_file_path_nullable(nullable: bool) -> None:
    """Relax or restore the NOT NULL on file_path.

    SQLite cannot alter a column in place, so Alembic's batch mode rebuilds
    the table. That rebuild needs to read the existing schema, which means a
    live connection - it cannot run in offline (--sql) mode. Every other
    database alters the column directly, so only SQLite pays that cost.
    """
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("file_records") as batch:
            batch.alter_column(
                "file_path",
                existing_type=sa.String(),
                nullable=nullable,
            )
        return

    op.alter_column(
        "file_records",
        "file_path",
        existing_type=sa.String(),
        nullable=nullable,
    )
