"""Add journal and feedback tables

Revision ID: 010
Revises: 009
Create Date: 2024-12-25
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create journal_entries table
    op.create_table(
        'journal_entries',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('entry_id', sa.String(100), nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('strategy_name', sa.String(50), nullable=False),
        sa.Column('strategy_config', sa.JSON(), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('timeframe', sa.String(10), nullable=False),
        sa.Column('side', sa.String(10), nullable=False),
        sa.Column('entry_price', sa.Float(), nullable=False),
        sa.Column('exit_price', sa.Float(), nullable=False),
        sa.Column('position_size', sa.Float(), nullable=False),
        sa.Column('stop_loss', sa.Float(), nullable=False),
        sa.Column('take_profit', sa.Float(), nullable=False),
        sa.Column('risk_percent', sa.Float(), nullable=False),
        sa.Column('risk_reward_ratio', sa.Float(), nullable=False),
        sa.Column('pnl', sa.Float(), nullable=False),
        sa.Column('pnl_percent', sa.Float(), nullable=False),
        sa.Column('is_winner', sa.Boolean(), nullable=False),
        sa.Column('exit_reason', sa.String(50), nullable=False),
        sa.Column('entry_slippage', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('exit_slippage', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('commission', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('market_context', sa.JSON(), nullable=False),
        sa.Column('entry_time', sa.DateTime(), nullable=False),
        sa.Column('exit_time', sa.DateTime(), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=False),
        sa.Column('backtest_id', sa.String(36), nullable=True),
        sa.Column('execution_order_id', sa.Integer(), nullable=True),
        sa.Column('signal_id', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for journal_entries
    op.create_index('ix_journal_entries_entry_id', 'journal_entries', ['entry_id'], unique=True)
    op.create_index('ix_journal_entries_source', 'journal_entries', ['source'])
    op.create_index('ix_journal_entries_strategy_name', 'journal_entries', ['strategy_name'])
    op.create_index('ix_journal_entries_symbol', 'journal_entries', ['symbol'])
    op.create_index('ix_journal_entries_is_winner', 'journal_entries', ['is_winner'])
    op.create_index('ix_journal_entries_entry_time', 'journal_entries', ['entry_time'])
    op.create_index('ix_journal_strategy_source', 'journal_entries', ['strategy_name', 'source'])
    op.create_index('ix_journal_symbol_time', 'journal_entries', ['symbol', 'entry_time'])

    # Create feedback_decisions table
    op.create_table(
        'feedback_decisions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('decision_type', sa.String(50), nullable=False),
        sa.Column('strategy_name', sa.String(50), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('analysis', sa.JSON(), nullable=False),
        sa.Column('action_taken', sa.Text(), nullable=False),
        sa.Column('action_params', sa.JSON(), nullable=True),
        sa.Column('executed', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('execution_result', sa.Text(), nullable=True),
        sa.Column('decision_time', sa.DateTime(), nullable=False),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for feedback_decisions
    op.create_index('ix_feedback_decisions_decision_type', 'feedback_decisions', ['decision_type'])
    op.create_index('ix_feedback_decisions_strategy_name', 'feedback_decisions', ['strategy_name'])
    op.create_index('ix_feedback_decisions_decision_time', 'feedback_decisions', ['decision_time'])
    op.create_index('ix_feedback_strategy_type', 'feedback_decisions', ['strategy_name', 'decision_type'])

    # Create performance_snapshots table
    op.create_table(
        'performance_snapshots',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('strategy_name', sa.String(50), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('total_trades', sa.Integer(), nullable=False),
        sa.Column('winning_trades', sa.Integer(), nullable=False),
        sa.Column('losing_trades', sa.Integer(), nullable=False),
        sa.Column('win_rate_percent', sa.Float(), nullable=False),
        sa.Column('total_pnl', sa.Float(), nullable=False),
        sa.Column('avg_win', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('avg_loss', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('profit_factor', sa.Float(), nullable=True),
        sa.Column('max_consecutive_wins', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_consecutive_losses', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('avg_duration_minutes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('snapshot_time', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for performance_snapshots
    op.create_index('ix_performance_snapshots_strategy_name', 'performance_snapshots', ['strategy_name'])
    op.create_index('ix_performance_snapshots_symbol', 'performance_snapshots', ['symbol'])
    op.create_index('ix_performance_snapshots_snapshot_time', 'performance_snapshots', ['snapshot_time'])
    op.create_index('ix_performance_strategy_source_time', 'performance_snapshots', ['strategy_name', 'source', 'snapshot_time'])


def downgrade() -> None:
    # Drop indexes for performance_snapshots
    op.drop_index('ix_performance_strategy_source_time', table_name='performance_snapshots')
    op.drop_index('ix_performance_snapshots_snapshot_time', table_name='performance_snapshots')
    op.drop_index('ix_performance_snapshots_symbol', table_name='performance_snapshots')
    op.drop_index('ix_performance_snapshots_strategy_name', table_name='performance_snapshots')
    op.drop_table('performance_snapshots')

    # Drop indexes for feedback_decisions
    op.drop_index('ix_feedback_strategy_type', table_name='feedback_decisions')
    op.drop_index('ix_feedback_decisions_decision_time', table_name='feedback_decisions')
    op.drop_index('ix_feedback_decisions_strategy_name', table_name='feedback_decisions')
    op.drop_index('ix_feedback_decisions_decision_type', table_name='feedback_decisions')
    op.drop_table('feedback_decisions')

    # Drop indexes for journal_entries
    op.drop_index('ix_journal_symbol_time', table_name='journal_entries')
    op.drop_index('ix_journal_strategy_source', table_name='journal_entries')
    op.drop_index('ix_journal_entries_entry_time', table_name='journal_entries')
    op.drop_index('ix_journal_entries_is_winner', table_name='journal_entries')
    op.drop_index('ix_journal_entries_symbol', table_name='journal_entries')
    op.drop_index('ix_journal_entries_strategy_name', table_name='journal_entries')
    op.drop_index('ix_journal_entries_source', table_name='journal_entries')
    op.drop_index('ix_journal_entries_entry_id', table_name='journal_entries')
    op.drop_table('journal_entries')
