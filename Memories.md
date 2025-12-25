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

## Frontend-Specific Gotchas
- Next.js 15+ has breaking changes with jest - stick to Next.js 14.2.x for stability
- React 19 has peer dependency conflicts with testing-library - use React 18.3.x
- jest.setup.js must be plain JavaScript, not TypeScript (SWC parser fails on TS syntax)
- Next.js builds create .next/standalone/package.json that causes Haste module collision in Jest
  - Fix: Add `modulePathIgnorePatterns: ['<rootDir>/.next/']` to jest.config.js
- Date assertions in tests can fail due to timezone differences - use regex patterns
- ErrorBoundary tests should not try to verify state reset after rerender (not possible with class components)
- API client tests need careful mocking - module caching affects axios.create mock timing
- TailwindCSS v3 uses `@tailwind` directives, not `@import "tailwindcss/..."`
- React Query stale time of 60000ms (1 min) balances freshness with API rate limits
- ModeProvider defaults to 'guide' on error (safety-first principle)

## Rate Limiting & Auth Gotchas
- SlowAPI `@limiter.limit()` decorator REQUIRES `request: Request` as first parameter
- Without request parameter, FastAPI fails to import the module entirely
- Token blacklist uses Redis - tests need to mock `redis_client` or will fail silently with 401
- Test fixture should patch `app.auth.blacklist.redis_client` with AsyncMock

## Test Isolation Gotchas
- conftest.py `client` fixture shares same app instance - state can leak
- Rate limiter storage persists across tests - reset with `limiter.reset()` in fixture
- Redis blacklist persists across tests - mock to avoid connection errors

## Test Counts by Prompt
- Prompt 02 (Auth): 7 tests
- Prompt 03 (Data): 12 tests
- Prompt 04 (Strategy): 18 tests
- Prompt 05 (Backtest): 29 tests
- Prompt 06 (Optimization): 32 tests
- Prompt 07 (AI Agents): 22 tests
- Prompt 08 (Coordination): 21 tests
- Prompt 09 (Risk): 19 tests
- Prompt 10 (Execution): 28 tests
- Prompt 11 (Journal): 22 tests
- **Backend Total: 210 tests** ✅ All passing (verified 2025-12-25)
- Prompt 12 (Frontend): 41 tests
- **Frontend Total: 41 tests** ✅ All passing
- **Combined Total: 251 tests**

## Security Implementation Notes
- CSRF uses double-submit cookie pattern (cookie value must match X-CSRF-Token header)
- Token blacklist stored in Redis with TTL = token expiry time
- JTI (JWT ID) added to tokens for blacklist tracking
- Rate limiting via SlowAPI with Redis storage
- CORS origins configurable via `CORS_ALLOWED_ORIGINS` env var (comma-separated)

## Multi-Tenancy Notes
- Signal, Position, ExecutionOrder models now have `user_id` FK
- All queries for these entities should filter by current user
- Migration 011 adds user_id columns (nullable initially for existing data)

## E2E Testing Notes
- E2E tests require `--e2e` flag to run
- Tests skip by default to avoid failures in CI without services
- Use `pytest tests/e2e/ -v --e2e` to run E2E suite
- E2E tests need running backend (localhost:8000) and services (Postgres, Redis)
