"""Persist de-identified AI inference health events."""
from alembic import op
import sqlalchemy as sa

revision = "20261119_0011"
down_revision = "20261103_0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_inference_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("feature", sa.String(32), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("fallback_used", sa.Boolean(),
                  server_default=sa.false(), nullable=False),
        sa.Column("low_confidence", sa.Boolean(),
                  server_default=sa.false(), nullable=False),
        sa.Column("age_band", sa.String(16), nullable=True),
        sa.Column("request_id", sa.String(32), nullable=True),
    )
    op.create_index(
        "ix_ai_inference_events_created_at",
        "ai_inference_events",
        ["created_at"],
    )
    op.create_index(
        "ix_ai_inference_events_feature",
        "ai_inference_events",
        ["feature"],
    )


def downgrade():
    op.drop_index("ix_ai_inference_events_feature", table_name="ai_inference_events")
    op.drop_index("ix_ai_inference_events_created_at", table_name="ai_inference_events")
    op.drop_table("ai_inference_events")
