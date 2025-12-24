"""Add execution engine tables

Revision ID: 009
Revises: 008
Create Date: 2024-12-25
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create execution_orders table
    op.create_table(
        'execution_orders',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('client_order_id', sa.String(100), nullable=False),
        sa.Column('broker_order_id', sa.String(100), nullable=True),
        sa.Column('broker_type', sa.String(50), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('order_type', sa.String(50), nullable=False),
        sa.Column('side', sa.String(50), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('stop_price', sa.Float(), nullable=True),
        sa.Column('stop_loss', sa.Float(), nullable=True),
        sa.Column('take_profit', sa.Float(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('filled_quantity', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('average_fill_price', sa.Float(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('filled_at', sa.DateTime(), nullable=True),
        sa.Column('signal_id', sa.Integer(), sa.ForeignKey('signals.id'), nullable=True),
        sa.Column('position_id', sa.Integer(), sa.ForeignKey('positions.id'), nullable=True),
        sa.Column('strategy_name', sa.String(50), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('extra_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_execution_orders_client_order_id', 'execution_orders', ['client_order_id'], unique=True)
    op.create_index('ix_execution_orders_broker_order_id', 'execution_orders', ['broker_order_id'])
    op.create_index('ix_execution_orders_symbol', 'execution_orders', ['symbol'])
    op.create_index('ix_execution_orders_status', 'execution_orders', ['status'])
    op.create_index('ix_execution_orders_strategy_name', 'execution_orders', ['strategy_name'])
    op.create_index('ix_execution_order_broker_symbol', 'execution_orders', ['broker_type', 'symbol'])

    # Create execution_logs table
    op.create_table(
        'execution_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('order_id', sa.Integer(), sa.ForeignKey('execution_orders.id'), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('event_data', sa.JSON(), nullable=False),
        sa.Column('old_status', sa.String(50), nullable=True),
        sa.Column('new_status', sa.String(50), nullable=True),
        sa.Column('event_time', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_execution_logs_order_id', 'execution_logs', ['order_id'])
    op.create_index('ix_execution_logs_event_type', 'execution_logs', ['event_type'])
    op.create_index('ix_execution_logs_event_time', 'execution_logs', ['event_time'])

    # Create broker_connections table
    op.create_table(
        'broker_connections',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('broker_type', sa.String(50), nullable=False),
        sa.Column('credentials', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('is_connected', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('last_health_check', sa.DateTime(), nullable=True),
        sa.Column('last_connection_time', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_broker_connections_broker_type', 'broker_connections', ['broker_type'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_broker_connections_broker_type', table_name='broker_connections')
    op.drop_table('broker_connections')
    
    op.drop_index('ix_execution_logs_event_time', table_name='execution_logs')
    op.drop_index('ix_execution_logs_event_type', table_name='execution_logs')
    op.drop_index('ix_execution_logs_order_id', table_name='execution_logs')
    op.drop_table('execution_logs')
    
    op.drop_index('ix_execution_order_broker_symbol', table_name='execution_orders')
    op.drop_index('ix_execution_orders_strategy_name', table_name='execution_orders')
    op.drop_index('ix_execution_orders_status', table_name='execution_orders')
    op.drop_index('ix_execution_orders_symbol', table_name='execution_orders')
    op.drop_index('ix_execution_orders_broker_order_id', table_name='execution_orders')
    op.drop_index('ix_execution_orders_client_order_id', table_name='execution_orders')
    op.drop_table('execution_orders')
