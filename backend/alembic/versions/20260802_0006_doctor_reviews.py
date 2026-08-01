"""Add proof-backed doctor reviews and cached rating summaries.

Revision ID: 20260802_0006
Revises: 20260801_0005
Create Date: 2026-08-01 19:36:33.959910
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



revision: str = "20260802_0006"
down_revision: Union[str, Sequence[str], None] = "20260801_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('doctor_rating_summaries',
    sa.Column('doctor_id', sa.String(), nullable=False),
    sa.Column('average_rating', sa.Float(), server_default='0', nullable=False),
    sa.Column('bayesian_rating', sa.Float(), server_default='0', nullable=False),
    sa.Column('review_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('verified_review_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('average_explanation', sa.Float(), nullable=True),
    sa.Column('average_punctuality', sa.Float(), nullable=True),
    sa.Column('average_respect', sa.Float(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
    sa.ForeignKeyConstraint(['doctor_id'], ['doctors.id'], ),
    sa.PrimaryKeyConstraint('doctor_id')
    )
    op.create_table('doctor_reviews',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('doctor_id', sa.String(), nullable=False),
    sa.Column('patient_id', sa.String(), nullable=False),
    sa.Column('appointment_id', sa.String(), nullable=False),
    sa.Column('consultation_id', sa.String(), nullable=True),
    sa.Column('rating', sa.Integer(), nullable=False),
    sa.Column('rating_explanation', sa.Integer(), nullable=True),
    sa.Column('rating_punctuality', sa.Integer(), nullable=True),
    sa.Column('rating_respect', sa.Integer(), nullable=True),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('language', sa.String(), nullable=True),
    sa.Column('proof_type', sa.String(), nullable=False),
    sa.Column('proof_weight', sa.Float(), server_default='1.0', nullable=False),
    sa.Column('proof_reference', sa.String(), nullable=True),
    sa.Column('is_verified', sa.Boolean(), server_default='1', nullable=True),
    sa.Column('is_hidden', sa.Boolean(), server_default=sa.text('0'), nullable=True),
    sa.Column('hidden_reason', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ),
    sa.ForeignKeyConstraint(['consultation_id'], ['consultations.id'], ),
    sa.ForeignKeyConstraint(['doctor_id'], ['doctors.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('appointment_id', name='uq_review_per_appointment')
    )
    op.create_index(op.f('ix_doctor_reviews_doctor_id'), 'doctor_reviews', ['doctor_id'], unique=False)
    op.create_index(op.f('ix_doctor_reviews_patient_id'), 'doctor_reviews', ['patient_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_doctor_reviews_patient_id'), table_name='doctor_reviews')
    op.drop_index(op.f('ix_doctor_reviews_doctor_id'), table_name='doctor_reviews')
    op.drop_table('doctor_reviews')
    op.drop_table('doctor_rating_summaries')
