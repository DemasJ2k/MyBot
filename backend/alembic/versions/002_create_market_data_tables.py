"""create market data tables

Revision ID: 002
Revises: 001
Create Date: 2025-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Candles table
    op.create_table(
        'candles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('interval', sa.String(length=10), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('open', sa.Float(), nullable=False),
        sa.Column('high', sa.Float(), nullable=False),
        sa.Column('low', sa.Float(), nullable=False),
        sa.Column('close', sa.Float(), nullable=False),
        sa.Column('volume', sa.BigInteger(), default=0),
        sa.Column('source', sa.String(length=50), default='twelvedata'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_candles_symbol_interval_timestamp', 'candles', ['symbol', 'interval', 'timestamp'], unique=True)
    op.create_index('ix_candles_symbol', 'candles', ['symbol'])
    op.create_index('ix_candles_timestamp', 'candles', ['timestamp'])

    # Symbols table
    op.create_table(
        'symbols',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=200)),
        sa.Column('exchange', sa.String(length=50)),
        sa.Column('currency', sa.String(length=10)),
        sa.Column('country', sa.String(length=50)),
        sa.Column('asset_type', sa.String(length=50)),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('symbol')
    )
    op.create_index('ix_symbols_symbol', 'symbols', ['symbol'])

    # Economic events table
    op.create_table(
        'economic_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('country', sa.String(length=10), nullable=False),
        sa.Column('event', sa.String(length=500), nullable=False),
        sa.Column('impact', sa.String(length=20)),
        sa.Column('actual', sa.String(length=50)),
        sa.Column('forecast', sa.String(length=50)),
        sa.Column('previous', sa.String(length=50)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_economic_events_date_country', 'economic_events', ['event_date', 'country'])


def downgrade() -> None:
    op.drop_index('ix_economic_events_date_country', table_name='economic_events')
    op.drop_table('economic_events')

    op.drop_index('ix_symbols_symbol', table_name='symbols')
    op.drop_table('symbols')

    op.drop_index('ix_candles_timestamp', table_name='candles')
    op.drop_index('ix_candles_symbol', table_name='candles')
    op.drop_index('ix_candles_symbol_interval_timestamp', table_name='candles')
    op.drop_table('candles')
