"""Add simulation and execution mode tables

Revision ID: 013_add_simulation_tables
Revises: 012_add_settings_tables
Create Date: 2025-12-26

This migration adds support for:
- Execution mode tracking (SIMULATION/PAPER/LIVE)
- Simulation accounts with virtual balance
- Simulation positions separate from live
- Mode change audit trail
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '013_add_simulation_tables'
down_revision: Union[str, None] = '012_add_settings_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add execution_mode column to system_settings
    op.add_column(
        'system_settings',
        sa.Column('execution_mode', sa.String(20), nullable=False, server_default='simulation')
    )
    
    # Create simulation_accounts table
    op.create_table(
        'simulation_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        
        # Account State
        sa.Column('balance', sa.Float(), nullable=False, server_default='10000.0'),
        sa.Column('equity', sa.Float(), nullable=False, server_default='10000.0'),
        sa.Column('margin_used', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('margin_available', sa.Float(), nullable=False, server_default='10000.0'),
        
        # Configuration
        sa.Column('initial_balance', sa.Float(), nullable=False, server_default='10000.0'),
        sa.Column('currency', sa.String(3), nullable=False, server_default='USD'),
        
        # Simulation Parameters
        sa.Column('slippage_pips', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('commission_per_lot', sa.Float(), nullable=False, server_default='7.0'),
        sa.Column('latency_ms', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('fill_probability', sa.Float(), nullable=False, server_default='0.98'),
        
        # Trading Statistics
        sa.Column('total_trades', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('winning_trades', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_pnl', sa.Float(), nullable=False, server_default='0.0'),
        
        # Metadata
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('last_reset_at', sa.DateTime(), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', name='uq_simulation_accounts_user_id')
    )
    
    # Create index on user_id
    op.create_index('ix_simulation_accounts_user_id', 'simulation_accounts', ['user_id'])
    
    # Create execution_mode_audit table
    op.create_table(
        'execution_mode_audit',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        
        # Mode Change
        sa.Column('old_mode', sa.String(20), nullable=True),
        sa.Column('new_mode', sa.String(20), nullable=False),
        
        # Context
        sa.Column('reason', sa.String(500), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        
        # Safety Checks
        sa.Column('confirmation_required', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('password_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('had_open_positions', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('positions_cancelled', sa.Integer(), nullable=False, server_default='0'),
        
        # Timestamp
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    
    # Create indexes for audit table
    op.create_index('ix_execution_mode_audit_user_id', 'execution_mode_audit', ['user_id'])
    op.create_index('ix_execution_mode_audit_created_at', 'execution_mode_audit', ['created_at'])
    
    # Create simulation_positions table
    op.create_table(
        'simulation_positions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('simulation_account_id', sa.Integer(), nullable=False),
        
        # Position Details
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('side', sa.String(10), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('entry_price', sa.Float(), nullable=False),
        sa.Column('current_price', sa.Float(), nullable=False),
        
        # Risk Management
        sa.Column('stop_loss', sa.Float(), nullable=True),
        sa.Column('take_profit', sa.Float(), nullable=True),
        
        # P&L
        sa.Column('unrealized_pnl', sa.Float(), nullable=False, server_default='0.0'),
        
        # Margin
        sa.Column('margin_required', sa.Float(), nullable=False, server_default='0.0'),
        
        # Metadata
        sa.Column('order_id', sa.String(50), nullable=False),
        sa.Column('opened_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['simulation_account_id'], ['simulation_accounts.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('order_id', name='uq_simulation_positions_order_id')
    )
    
    # Create indexes for simulation_positions
    op.create_index('ix_simulation_positions_user_id', 'simulation_positions', ['user_id'])
    op.create_index('ix_simulation_positions_account_id', 'simulation_positions', ['simulation_account_id'])
    op.create_index('ix_simulation_positions_symbol', 'simulation_positions', ['symbol'])


def downgrade() -> None:
    # Drop simulation_positions table
    op.drop_index('ix_simulation_positions_symbol', 'simulation_positions')
    op.drop_index('ix_simulation_positions_account_id', 'simulation_positions')
    op.drop_index('ix_simulation_positions_user_id', 'simulation_positions')
    op.drop_table('simulation_positions')
    
    # Drop execution_mode_audit table
    op.drop_index('ix_execution_mode_audit_created_at', 'execution_mode_audit')
    op.drop_index('ix_execution_mode_audit_user_id', 'execution_mode_audit')
    op.drop_table('execution_mode_audit')
    
    # Drop simulation_accounts table
    op.drop_index('ix_simulation_accounts_user_id', 'simulation_accounts')
    op.drop_table('simulation_accounts')
    
    # Remove execution_mode column from system_settings
    op.drop_column('system_settings', 'execution_mode')
