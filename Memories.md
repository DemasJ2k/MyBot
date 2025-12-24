# Memories

## Project Context
- Flowrex is a safety-first trading platform built following a 19-prompt sequence
- User specified: generate directly under `c:\Users\demas\myBot`, strictly follow prompt order
- React 19 has peer dependency conflicts - use `--legacy-peer-deps` in npm installs

## Technical Decisions
- PostgreSQL 16 + Redis 7 as core infrastructure
- SQLAlchemy 2.0 async with modern Mapped types
- JWT with 30min access / 7 day refresh tokens
- TwelveData free tier = 8 requests/minute rate limit
- All 4 strategies use same base config pattern with get_default_config()
- Backtest engine uses position sizing as % of equity (default 2%)
- Optimization uses background tasks for long-running jobs
- AI agents follow strict hierarchy: Supervisor → Strategy → Risk → Execution
- Coordination uses message-based communication with priority ordering
- Supervisor is the ONLY agent that can transition phases

## Implementation Notes
- Prompt 01: Project scaffold with Docker Compose, Next.js frontend, FastAPI backend
- Prompt 02: Auth system with register/login/refresh/me/logout endpoints, 7 tests pass
- Prompt 03: Data engine with TwelveData client, candle/symbol/event models, API routes
- Prompt 04: Strategy engine with NBB, JadeCap, Fabio, Tori strategies, 18 tests pass
- Prompt 05: Backtest engine with Portfolio simulator, PerformanceMetrics, 29 tests pass
- Prompt 06: Optimization engine with Grid/Random/AI optimizers, Playbooks, 32 tests pass
- Prompt 07: AI Agent system with Supervisor/Strategy/Risk/Execution agents, 22 tests pass
- Prompt 08: Multi-Agent Coordination with MessageBus, SharedState, Pipeline, 21 tests pass
- Prompt 09: Risk Engine with immutable hard limits, 9-check validation pipeline, 19 tests pass

## Technical Decisions (continued)
- Risk Engine operates independently of AI agents (absolute veto power)
- Hard risk limits are Python constants, not database-configurable
- Risk checks execute in severity order (emergency shutdown first)
- Strategy auto-disables after 5 consecutive losses (safety mechanism)
- Risk decisions logged with full audit trail for compliance

## Gotchas Encountered
- Alembic logger config needs `qualname` field in alembic.ini
- Use `pydantic[email]` not separate email-validator package
- pytest-asyncio fixtures must use `@pytest_asyncio.fixture` decorator
- Symbol model uses `type` column, not `asset_type`
- Floating point comparisons need tolerance (use pytest.approx)
- SQLAlchemy relationships with TYPE_CHECKING to avoid circular imports
- UUID columns: Use String(36) for cross-database compatibility (SQLite test vs PostgreSQL prod)
- PostgreSQL.UUID doesn't work with SQLite - use generic types for test compatibility
- User model uses Integer id, not UUID - ensure ForeignKey matches parent type
- SQLEnum needs `native_enum=False` for cross-database compatibility
- BacktestEngine.run() is synchronous, not async - adapt optimization engine accordingly
- ParameterSpace range generation needs epsilon for floating point edge cases
- bcrypt 5.0.0 incompatible with passlib 1.7.4 - use bcrypt==4.0.1
- SQLite doesn't support ALTER COLUMN - write explicit CREATE TABLE migrations
- Alembic autogenerate creates PostgreSQL-specific migrations - review before running
- conftest.py fixture is `test_db`, not `async_db_session`
- BacktestResult uses `max_drawdown` and `win_rate`, not `max_drawdown_percent` or `win_rate_percent`
- When creating SQLAlchemy model instances in code, must provide ALL required fields (default values from migration don't apply)
- StrategyRiskBudget needs all numeric fields initialized (total_trades=0, winning_trades=0, etc.)
