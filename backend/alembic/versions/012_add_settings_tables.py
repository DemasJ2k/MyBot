"""Add settings tables

Revision ID: 012
Revises: 011_add_user_id_multitenancy
Create Date: 2025-12-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '012_add_settings_tables'
down_revision: Union[str, None] = '011_add_user_id_multitenancy'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create system_settings table
    op.create_table(
        'system_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        # Mode Configuration
        sa.Column('mode', sa.Enum('guide', 'autonomous', name='systemmode'), nullable=False, server_default='guide'),
        # Broker Configuration
        sa.Column('broker_type', sa.Enum('mt5', 'oanda', 'binance', 'paper', name='brokertype'), nullable=False, server_default='paper'),
        sa.Column('broker_connected', sa.Boolean(), nullable=False, server_default='false'),
        # Data Provider Configuration
        sa.Column('data_provider', sa.String(50), nullable=False, server_default='twelvedata'),
        # Risk Configuration (Soft Limits)
        sa.Column('max_risk_per_trade_percent', sa.Float(), nullable=False, server_default='2.0'),
        sa.Column('max_daily_loss_percent', sa.Float(), nullable=False, server_default='5.0'),
        sa.Column('emergency_drawdown_percent', sa.Float(), nullable=False, server_default='15.0'),
        sa.Column('max_open_positions', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('max_trades_per_day', sa.Integer(), nullable=False, server_default='20'),
        # Strategy Management
        sa.Column('auto_disable_strategies', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('strategy_disable_threshold', sa.Integer(), nullable=False, server_default='5'),
        # Mode Transition Behavior
        sa.Column('cancel_orders_on_mode_switch', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('require_confirmation_for_autonomous', sa.Boolean(), nullable=False, server_default='true'),
        # System Health Monitoring
        sa.Column('health_check_interval_seconds', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('agent_timeout_seconds', sa.Integer(), nullable=False, server_default='60'),
        # Notification Settings
        sa.Column('email_notifications_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('notification_email', sa.String(255), nullable=True),
        # Advanced Settings
        sa.Column('advanced_settings', sa.JSON(), nullable=False, server_default='{}'),
        # Audit Fields
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create settings_audit table
    op.create_table(
        'settings_audit',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('settings_version', sa.Integer(), nullable=False),
        sa.Column('changed_by', sa.Integer(), nullable=True),
        sa.Column('changed_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('change_type', sa.String(50), nullable=False),
        sa.Column('old_value', sa.JSON(), nullable=False),
        sa.Column('new_value', sa.JSON(), nullable=False),
        sa.Column('reason', sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index on settings_audit for faster queries
    op.create_index('ix_settings_audit_changed_at', 'settings_audit', ['changed_at'], unique=False)
    op.create_index('ix_settings_audit_change_type', 'settings_audit', ['change_type'], unique=False)

    # Create user_preferences table
    op.create_table(
        'user_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        # UI Preferences
        sa.Column('theme', sa.String(20), nullable=False, server_default='system'),
        sa.Column('sidebar_collapsed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('default_chart_timeframe', sa.String(10), nullable=False, server_default='1h'),
        # Notification Preferences
        sa.Column('email_on_trade_execution', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('email_on_signal_generated', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('email_on_risk_alert', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('email_on_emergency_shutdown', sa.Boolean(), nullable=False, server_default='true'),
        # Dashboard Preferences
        sa.Column('dashboard_widgets', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('favorite_symbols', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('favorite_strategies', sa.JSON(), nullable=False, server_default='[]'),
        # Display Settings
        sa.Column('decimal_places', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('date_format', sa.String(20), nullable=False, server_default='YYYY-MM-DD'),
        sa.Column('timezone', sa.String(50), nullable=False, server_default='UTC'),
        # Audit Fields
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id')
    )
    
    # Create index on user_preferences.user_id
    op.create_index('ix_user_preferences_user_id', 'user_preferences', ['user_id'], unique=True)

    # Insert default system settings row
    op.execute("""
        INSERT INTO system_settings (id, mode, broker_type, broker_connected, data_provider, 
            max_risk_per_trade_percent, max_daily_loss_percent, emergency_drawdown_percent,
            max_open_positions, max_trades_per_day, auto_disable_strategies, strategy_disable_threshold,
            cancel_orders_on_mode_switch, require_confirmation_for_autonomous, health_check_interval_seconds,
            agent_timeout_seconds, email_notifications_enabled, advanced_settings, version)
        VALUES (1, 'guide', 'paper', false, 'twelvedata', 
            2.0, 5.0, 15.0, 10, 20, true, 5, true, true, 30, 60, false, '{}', 1)
    """)


def downgrade() -> None:
    op.drop_index('ix_user_preferences_user_id', table_name='user_preferences')
    op.drop_table('user_preferences')
    op.drop_index('ix_settings_audit_change_type', table_name='settings_audit')
    op.drop_index('ix_settings_audit_changed_at', table_name='settings_audit')
    op.drop_table('settings_audit')
    op.drop_table('system_settings')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS systemmode')
    op.execute('DROP TYPE IF EXISTS brokertype')
