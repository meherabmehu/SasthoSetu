"""Add hospitals, wards, staff assignments and bed status history.

Revision ID: 20260801_0003
Revises: b49ae5881a18
Create Date: 2026-08-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260801_0003"
down_revision: Union[str, Sequence[str], None] = "b49ae5881a18"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hospitals",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("district", sa.String(), nullable=False),
        sa.Column("area", sa.String(), nullable=True),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column(
            "has_emergency",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_hospitals_district", "hospitals", ["district"])

    op.create_table(
        "wards",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("hospital_id", sa.String(), nullable=False),
        sa.Column("ward_type", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "total_beds", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "occupied_beds", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hospital_id", "ward_type", name="uq_ward_type_per_hospital"),
    )

    op.create_table(
        "hospital_staff",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("hospital_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column(
            "staff_role",
            sa.String(),
            server_default="WARD_MANAGER",
            nullable=False,
        ),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.true(), nullable=True
        ),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hospital_id", "user_id", name="uq_staff_per_hospital"),
    )

    op.create_table(
        "bed_status_history",
        sa.Column("sequence", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("ward_id", sa.String(), nullable=False),
        sa.Column("occupied_beds", sa.Integer(), nullable=False),
        sa.Column("total_beds", sa.Integer(), nullable=False),
        sa.Column("recorded_by", sa.String(), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "is_synthetic",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["ward_id"], ["wards.id"]),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("sequence"),
        sa.UniqueConstraint("id"),
    )
    op.create_index(
        "ix_bed_history_ward_time",
        "bed_status_history",
        ["ward_id", "sequence"],
    )


def downgrade() -> None:
    op.drop_index("ix_bed_history_ward_time", table_name="bed_status_history")
    op.drop_table("bed_status_history")
    op.drop_table("hospital_staff")
    op.drop_table("wards")
    op.drop_index("ix_hospitals_district", table_name="hospitals")
    op.drop_table("hospitals")
