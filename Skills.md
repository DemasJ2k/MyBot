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
- 351 tests total: 297 backend + 41 frontend + 13 E2E (1 skipped)
- Test Pyramid architecture: 70% unit, 20% integration, 10% E2E
- CROSSCHECK architectural validation tests
- Coverage configuration with 80% threshold
- GitHub Actions CI/CD workflow

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

## Frontend Charting (Recharts)
- LineChart for equity curves and time series data
- BarChart for trade distribution and comparisons
- PieChart for allocation and distribution views
- AreaChart for cumulative metrics visualization
- ResponsiveContainer for mobile-friendly charts
- Chart data transformation patterns (API → chart format)
- TypeScript typing for chart components and data
- Custom tooltips and legend formatting

## Multi-Tenancy Testing
- Fixture-based test user creation for foreign key constraints
- Redis mock for token blacklist in tests
- Rate limiter reset between test runs
- User ID propagation through Signal → Position → ExecutionOrder chain

## Settings and Configuration Management
- Singleton pattern for system settings (single source of truth)
- Immutable hard-coded constants that soft settings cannot exceed
- Settings audit trail with version tracking and change reasons
- Mode transition validation rules:
  - GUIDE → AUTONOMOUS requires broker connection (except PAPER)
  - Settings changes recorded with old_values and new_values JSON diff
- SystemMode enum (GUIDE/AUTONOMOUS) for operation mode control
- BrokerType enum (MT5/OANDA/BINANCE/PAPER) for broker selection
- Per-user preferences with favorites (strategies, symbols)
- Settings API with full CRUD operations and audit history

## SQLAlchemy Model Defaults Gotcha
- `mapped_column(default=...)` only applies during database INSERT
- Python model instantiation does NOT apply these defaults
- Tests must explicitly provide all required field values
- Use helper methods to create model instances with explicit defaults

## CROSSCHECK Validation
- Architectural rule enforcement via automated tests
- Hard risk constant validation (existence and safe values)
- Execution engine sole trade executor verification
- Journal entry immutability checks
- Mode enforcement validation
- Audit trail compliance verification
- Multi-tenant foreign key validation
- Safety mechanism verification (emergency shutdown, rate limiting)

## CI/CD Testing
- GitHub Actions workflow for automated testing
- Parallel job execution (unit, crosscheck, frontend)
- PostgreSQL and Redis service containers for integration tests
- Security scanning with safety (Python) and npm audit
- Gate job pattern (all-tests-passed) to ensure quality
## Simulation and Demo Mode (Prompt 16)
- ExecutionMode enum: SIMULATION (default), PAPER, LIVE
- SimulationAccount model with virtual balance tracking:
  - Initial balance configurable (default $10,000)
  - Balance, equity, margin tracking
  - Simulation parameters: slippage_pips, commission_per_lot, latency_ms, fill_probability
  - Trading statistics: total_trades, winning_trades, total_pnl, win_rate
  - Account reset functionality
- SimulationPosition model for virtual positions:
  - Position tracking separate from live
  - SL/TP trigger checking
  - Unrealized P&L calculation
- SimulatedBrokerAdapter extends BaseBrokerAdapter:
  - Database-backed persistent state
  - Realistic execution simulation (latency, slippage, fill probability)
  - Bid/ask spread simulation
  - Full position lifecycle management
- ExecutionModeService for mode transitions:
  - Live mode requires: password verification + explicit confirmation + reason
  - Safety-first design: SIMULATION is always default
  - Full audit trail for mode changes (ExecutionModeAudit)
  - validate_mode_for_action() for mode-restricted operations
- Frontend components:
  - ExecutionModeIndicator (visual mode display)
  - ExecutionModeSelector (mode switching with confirmation dialog)
  - ExecutionModeWarning (live trading warning banner)
  - SimulationAccountCard (account stats display)
- Data isolation: Simulation positions stored separately from live

## E2E Testing Skills
- ASGI transport for standalone E2E testing (no server required)
- Dual-mode fixtures: real server mode vs ASGI transport mode
- Test data isolation with in-memory databases
- Handling graceful skips for missing external data
- JSON vs form-data authentication handling
- Test assertion design for multiple valid API responses

## Debugging Skills
- Identifying field name mismatches (e.g., `timeframe` vs `interval`)
- Tracing Pydantic validation errors to missing class methods
- Root cause analysis for 500 errors in test environments
- Fixture scope management for test isolation
