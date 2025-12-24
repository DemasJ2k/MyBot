"""add_coordination_tables

Revision ID: 007
Revises: 006
Create Date: 2025-01-20
"""
from alembic import op
import sqlalchemy as sa

revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    # Create agent_messages table
    op.create_table(
        'agent_messages',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('from_agent', sa.String(50), nullable=False, index=True),
        sa.Column('to_agent', sa.String(50), nullable=False, index=True),
        sa.Column('message_type', sa.Enum('COMMAND', 'REQUEST', 'RESPONSE', 'EVENT', 'HALT', name='messagetype'), nullable=False),
        sa.Column('priority', sa.Enum('CRITICAL', 'HIGH', 'NORMAL', 'LOW', name='messagepriority'), nullable=False, default='NORMAL'),
        sa.Column('subject', sa.String(200), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('processed', sa.Boolean(), nullable=False, default=False, index=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('response_message_id', sa.Integer(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=False, index=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    op.create_index('ix_agent_message_to_processed', 'agent_messages', ['to_agent', 'processed'])

    # Create coordination_state table
    op.create_table(
        'coordination_state',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('cycle_id', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('phase', sa.Enum('IDLE', 'INITIALIZING', 'STRATEGY_ANALYSIS', 'RISK_VALIDATION', 'EXECUTION', 'MONITORING', 'HALTED', 'FAILED', 'COMPLETED', name='coordinationphase'), nullable=False, index=True),
        sa.Column('active_agents', sa.JSON(), nullable=False),
        sa.Column('shared_data', sa.JSON(), nullable=False, default=dict),
        sa.Column('halt_requested', sa.Boolean(), nullable=False, default=False),
        sa.Column('halt_reason', sa.Text(), nullable=True),
        sa.Column('cycle_started_at', sa.DateTime(), nullable=False),
        sa.Column('cycle_completed_at', sa.DateTime(), nullable=True),
        sa.Column('cycle_result', sa.JSON(), nullable=True),
        sa.Column('errors', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )

    # Create agent_health table
    op.create_table(
        'agent_health',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('agent_name', sa.String(50), nullable=False, index=True),
        sa.Column('is_healthy', sa.Boolean(), nullable=False, default=True),
        sa.Column('last_heartbeat', sa.DateTime(), nullable=False, index=True),
        sa.Column('avg_response_time_ms', sa.Float(), nullable=False, default=0.0),
        sa.Column('error_count', sa.Integer(), nullable=False, default=0),
        sa.Column('success_count', sa.Integer(), nullable=False, default=0),
        sa.Column('status_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )


def downgrade():
    op.drop_table('agent_health')
    op.drop_table('coordination_state')
    op.drop_table('agent_messages')
