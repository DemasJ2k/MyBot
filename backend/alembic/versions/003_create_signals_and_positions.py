"""create signals and positions tables

Revision ID: 003
Revises: 002
Create Date: 2025-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Positions table (must be created first due to foreign key)
    op.create_table(
        'positions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('strategy_name', sa.String(length=50), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('side', sa.Enum('long', 'short', name='positionside'), nullable=False),
        sa.Column('status', sa.Enum('open', 'closed', 'partial', name='positionstatus'), nullable=False, default='open'),
        sa.Column('entry_price', sa.Float(), nullable=False),
        sa.Column('position_size', sa.Float(), nullable=False),
        sa.Column('entry_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('exit_price', sa.Float(), nullable=True),
        sa.Column('exit_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('stop_loss', sa.Float(), nullable=False),
        sa.Column('take_profit', sa.Float(), nullable=False),
        sa.Column('trailing_stop', sa.Float(), nullable=True),
        sa.Column('unrealized_pnl', sa.Float(), nullable=False, default=0.0),
        sa.Column('realized_pnl', sa.Float(), nullable=True),
        sa.Column('commission_paid', sa.Float(), nullable=False, default=0.0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_position_strategy_name', 'positions', ['strategy_name'])
    op.create_index('ix_position_symbol', 'positions', ['symbol'])
    op.create_index('ix_position_status', 'positions', ['status'])
    op.create_index('ix_position_entry_time', 'positions', ['entry_time'])
    op.create_index('ix_position_strategy_status', 'positions', ['strategy_name', 'status'])
    op.create_index('ix_position_symbol_status', 'positions', ['symbol', 'status'])

    # Signals table
    op.create_table(
        'signals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('strategy_name', sa.String(length=50), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('signal_type', sa.Enum('long', 'short', name='signaltype'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'active', 'executed', 'cancelled', 'expired', name='signalstatus'), nullable=False, default='pending'),
        sa.Column('entry_price', sa.Float(), nullable=False),
        sa.Column('stop_loss', sa.Float(), nullable=False),
        sa.Column('take_profit', sa.Float(), nullable=False),
        sa.Column('risk_percent', sa.Float(), nullable=False),
        sa.Column('position_size', sa.Float(), nullable=True),
        sa.Column('timeframe', sa.String(length=10), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False, default=0.0),
        sa.Column('reason', sa.String(length=500), nullable=True),
        sa.Column('signal_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expiry_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('position_id', sa.Integer(), sa.ForeignKey('positions.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_signal_strategy_name', 'signals', ['strategy_name'])
    op.create_index('ix_signal_symbol', 'signals', ['symbol'])
    op.create_index('ix_signal_status', 'signals', ['status'])
    op.create_index('ix_signal_time', 'signals', ['signal_time'])
    op.create_index('ix_signal_strategy_status', 'signals', ['strategy_name', 'status'])
    op.create_index('ix_signal_symbol_status', 'signals', ['symbol', 'status'])


def downgrade() -> None:
    op.drop_index('ix_signal_symbol_status', table_name='signals')
    op.drop_index('ix_signal_strategy_status', table_name='signals')
    op.drop_index('ix_signal_time', table_name='signals')
    op.drop_index('ix_signal_status', table_name='signals')
    op.drop_index('ix_signal_symbol', table_name='signals')
    op.drop_index('ix_signal_strategy_name', table_name='signals')
    op.drop_table('signals')

    op.drop_index('ix_position_symbol_status', table_name='positions')
    op.drop_index('ix_position_strategy_status', table_name='positions')
    op.drop_index('ix_position_entry_time', table_name='positions')
    op.drop_index('ix_position_status', table_name='positions')
    op.drop_index('ix_position_symbol', table_name='positions')
    op.drop_index('ix_position_strategy_name', table_name='positions')
    op.drop_table('positions')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS signalstatus")
    op.execute("DROP TYPE IF EXISTS signaltype")
    op.execute("DROP TYPE IF EXISTS positionstatus")
    op.execute("DROP TYPE IF EXISTS positionside")
