"""Optional shared rate limits using the application database."""
from alembic import op
import sqlalchemy as sa

revision = "20261103_0010"
down_revision = "20261103_0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("rate_limit_windows",
        sa.Column("client_hash", sa.String(64), primary_key=True),
        sa.Column("window_start", sa.BigInteger(), primary_key=True),
        sa.Column("requests", sa.Integer(), nullable=False))


def downgrade():
    op.drop_table("rate_limit_windows")
