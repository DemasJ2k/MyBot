"""add_ai_agent_tables

Revision ID: 006
Revises: 005
Create Date: 2025-01-20
"""
from alembic import op
import sqlalchemy as sa

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    # Create ai_decisions table
    op.create_table(
        'ai_decisions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('session_id', sa.String(100), nullable=False, index=True),
        sa.Column('agent_role', sa.Enum('SUPERVISOR', 'STRATEGY', 'RISK', 'EXECUTION', name='agentrole'), nullable=False),
        sa.Column('decision_type', sa.Enum('SIGNAL', 'POSITION_SIZE', 'RISK_APPROVAL', 'EXECUTION', 'HALT', 'MODE_SWITCH', name='decisiontype'), nullable=False),
        sa.Column('input_data', sa.JSON(), nullable=False),
        sa.Column('reasoning', sa.Text(), nullable=False),
        sa.Column('output_data', sa.JSON(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('user_approved', sa.Boolean(), nullable=True),
        sa.Column('executed', sa.Boolean(), nullable=False, default=False),
        sa.Column('execution_result', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    op.create_index('ix_ai_decisions_created_at', 'ai_decisions', ['created_at'])
    op.create_index('ix_ai_decisions_agent_role', 'ai_decisions', ['agent_role'])

    # Create agent_memory table
    op.create_table(
        'agent_memory',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('agent_role', sa.Enum('SUPERVISOR', 'STRATEGY', 'RISK', 'EXECUTION', name='agentrole'), nullable=False),
        sa.Column('memory_type', sa.String(50), nullable=False),
        sa.Column('key', sa.String(200), nullable=False),
        sa.Column('value', sa.JSON(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    op.create_index('ix_agent_memory_agent_role', 'agent_memory', ['agent_role'])
    op.create_index('ix_agent_memory_key', 'agent_memory', ['key'])

    # Create system_config table
    op.create_table(
        'system_config',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('key', sa.String(100), nullable=False, unique=True),
        sa.Column('value', sa.JSON(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    op.create_index('ix_system_config_key', 'system_config', ['key'])


def downgrade():
    op.drop_table('system_config')
    op.drop_table('agent_memory')
    op.drop_table('ai_decisions')
