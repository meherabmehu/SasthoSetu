"""Add lab and pharmacy providers, orders, stock and payments.

Revision ID: 20260801_0005
Revises: 20260801_0004
Create Date: 2026-07-31 19:20:16.836984
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



revision: str = "20260801_0005"
down_revision: Union[str, Sequence[str], None] = "20260801_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('providers',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('code', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('provider_type', sa.String(), nullable=False),
    sa.Column('district', sa.String(), nullable=False),
    sa.Column('area', sa.String(), nullable=True),
    sa.Column('address', sa.String(), nullable=True),
    sa.Column('phone', sa.String(), nullable=True),
    sa.Column('licence_number', sa.String(), nullable=True),
    sa.Column('latitude', sa.Float(), nullable=True),
    sa.Column('longitude', sa.Float(), nullable=True),
    sa.Column('is_verified', sa.Boolean(), server_default=sa.text('0'), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('1'), nullable=True),
    sa.Column('owner_user_id', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )
    op.create_index(op.f('ix_providers_district'), 'providers', ['district'], unique=False)
    op.create_index(op.f('ix_providers_provider_type'), 'providers', ['provider_type'], unique=False)
    op.create_table('lab_tests',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('provider_id', sa.String(), nullable=False),
    sa.Column('code', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('sample_type', sa.String(), nullable=True),
    sa.Column('price_bdt', sa.Float(), nullable=False),
    sa.Column('turnaround_hours', sa.Integer(), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('1'), nullable=True),
    sa.ForeignKeyConstraint(['provider_id'], ['providers.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('provider_id', 'code', name='uq_test_code_per_provider')
    )
    op.create_index(op.f('ix_lab_tests_provider_id'), 'lab_tests', ['provider_id'], unique=False)
    op.create_table('pharmacy_stock',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('provider_id', sa.String(), nullable=False),
    sa.Column('brand_name', sa.String(), nullable=False),
    sa.Column('generic_name', sa.String(), nullable=False),
    sa.Column('strength', sa.String(), nullable=True),
    sa.Column('unit_price_bdt', sa.Float(), nullable=False),
    sa.Column('quantity_available', sa.Integer(), server_default='0', nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
    sa.ForeignKeyConstraint(['provider_id'], ['providers.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('provider_id', 'generic_name', 'strength', name='uq_stock_item_per_provider')
    )
    op.create_index(op.f('ix_pharmacy_stock_generic_name'), 'pharmacy_stock', ['generic_name'], unique=False)
    op.create_index(op.f('ix_pharmacy_stock_provider_id'), 'pharmacy_stock', ['provider_id'], unique=False)
    op.create_table('lab_orders',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('order_code', sa.String(), nullable=False),
    sa.Column('provider_id', sa.String(), nullable=False),
    sa.Column('lab_test_id', sa.String(), nullable=False),
    sa.Column('patient_id', sa.String(), nullable=False),
    sa.Column('ordered_by_doctor_id', sa.String(), nullable=True),
    sa.Column('consultation_id', sa.String(), nullable=True),
    sa.Column('status', sa.String(), server_default='REQUESTED', nullable=False),
    sa.Column('price_bdt', sa.Float(), nullable=False),
    sa.Column('share_with_doctor', sa.Boolean(), server_default=sa.text('1'), nullable=True),
    sa.Column('result_summary', sa.Text(), nullable=True),
    sa.Column('result_values', sa.JSON(), nullable=True),
    sa.Column('result_file_id', sa.String(), nullable=True),
    sa.Column('is_abnormal', sa.Boolean(), server_default=sa.text('0'), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('collected_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('reported_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['consultation_id'], ['consultations.id'], ),
    sa.ForeignKeyConstraint(['lab_test_id'], ['lab_tests.id'], ),
    sa.ForeignKeyConstraint(['ordered_by_doctor_id'], ['doctors.id'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ),
    sa.ForeignKeyConstraint(['provider_id'], ['providers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_lab_orders_order_code'), 'lab_orders', ['order_code'], unique=True)
    op.create_index(op.f('ix_lab_orders_patient_id'), 'lab_orders', ['patient_id'], unique=False)
    op.create_index(op.f('ix_lab_orders_provider_id'), 'lab_orders', ['provider_id'], unique=False)
    op.create_table('payments',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('reference', sa.String(), nullable=False),
    sa.Column('idempotency_key', sa.String(), nullable=False),
    sa.Column('payer_user_id', sa.String(), nullable=False),
    sa.Column('purpose', sa.String(), nullable=False),
    sa.Column('appointment_id', sa.String(), nullable=True),
    sa.Column('lab_order_id', sa.String(), nullable=True),
    sa.Column('provider_id', sa.String(), nullable=True),
    sa.Column('amount_bdt', sa.Float(), nullable=False),
    sa.Column('platform_fee_bdt', sa.Float(), server_default='0', nullable=False),
    sa.Column('payout_bdt', sa.Float(), server_default='0', nullable=False),
    sa.Column('method', sa.String(), nullable=False),
    sa.Column('status', sa.String(), server_default='PENDING', nullable=False),
    sa.Column('gateway_reference', sa.String(), nullable=True),
    sa.Column('gateway_payload', sa.JSON(), nullable=True),
    sa.Column('failure_reason', sa.Text(), nullable=True),
    sa.Column('refunded_amount_bdt', sa.Float(), server_default='0', nullable=False),
    sa.Column('is_reconciled', sa.Boolean(), server_default=sa.text('0'), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ),
    sa.ForeignKeyConstraint(['lab_order_id'], ['lab_orders.id'], ),
    sa.ForeignKeyConstraint(['payer_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['provider_id'], ['providers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_payments_idempotency_key'), 'payments', ['idempotency_key'], unique=True)
    op.create_index(op.f('ix_payments_payer_user_id'), 'payments', ['payer_user_id'], unique=False)
    op.create_index(op.f('ix_payments_reference'), 'payments', ['reference'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_payments_reference'), table_name='payments')
    op.drop_index(op.f('ix_payments_payer_user_id'), table_name='payments')
    op.drop_index(op.f('ix_payments_idempotency_key'), table_name='payments')
    op.drop_table('payments')
    op.drop_index(op.f('ix_lab_orders_provider_id'), table_name='lab_orders')
    op.drop_index(op.f('ix_lab_orders_patient_id'), table_name='lab_orders')
    op.drop_index(op.f('ix_lab_orders_order_code'), table_name='lab_orders')
    op.drop_table('lab_orders')
    op.drop_index(op.f('ix_pharmacy_stock_provider_id'), table_name='pharmacy_stock')
    op.drop_index(op.f('ix_pharmacy_stock_generic_name'), table_name='pharmacy_stock')
    op.drop_table('pharmacy_stock')
    op.drop_index(op.f('ix_lab_tests_provider_id'), table_name='lab_tests')
    op.drop_table('lab_tests')
    op.drop_index(op.f('ix_providers_provider_type'), table_name='providers')
    op.drop_index(op.f('ix_providers_district'), table_name='providers')
    op.drop_table('providers')
