"""Add user_id to signals, positions, and execution_orders for multi-tenancy.

Revision ID: 011
Revises: 010
Create Date: 2025-12-25
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '011'
down_revision: Union[str, None] = '010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add user_id to signals table
    op.add_column('signals', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_index('ix_signal_user_id', 'signals', ['user_id'], unique=False)
    op.create_foreign_key('fk_signals_user_id', 'signals', 'users', ['user_id'], ['id'])

    # Add user_id to positions table
    op.add_column('positions', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_index('ix_position_user_id', 'positions', ['user_id'], unique=False)
    op.create_foreign_key('fk_positions_user_id', 'positions', 'users', ['user_id'], ['id'])

    # Add user_id to execution_orders table
    op.add_column('execution_orders', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_index('ix_execution_order_user_id', 'execution_orders', ['user_id'], unique=False)
    op.create_foreign_key('fk_execution_orders_user_id', 'execution_orders', 'users', ['user_id'], ['id'])

    # Note: In production, you would need to:
    # 1. Backfill user_id for existing rows
    # 2. Then alter columns to NOT NULL
    # For new deployments, the columns will be NOT NULL from the start


def downgrade() -> None:
    # Remove from execution_orders
    op.drop_constraint('fk_execution_orders_user_id', 'execution_orders', type_='foreignkey')
    op.drop_index('ix_execution_order_user_id', table_name='execution_orders')
    op.drop_column('execution_orders', 'user_id')

    # Remove from positions
    op.drop_constraint('fk_positions_user_id', 'positions', type_='foreignkey')
    op.drop_index('ix_position_user_id', table_name='positions')
    op.drop_column('positions', 'user_id')

    # Remove from signals
    op.drop_constraint('fk_signals_user_id', 'signals', type_='foreignkey')
    op.drop_index('ix_signal_user_id', table_name='signals')
    op.drop_column('signals', 'user_id')
