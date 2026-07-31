"""Add triage sessions, consultations and signed prescriptions.

Revision ID: 20260801_0004
Revises: 20260801_0003
Create Date: 2026-07-31 19:10:01.324560
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



revision: str = "20260801_0004"
down_revision: Union[str, Sequence[str], None] = "20260801_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('triage_sessions',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('patient_id', sa.String(), nullable=True),
    sa.Column('user_id', sa.String(), nullable=True),
    sa.Column('input_text', sa.Text(), nullable=False),
    sa.Column('language', sa.String(), nullable=True),
    sa.Column('age_years', sa.Integer(), nullable=True),
    sa.Column('temperature_c', sa.Float(), nullable=True),
    sa.Column('engine', sa.String(), server_default='rules', nullable=False),
    sa.Column('model_version', sa.String(), nullable=True),
    sa.Column('triage_level', sa.String(), nullable=False),
    sa.Column('severity_level', sa.Integer(), nullable=True),
    sa.Column('possible_condition', sa.String(), nullable=True),
    sa.Column('recommended_specialty', sa.String(), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('matched_symptoms', sa.JSON(), nullable=True),
    sa.Column('safety_flags', sa.JSON(), nullable=True),
    sa.Column('latitude', sa.Float(), nullable=True),
    sa.Column('longitude', sa.Float(), nullable=True),
    sa.Column('reviewed_by', sa.String(), nullable=True),
    sa.Column('clinician_level', sa.Integer(), nullable=True),
    sa.Column('review_note', sa.Text(), nullable=True),
    sa.Column('was_overridden', sa.Boolean(), server_default=sa.text('0'), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
    sa.ForeignKeyConstraint(['reviewed_by'], ['doctors.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('consultations',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('appointment_id', sa.String(), nullable=False),
    sa.Column('doctor_id', sa.String(), nullable=False),
    sa.Column('patient_id', sa.String(), nullable=False),
    sa.Column('triage_session_id', sa.String(), nullable=True),
    sa.Column('status', sa.String(), server_default='OPEN', nullable=False),
    sa.Column('chief_complaint', sa.Text(), nullable=True),
    sa.Column('examination_notes', sa.Text(), nullable=True),
    sa.Column('diagnosis', sa.String(), nullable=True),
    sa.Column('advice', sa.Text(), nullable=True),
    sa.Column('follow_up_date', sa.String(), nullable=True),
    sa.Column('investigations', sa.JSON(), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('is_signed', sa.Boolean(), server_default=sa.text('0'), nullable=True),
    sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ),
    sa.ForeignKeyConstraint(['doctor_id'], ['doctors.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
    sa.ForeignKeyConstraint(['triage_session_id'], ['triage_sessions.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('appointment_id')
    )
    op.create_table('consultation_messages',
    sa.Column('sequence', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('consultation_id', sa.String(), nullable=False),
    sa.Column('sender_user_id', sa.String(), nullable=False),
    sa.Column('sender_role', sa.String(), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['consultation_id'], ['consultations.id'], ),
    sa.ForeignKeyConstraint(['sender_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('sequence'),
    sa.UniqueConstraint('id')
    )
    op.create_index(op.f('ix_consultation_messages_consultation_id'), 'consultation_messages', ['consultation_id'], unique=False)
    op.create_table('prescription_records',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('consultation_id', sa.String(), nullable=True),
    sa.Column('appointment_id', sa.String(), nullable=True),
    sa.Column('doctor_id', sa.String(), nullable=False),
    sa.Column('patient_id', sa.String(), nullable=False),
    sa.Column('diagnosis', sa.String(), nullable=True),
    sa.Column('advice', sa.Text(), nullable=True),
    sa.Column('verification_code', sa.String(), nullable=False),
    sa.Column('signature', sa.String(), nullable=False),
    sa.Column('issued_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('valid_until', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.String(), server_default='ACTIVE', nullable=False),
    sa.Column('dispensed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('dispensed_by', sa.String(), nullable=True),
    sa.Column('interaction_report', sa.JSON(), nullable=True),
    sa.Column('is_cancelled', sa.Boolean(), server_default=sa.text('0'), nullable=True),
    sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ),
    sa.ForeignKeyConstraint(['consultation_id'], ['consultations.id'], ),
    sa.ForeignKeyConstraint(['dispensed_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['doctor_id'], ['doctors.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_prescription_records_verification_code'), 'prescription_records', ['verification_code'], unique=True)
    op.create_table('prescription_lines',
    sa.Column('sequence', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('prescription_id', sa.String(), nullable=False),
    sa.Column('medicine_name', sa.String(), nullable=False),
    sa.Column('generic_name', sa.String(), nullable=True),
    sa.Column('strength', sa.String(), nullable=True),
    sa.Column('dosage_form', sa.String(), nullable=True),
    sa.Column('frequency', sa.String(), nullable=False),
    sa.Column('duration', sa.String(), nullable=False),
    sa.Column('route', sa.String(), nullable=True),
    sa.Column('instructions', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['prescription_id'], ['prescription_records.id'], ),
    sa.PrimaryKeyConstraint('sequence'),
    sa.UniqueConstraint('id')
    )
    op.create_index(op.f('ix_prescription_lines_prescription_id'), 'prescription_lines', ['prescription_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_prescription_lines_prescription_id'), table_name='prescription_lines')
    op.drop_table('prescription_lines')
    op.drop_index(op.f('ix_prescription_records_verification_code'), table_name='prescription_records')
    op.drop_table('prescription_records')
    op.drop_index(op.f('ix_consultation_messages_consultation_id'), table_name='consultation_messages')
    op.drop_table('consultation_messages')
    op.drop_table('consultations')
    op.drop_table('triage_sessions')
