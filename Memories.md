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
- Prompt 14 (Settings): 33 tests
- Prompt 15 (CROSSCHECK): 12 tests
- Prompt 16 (Simulation): 38 tests
- **Backend Total: 297 tests** ✅ All passing
- Prompt 12 (Frontend): 41 tests
- **Frontend Total: 41 tests** ✅ All passing
- **Combined Total: 338 tests**

## Prompt 17 Deployment Prep Notes
- Creating `config/` directory conflicted with `config.py` - keep single file
- Observability uses optional deps (prometheus_client, pythonjsonlogger) with fallbacks
- Metrics endpoint at `/metrics` excluded from metrics collection to avoid recursion
- Security middleware adds request ID for distributed tracing
- Migration scripts use asyncio for database connection check
- Deployment checklist designed for CI/CD integration
- Alerts.yaml follows Prometheus alerting rules format

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

## Prompt 14 (Settings & Modes) Implementation Notes
- SystemSettings is a singleton pattern - only one row exists in database
- Hard-coded constants in risk/constants.py are IMMUTABLE - soft settings cannot exceed these
- Mode switching from GUIDE → AUTONOMOUS requires broker connection (except for PAPER broker)
- SettingsAudit creates immutable audit trail - every change recorded with reason
- SQLAlchemy `mapped_column(default=...)` only applies during DB insert, not Python instantiation
  - Tests that create model instances must explicitly provide all required field values
  - Use helper methods like `_create_settings()` to provide defaults in tests
- UserPreferences stores favorite_strategies and favorite_symbols as JSON arrays
- Settings API returns `can_switch` boolean to indicate if mode switch is currently allowed

## Prompt 15 (Testing & Validation) Implementation Notes
- Test Pyramid: 70% unit, 20% integration, 10% E2E
- pytest.ini configures markers: unit, integration, e2e, slow, crosscheck
- .coveragerc sets 80% minimum coverage threshold
- CROSSCHECK tests validate architectural rules:
  - Hard risk constants exist and have safe values
  - Execution engine is sole trade executor
  - Journal entries are immutable (no update/delete methods)
  - Mode enforcement is in place
  - Audit trail models exist
- NullPool breaks in-memory SQLite (each connection is separate DB)
  - Use simple `create_async_engine("sqlite+aiosqlite:///:memory:")` without NullPool
- GitHub Actions workflow gates merges on test success
- Security scanning with `safety` (Python) and `npm audit` (frontend)

## Prompt 16 (Simulation & Demo Mode) Implementation Notes
- Three execution modes: SIMULATION (default/safest), PAPER, LIVE
- SIMULATION mode uses SimulatedBrokerAdapter with database-backed SimulationAccount
- LIVE mode requires: password verification + explicit confirmation + reason (all three)
- ExecutionModeService handles mode transitions with full safety validation
- Mode changes create ExecutionModeAudit records with IP, user agent, context
- SimulationAccount tracks: balance, equity, margin, P&L, win rate, slippage settings
- SimulationPosition tracks virtual positions separately from live
- Frontend components provide visual mode indication and confirmation dialogs
- Migration 013 adds: simulation_accounts, execution_mode_audit, simulation_positions tables
- File reading in crosscheck tests needs `encoding="utf-8"` for Unicode compatibility

## Audit Fixes Session (December 25, 2025) Notes
- **H1 Fix:** Live mode password verification was placeholder (`password_verified = True`)
  - Fixed by using `verify_password(request.password, current_user.hashed_password)`
  - Added 4 unit tests in `TestPasswordVerificationForLiveMode`
- **H2 Fix:** E2E tests were failing due to multiple issues:
  - E2E conftest was making real HTTP calls to localhost:8000
  - Fixed by adding ASGI transport fallback for standalone testing
  - Login was using form-data but API expects JSON (`email`, not `username`)
  - `test_risk_state_retrieval` needed to accept empty state response
  - `test_backtest_execution` used wrong strategy name (`sma_crossover` → `nbb`)
  - `Candle.timeframe` bug - actual field is `Candle.interval`
  - `StrategyManager.get_available_strategies()` was missing - added as class method
- **Test counts after fixes:** Backend: 297, E2E: 13 passed + 1 skipped, Frontend: 41

## Prompt 18 Production Deployment Notes
- Docker multi-stage builds reduce image size and attack surface
- Non-root users (flowrex) in containers for security
- dumb-init in frontend container for proper signal handling
- Rolling updates: scale up → health check → scale down (zero downtime)
- Health endpoints hierarchy: /health (basic) → /health/ready (deps) → /health/live (liveness)
- NGINX rate limiting zones: api (100r/s), auth (20r/m), ws (20r/s)
- Prometheus scrape interval: 15s for metrics freshness
- Grafana datasources auto-provisioned via YAML files
- Deployment script uses Slack webhooks for notifications
- Rollback script can optionally restore database from backup
- Incident severity levels: P0 (immediate), P1 (15min), P2 (1hr), P3 (next day)
- Post-mortem template includes timeline, root cause, impact, action items

## Production Infrastructure Decisions
- 5 backend replicas for high availability
- 3 frontend replicas for load distribution
- Resource limits prevent runaway containers (backend: 1CPU/1GB, frontend: 0.5CPU/512MB)
- Update parallelism: 2 at a time to maintain capacity during deploys
- Health check intervals: 30s with 60s start period for warm-up
- Postgres connection limit: 100 (shared mode)
- Redis maxmemory: 256mb with allkeys-lru eviction

## Prompt 18 Audit Fix Learnings (December 25, 2025)
- Settings class with pydantic-settings needs `extra="ignore"` when .env has extra variables
- psutil must be added to requirements.txt for system metrics in health endpoints
- Redis CLI password should use REDISCLI_AUTH env var, not `-a` flag (security)
- Alertmanager service required when Prometheus config references alerting
- Health endpoint tests should be flexible about DB connectivity in isolated test environments
- nginx-exporter requires NGINX stub_status module configuration (not trivial to add)
- SSL certificate check should be blocking for production deployments

## Updated Test Count Summary
- **Backend Total: 311 tests** (297 original + 14 health)
- **Frontend Total: 41 tests**
- **E2E: 13 passed, 1 skipped**
- **Combined Total: 365+ tests**