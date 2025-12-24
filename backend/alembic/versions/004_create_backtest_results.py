"""create backtest results table

Revision ID: 004
Revises: 003
Create Date: 2025-01-01 12:00:00.000000

Prompt 05 - Backtest Engine
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create backtest_results table."""
    op.create_table(
        'backtest_results',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        
        # Backtest configuration
        sa.Column('strategy_name', sa.String(100), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False, index=True),
        sa.Column('timeframe', sa.String(10), nullable=False),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=False),
        
        # Initial conditions
        sa.Column('initial_capital', sa.Float, nullable=False),
        
        # Performance metrics
        sa.Column('total_return', sa.Float, nullable=False),
        sa.Column('sharpe_ratio', sa.Float, nullable=True),
        sa.Column('sortino_ratio', sa.Float, nullable=True),
        sa.Column('max_drawdown', sa.Float, nullable=False),
        sa.Column('win_rate', sa.Float, nullable=False),
        sa.Column('profit_factor', sa.Float, nullable=True),
        
        # Trade statistics
        sa.Column('total_trades', sa.Integer, nullable=False),
        sa.Column('winning_trades', sa.Integer, nullable=False),
        sa.Column('losing_trades', sa.Integer, nullable=False),
        
        # JSON columns for detailed data
        sa.Column('equity_curve', JSON, nullable=False, server_default='[]'),
        sa.Column('trade_log', JSON, nullable=False, server_default='[]'),
        
        # Strategy parameters used
        sa.Column('strategy_params', JSON, nullable=True),
        
        # Optional notes
        sa.Column('notes', sa.Text, nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # Create indexes for common queries
    op.create_index(
        'ix_backtest_results_user_strategy',
        'backtest_results',
        ['user_id', 'strategy_name']
    )
    op.create_index(
        'ix_backtest_results_created_at',
        'backtest_results',
        ['created_at']
    )


def downgrade() -> None:
    """Drop backtest_results table."""
    op.drop_index('ix_backtest_results_created_at', table_name='backtest_results')
    op.drop_index('ix_backtest_results_user_strategy', table_name='backtest_results')
    op.drop_table('backtest_results')
