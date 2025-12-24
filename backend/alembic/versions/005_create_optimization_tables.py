"""create optimization tables

Revision ID: 005
Revises: 004
Create Date: 2025-01-01 14:00:00.000000

Prompt 06 - Optimization Engine
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create optimization tables."""
    
    # Create optimization_jobs table
    op.create_table(
        'optimization_jobs',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('strategy_name', sa.String(50), nullable=False, index=True),
        sa.Column('symbol', sa.String(20), nullable=False, index=True),
        sa.Column('interval', sa.String(10), nullable=False),
        
        # Optimization parameters
        sa.Column('method', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, index=True),
        
        # Parameter space (JSON)
        sa.Column('parameter_ranges', JSON, nullable=False),
        
        # Backtest configuration
        sa.Column('start_date', sa.DateTime, nullable=False),
        sa.Column('end_date', sa.DateTime, nullable=False),
        sa.Column('initial_balance', sa.Float, nullable=False, default=10000.0),
        sa.Column('commission_percent', sa.Float, nullable=False, default=0.1),
        sa.Column('slippage_percent', sa.Float, nullable=False, default=0.05),
        
        # Optimization settings
        sa.Column('max_iterations', sa.Integer, nullable=False, default=100),
        sa.Column('objective_metric', sa.String(50), nullable=False, default='sharpe_ratio'),
        sa.Column('minimize', sa.Boolean, nullable=False, default=False),
        
        # Progress tracking
        sa.Column('total_combinations', sa.Integer, nullable=True),
        sa.Column('completed_iterations', sa.Integer, nullable=False, default=0),
        sa.Column('progress_percent', sa.Float, nullable=False, default=0.0),
        
        # Results
        sa.Column('best_config', JSON, nullable=True),
        sa.Column('best_score', sa.Float, nullable=True),
        sa.Column('best_backtest_id', sa.String(36), nullable=True),
        
        # Execution metadata
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Create composite index for strategy + status
    op.create_index(
        'ix_optimization_strategy_status',
        'optimization_jobs',
        ['strategy_name', 'status']
    )
    
    # Create optimization_results table
    op.create_table(
        'optimization_results',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('job_id', sa.Integer, sa.ForeignKey('optimization_jobs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('iteration', sa.Integer, nullable=False),
        
        # Configuration tested
        sa.Column('config', JSON, nullable=False),
        
        # Performance metrics
        sa.Column('score', sa.Float, nullable=False),
        sa.Column('total_return_percent', sa.Float, nullable=False),
        sa.Column('sharpe_ratio', sa.Float, nullable=True),
        sa.Column('max_drawdown_percent', sa.Float, nullable=False),
        sa.Column('win_rate_percent', sa.Float, nullable=False),
        sa.Column('profit_factor', sa.Float, nullable=True),
        sa.Column('total_trades', sa.Integer, nullable=False),
        
        # Reference to backtest
        sa.Column('backtest_id', sa.String(36), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Create composite index for job_id + score
    op.create_index(
        'ix_optimization_result_job_score',
        'optimization_results',
        ['job_id', 'score']
    )
    
    # Create playbooks table
    op.create_table(
        'playbooks',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('strategy_name', sa.String(50), nullable=False, index=True),
        sa.Column('symbol', sa.String(20), nullable=False, index=True),
        
        # Strategy configuration (JSON)
        sa.Column('config', JSON, nullable=False),
        
        # Performance metrics from optimization
        sa.Column('expected_return_percent', sa.Float, nullable=True),
        sa.Column('expected_sharpe_ratio', sa.Float, nullable=True),
        sa.Column('expected_max_drawdown_percent', sa.Float, nullable=True),
        
        # Metadata
        sa.Column('optimization_job_id', sa.Integer, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, default=True),
        sa.Column('notes', sa.Text, nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Create composite index for strategy + active
    op.create_index(
        'ix_playbook_strategy_active',
        'playbooks',
        ['strategy_name', 'is_active']
    )


def downgrade() -> None:
    """Drop optimization tables."""
    op.drop_index('ix_playbook_strategy_active', table_name='playbooks')
    op.drop_table('playbooks')
    
    op.drop_index('ix_optimization_result_job_score', table_name='optimization_results')
    op.drop_table('optimization_results')
    
    op.drop_index('ix_optimization_strategy_status', table_name='optimization_jobs')
    op.drop_table('optimization_jobs')
