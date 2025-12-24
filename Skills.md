# Skills

## Backend Development
- FastAPI async API design with dependency injection
- SQLAlchemy 2.0 async ORM with mapped_column and Mapped types
- Alembic migrations for PostgreSQL and SQLite
- JWT authentication (access + refresh tokens)
- Pydantic v2 models with email validation
- Redis integration for caching and rate limiting
- aiohttp with retry logic for external API calls

## Testing
- pytest-asyncio for async test fixtures
- AsyncMock and MagicMock for unit testing
- In-memory SQLite for isolated auth tests
- Cross-database compatible models (PostgreSQL + SQLite)
- 141+ unit tests covering all components

## Infrastructure
- Docker Compose multi-service orchestration
- Health check patterns for containers
- Environment-based configuration with pydantic-settings

## Market Data
- TwelveData API integration (time_series, quote, search, economic_calendar)
- Token bucket rate limiting for API calls
- Redis caching with TTL for market data
- OHLCV candle parsing and storage

## Trading Strategies
- Abstract base strategy pattern with validation
- Signal generation with risk/reward ratio calculation
- Position sizing based on risk percentage
- NBB: Supply/demand zone detection, breakout/retest logic
- JadeCap: EMA calculation, trend detection, pullback patterns
- Fabio: Value Area calculation (POC, VAH, VAL), AMT signals
- Tori: Swing point detection, trendline projection, Fibonacci levels

## Backtesting
- Portfolio simulation with position management
- Long and Short position P&L calculation
- Stop-loss and take-profit trigger logic
- Equity curve tracking with drawdown calculation
- Performance metrics:
  - Sharpe ratio (annualized, 252 trading days)
  - Sortino ratio (downside deviation only)
  - Profit factor (gross profits / gross losses)
  - Win rate, expectancy, recovery factor
  - Average trade duration calculation
- BacktestEngine orchestrating strategy + portfolio + metrics
- JSON serialization for equity curves and trade logs

## Flowrex Project Knowledge
- 19-prompt sequence (00-18) for building safety-first trading platform
- GUIDE vs AUTONOMOUS mode enforcement patterns
- Adapter-based execution architecture

## Optimization
- Parameter space definition (discrete lists, continuous ranges with step)
- Grid search optimization (exhaustive combinatorial search)
- Random search optimization (Monte Carlo sampling)
- AI-driven optimization (exploration + exploitation via mutation)
- Background task execution for long-running optimizations
- Playbook generation from optimal configurations
- Multi-objective optimization metrics (Sharpe, return, drawdown, win rate)

## AI Agent System
- Multi-agent architecture (Supervisor → Strategy → Risk → Execution)
- Agent decision logging with reasoning
- Persistent agent memory with key-value storage
- System mode enforcement (GUIDE/AUTONOMOUS)
- Hard cap validation (max positions, daily trades, drawdown)
- Strategy evaluation based on backtest performance
- Risk validation with position sizing
- Mode-aware execution (simulate vs live)

## Multi-Agent Coordination
- Inter-agent message bus with priority-based delivery
- Message types: COMMAND, REQUEST, RESPONSE, EVENT, HALT
- Request-response correlation with message linking
- HALT broadcast mechanism for emergency stops
- Shared state management with cycle tracking
- Phase transitions (Supervisor-only authority)
- Agent-prefixed write access control (strategy_*, risk_*, execution_*)
- Agent health monitoring with heartbeats
- Error tracking and unhealthy detection (>50% error rate)
- Unresponsive agent detection (60s timeout)
- Deterministic coordination pipeline (Strategy → Risk → Execution)
- Halt capability at any phase in the pipeline

## Risk Engine
- Immutable hard risk constants (cannot be changed at runtime)
- 9-check validation pipeline in severity order:
  1. Emergency shutdown (highest priority)
  2. Account drawdown (15% triggers shutdown)
  3. Max positions (10 limit)
  4. Daily trade limit (20/day)
  5. Hourly trade limit (5/hour)
  6. Position size (1.0 lots max)
  7. Risk/reward ratio (1.5:1 min)
  8. Strategy budget (enabled status, consecutive losses)
  9. Daily loss limit (5% max)
- Risk decision audit trail with full metrics
- Account state tracking (balance, drawdown, P&L, positions)
- Strategy risk budget with auto-disable (5 consecutive losses)
- Emergency shutdown mechanism with manual reset
- Daily metrics reset for trading day boundaries
- Position size calculation based on risk parameters
- Risk Engine has absolute veto power (cannot be bypassed)

## SQLite vs PostgreSQL Compatibility
- Avoid ALTER COLUMN operations (SQLite limitation)
- Use explicit CREATE TABLE migrations instead of autogenerate
- JSON column support across both databases

## Frontend Development (Next.js)
- Next.js 14 App Router architecture
- TypeScript strict mode configuration
- TailwindCSS v3 styling with custom configuration
- React Query for server state management
- Axios with interceptors for API client
- Context API for global state (ModeProvider)
- Custom hooks pattern for data fetching
- Component library with CVA (class-variance-authority)
- Jest + React Testing Library for unit tests

## Frontend Patterns
- Provider composition (QueryProvider → ModeProvider → children)
- Error boundary for graceful error handling
- Form validation patterns with useState
- Token management (localStorage for persistence)
- Automatic token injection via axios interceptors
- 401 response handling with auto-logout
- Mode-aware UI components (GUIDE vs AUTONOMOUS)
- Responsive layout with sidebar navigation

## Frontend Testing
- Jest configuration for Next.js projects
- jest-environment-jsdom for DOM testing
- @testing-library/react for component testing
- Mock service layer for isolated tests
- Test file organization by component type
