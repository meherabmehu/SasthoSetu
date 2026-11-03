"""Patient care consent, revocable sessions and single-use account tokens."""
from alembic import op
import sqlalchemy as sa

revision = "20261103_0009"
down_revision = "20260803_0008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False,
                                     server_default="0"))
    op.create_table(
        "account_tokens",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("purpose", sa.String(16), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_account_tokens_user_id", "account_tokens", ["user_id"])
    op.create_table(
        "patient_care_consents",
        sa.Column("patient_id", sa.String(), sa.ForeignKey("patients.id"), primary_key=True),
        sa.Column("doctor_id", sa.String(), sa.ForeignKey("doctors.id"), primary_key=True),
        sa.Column("granted", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("patient_care_consents")
    op.drop_index("ix_account_tokens_user_id", table_name="account_tokens")
    op.drop_table("account_tokens")
    op.drop_column("users", "token_version")
