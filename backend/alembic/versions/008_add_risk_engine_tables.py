"""Add risk engine tables

Revision ID: 008
Revises: 007
Create Date: 2024-12-25
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create risk_decisions table
    op.create_table(
        'risk_decisions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('decision_type', sa.String(50), nullable=False),
        sa.Column('subject', sa.String(200), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=True),
        sa.Column('approved', sa.Boolean(), nullable=False),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('risk_metrics', sa.JSON(), nullable=False),
        sa.Column('limits_checked', sa.JSON(), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False, server_default='info'),
        sa.Column('decision_time', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_risk_decisions_decision_type', 'risk_decisions', ['decision_type'])
    op.create_index('ix_risk_decisions_approved', 'risk_decisions', ['approved'])
    op.create_index('ix_risk_decisions_decision_time', 'risk_decisions', ['decision_time'])

    # Create account_risk_state table
    op.create_table(
        'account_risk_state',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('account_balance', sa.Float(), nullable=False),
        sa.Column('peak_balance', sa.Float(), nullable=False),
        sa.Column('current_drawdown_percent', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('daily_pnl', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('daily_loss_percent', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('trades_today', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('trades_this_hour', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('open_positions_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_exposure', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('total_exposure_percent', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('emergency_shutdown_active', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('throttling_active', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('last_updated', sa.DateTime(), nullable=False),
        sa.Column('last_trade_time', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_account_risk_state_last_updated', 'account_risk_state', ['last_updated'])

    # Create strategy_risk_budgets table
    op.create_table(
        'strategy_risk_budgets',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('strategy_name', sa.String(50), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('max_exposure_percent', sa.Float(), nullable=False, server_default='5.0'),
        sa.Column('max_daily_loss_percent', sa.Float(), nullable=False, server_default='2.0'),
        sa.Column('current_exposure', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('current_exposure_percent', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('daily_pnl', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('total_trades', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('winning_trades', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('losing_trades', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_pnl', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('consecutive_losses', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_consecutive_losses', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('disabled_reason', sa.Text(), nullable=True),
        sa.Column('last_trade_time', sa.DateTime(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_strategy_risk_budgets_strategy_name', 'strategy_risk_budgets', ['strategy_name'])
    op.create_index('ix_strategy_risk_budgets_symbol', 'strategy_risk_budgets', ['symbol'])
    op.create_index('ix_strategy_risk_budget_strategy_symbol', 'strategy_risk_budgets', ['strategy_name', 'symbol'])


def downgrade() -> None:
    op.drop_index('ix_strategy_risk_budget_strategy_symbol', table_name='strategy_risk_budgets')
    op.drop_index('ix_strategy_risk_budgets_symbol', table_name='strategy_risk_budgets')
    op.drop_index('ix_strategy_risk_budgets_strategy_name', table_name='strategy_risk_budgets')
    op.drop_table('strategy_risk_budgets')
    
    op.drop_index('ix_account_risk_state_last_updated', table_name='account_risk_state')
    op.drop_table('account_risk_state')
    
    op.drop_index('ix_risk_decisions_decision_time', table_name='risk_decisions')
    op.drop_index('ix_risk_decisions_approved', table_name='risk_decisions')
    op.drop_index('ix_risk_decisions_decision_type', table_name='risk_decisions')
    op.drop_table('risk_decisions')
