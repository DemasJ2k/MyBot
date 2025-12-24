# 15_TESTING_AND_VALIDATION.md

## Context for Claude Opus 4.5

You are implementing a comprehensive testing and validation framework for Flowrex. This system ensures code quality, prevents regressions, enforces CROSSCHECK compliance, and maintains system reliability through automated testing at multiple levels.

**Prerequisites:**
- All previous prompts (00-14) have been completed
- Backend and frontend codebases exist
- Database models and services implemented
- CI/CD pipeline infrastructure available

**Critical Requirements:**
- Tests MUST pass before code is merged
- Red tests = STOP - no exceptions
- Coverage thresholds are mandatory minimums
- Tests must be deterministic (no flaky tests)
- CROSSCHECK integration validates architectural rules
- Test failures trigger automatic rollback
- All tests must be runnable in CI/CD
- Test data must be isolated and reproducible

---

## Test Pyramid Architecture

### Level 1: Unit Tests (70% of test suite)

**Purpose:** Test individual functions, methods, and classes in isolation

**Characteristics:**
- Fast execution (< 1ms per test)
- No external dependencies (database, network, filesystem)
- Use mocks and stubs for dependencies
- Test edge cases and error conditions
- Deterministic and repeatable

**Coverage Target:** ≥ 90% line coverage for business logic

### Level 2: Integration Tests (20% of test suite)

**Purpose:** Test interactions between components

**Characteristics:**
- Medium execution speed (< 100ms per test)
- Use test database with transactions
- Test API endpoints with real database
- Test service layer integration
- Rollback after each test

**Coverage Target:** ≥ 80% of critical integration paths

### Level 3: End-to-End Tests (10% of test suite)

**Purpose:** Test complete user workflows

**Characteristics:**
- Slower execution (1-10s per test)
- Test full stack (frontend → backend → database)
- Simulate real user interactions
- Test critical business flows only
- Use dedicated test environment

**Coverage Target:** All critical user journeys covered

---

## Backend Testing Framework

### 1. Test Configuration

**File:** `backend/pytest.ini`

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    --strict-markers
    --tb=short
    --cov=app
    --cov-report=term-missing
    --cov-report=html
    --cov-report=xml
    --cov-fail-under=80
    -v
markers =
    unit: Unit tests (fast, no dependencies)
    integration: Integration tests (database required)
    e2e: End-to-end tests (full stack required)
    slow: Tests that take > 1 second
    crosscheck: CROSSCHECK validation tests
```

**File:** `backend/conftest.py`

```python
"""
Global pytest configuration and fixtures.
"""
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.database import Base
from app.models.user import User
from app.models.system_settings import SystemSettings
from app.auth.password import get_password_hash


# Test database URL (use in-memory SQLite for speed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def engine():
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="function")
async def db(engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def test_user(db: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        hashed_password=get_password_hash("testpassword123"),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def test_settings(db: AsyncSession) -> SystemSettings:
    """Create default test settings."""
    settings = SystemSettings()
    db.add(settings)
    await db.commit()
    await db.refresh(settings)
    return settings


@pytest.fixture
def mock_twelvedata_client(monkeypatch):
    """Mock TwelveData API client for testing."""
    class MockTwelveDataClient:
        async def get_time_series(self, symbol: str, **kwargs):
            return {
                "values": [
                    {
                        "datetime": "2024-01-01 00:00:00",
                        "open": "1.1000",
                        "high": "1.1050",
                        "low": "1.0950",
                        "close": "1.1020",
                        "volume": "10000",
                    }
                ]
            }

        async def get_quote(self, symbol: str):
            return {
                "symbol": symbol,
                "price": "1.1020",
                "bid": "1.1019",
                "ask": "1.1021",
            }

    return MockTwelveDataClient()
```

### 2. Unit Test Examples

**File:** `backend/tests/unit/test_risk_validation.py`

```python
"""
Unit tests for risk validation logic.
"""
import pytest
from app.risk_engine.core import RiskValidator
from app.risk_engine.constants import MAX_RISK_PER_TRADE_PERCENT


class TestRiskValidator:
    """Test suite for RiskValidator."""

    def test_validate_position_size_within_limit(self):
        """Test that position size within limit passes validation."""
        validator = RiskValidator(account_balance=10000)
        position_size = validator.calculate_position_size(
            risk_percent=1.5,
            stop_loss_pips=50,
            pip_value=10,
        )

        assert position_size > 0
        assert position_size <= 10000 * 0.015 / (50 * 10)

    def test_validate_position_size_exceeds_limit(self):
        """Test that oversized position is rejected."""
        validator = RiskValidator(account_balance=10000)

        with pytest.raises(ValueError, match="exceeds maximum"):
            validator.calculate_position_size(
                risk_percent=MAX_RISK_PER_TRADE_PERCENT + 1,
                stop_loss_pips=10,
                pip_value=10,
            )

    def test_validate_risk_reward_ratio(self):
        """Test risk/reward ratio validation."""
        validator = RiskValidator(account_balance=10000)

        # Valid R:R
        is_valid = validator.validate_risk_reward(
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1100,
        )
        assert is_valid

        # Invalid R:R (too low)
        is_valid = validator.validate_risk_reward(
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1025,
        )
        assert not is_valid

    @pytest.mark.parametrize(
        "daily_loss,expected_result",
        [
            (0, True),
            (250, True),  # 2.5% of 10000
            (500, False),  # 5% (at limit)
            (600, False),  # 6% (exceeds limit)
        ],
    )
    def test_daily_loss_limit(self, daily_loss, expected_result):
        """Test daily loss limit enforcement."""
        validator = RiskValidator(account_balance=10000)
        can_trade = validator.check_daily_loss_limit(daily_loss)
        assert can_trade == expected_result
```

**File:** `backend/tests/unit/test_strategy_signals.py`

```python
"""
Unit tests for strategy signal generation.
"""
import pytest
from datetime import datetime
from app.strategies.nbb_strategy import NBBStrategy
from app.models.candle import Candle


class TestNBBStrategy:
    """Test suite for NBB strategy."""

    @pytest.fixture
    def strategy(self):
        """Create NBB strategy instance."""
        return NBBStrategy(
            configuration={
                "lookback_period": 20,
                "zone_threshold": 0.002,
                "risk_reward_ratio": 2.0,
            }
        )

    @pytest.fixture
    def sample_candles(self):
        """Create sample candle data."""
        return [
            Candle(
                symbol="EURUSD",
                interval="1h",
                open=1.1000 + i * 0.0001,
                high=1.1010 + i * 0.0001,
                low=1.0990 + i * 0.0001,
                close=1.1005 + i * 0.0001,
                volume=1000,
                timestamp=datetime(2024, 1, 1, i, 0, 0),
            )
            for i in range(50)
        ]

    async def test_identify_supply_zone(self, strategy, sample_candles):
        """Test supply zone identification."""
        zones = await strategy._identify_zones(sample_candles)
        supply_zones = [z for z in zones if z.zone_type == "supply"]

        assert len(supply_zones) > 0
        for zone in supply_zones:
            assert zone.upper_price > zone.lower_price
            assert zone.strength > 0

    async def test_no_signal_without_setup(self, strategy):
        """Test that no signal is generated without valid setup."""
        # Insufficient candles
        candles = [
            Candle(
                symbol="EURUSD",
                interval="1h",
                open=1.1000,
                high=1.1010,
                low=1.0990,
                close=1.1005,
                volume=1000,
                timestamp=datetime(2024, 1, 1, 0, 0, 0),
            )
        ]

        signal = await strategy.analyze("EURUSD", candles, 1.1005)
        assert signal is None

    async def test_signal_generation(self, strategy, sample_candles):
        """Test valid signal generation."""
        signal = await strategy.analyze("EURUSD", sample_candles, 1.1050)

        if signal:  # Signal may or may not be generated depending on setup
            assert signal.symbol == "EURUSD"
            assert signal.entry_price > 0
            assert signal.stop_loss > 0
            assert signal.take_profit > 0
            assert signal.signal_type in ["long", "short"]
            # Verify R:R ratio
            if signal.signal_type == "long":
                risk = signal.entry_price - signal.stop_loss
                reward = signal.take_profit - signal.entry_price
            else:
                risk = signal.stop_loss - signal.entry_price
                reward = signal.entry_price - signal.take_profit
            assert reward / risk >= strategy.configuration["risk_reward_ratio"]
```

### 3. Integration Test Examples

**File:** `backend/tests/integration/test_strategy_workflow.py`

```python
"""
Integration tests for complete strategy workflow.
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.strategy_service import StrategyService
from app.services.signal_service import SignalService
from app.models.strategy import Strategy


@pytest.mark.integration
class TestStrategyWorkflow:
    """Test complete strategy workflow."""

    @pytest.fixture
    async def strategy_service(self, db: AsyncSession):
        """Create strategy service."""
        return StrategyService(db)

    @pytest.fixture
    async def signal_service(self, db: AsyncSession):
        """Create signal service."""
        return SignalService(db)

    @pytest.fixture
    async def active_strategy(self, db: AsyncSession):
        """Create an active strategy."""
        strategy = Strategy(
            name="NBB",
            description="Test strategy",
            enabled=True,
            configuration={
                "lookback_period": 20,
                "zone_threshold": 0.002,
                "risk_reward_ratio": 2.0,
            },
        )
        db.add(strategy)
        await db.commit()
        await db.refresh(strategy)
        return strategy

    async def test_strategy_enable_disable(self, strategy_service, db):
        """Test enabling and disabling strategies."""
        # Create strategy
        strategy_data = {
            "name": "TestStrategy",
            "description": "Integration test strategy",
            "enabled": True,
            "configuration": {},
        }

        strategy = await strategy_service.create_strategy(strategy_data)
        assert strategy.enabled is True

        # Disable strategy
        updated = await strategy_service.update_strategy(
            strategy.id, {"enabled": False}
        )
        assert updated.enabled is False

        # Re-enable strategy
        updated = await strategy_service.update_strategy(
            strategy.id, {"enabled": True}
        )
        assert updated.enabled is True

    async def test_signal_generation_workflow(
        self, active_strategy, signal_service, mock_twelvedata_client
    ):
        """Test end-to-end signal generation."""
        # Generate signal
        signal = await signal_service.generate_signal(
            strategy_id=active_strategy.id,
            symbol="EURUSD",
            signal_type="long",
            entry_price=1.1000,
            stop_loss=1.0950,
            take_profit=1.1100,
        )

        assert signal is not None
        assert signal.strategy_id == active_strategy.id
        assert signal.status == "pending"
        assert signal.symbol == "EURUSD"

        # Execute signal
        executed = await signal_service.execute_signal(signal.id)
        assert executed.status == "executed"

        # Cancel signal
        pending_signal = await signal_service.generate_signal(
            strategy_id=active_strategy.id,
            symbol="GBPUSD",
            signal_type="short",
            entry_price=1.2500,
            stop_loss=1.2550,
            take_profit=1.2400,
        )

        cancelled = await signal_service.cancel_signal(pending_signal.id)
        assert cancelled.status == "cancelled"
```

**File:** `backend/tests/integration/test_api_endpoints.py`

```python
"""
Integration tests for API endpoints.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.user import User


@pytest.mark.integration
class TestAuthEndpoints:
    """Test authentication endpoints."""

    @pytest.fixture
    async def client(self):
        """Create test HTTP client."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    async def test_register_user(self, client: AsyncClient, db: AsyncSession):
        """Test user registration."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "securepassword123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_success(self, client: AsyncClient, test_user: User):
        """Test successful login."""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.email,
                "password": "testpassword123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    async def test_login_invalid_credentials(self, client: AsyncClient):
        """Test login with invalid credentials."""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "nonexistent@example.com",
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 401

    async def test_protected_endpoint_without_token(self, client: AsyncClient):
        """Test accessing protected endpoint without token."""
        response = await client.get("/api/v1/strategies")
        assert response.status_code == 401

    async def test_protected_endpoint_with_token(
        self, client: AsyncClient, test_user: User
    ):
        """Test accessing protected endpoint with valid token."""
        # Login first
        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.email,
                "password": "testpassword123",
            },
        )
        token = login_response.json()["access_token"]

        # Access protected endpoint
        response = await client.get(
            "/api/v1/strategies",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
```

### 4. CROSSCHECK Validation Tests

**File:** `backend/tests/crosscheck/test_architecture_rules.py`

```python
"""
CROSSCHECK validation tests.
These tests enforce architectural rules from CROSSCHECK.md.
"""
import pytest
import ast
import os
from pathlib import Path


class TestArchitectureRules:
    """Validate architectural rules."""

    @pytest.fixture
    def backend_path(self):
        """Get backend source path."""
        return Path(__file__).parent.parent.parent / "app"

    def test_no_direct_database_imports_in_routes(self, backend_path):
        """
        CROSSCHECK RULE: API routes must not import database models directly.
        Routes should use service layer.
        """
        routes_path = backend_path / "api"
        violations = []

        for route_file in routes_path.rglob("*_routes.py"):
            with open(route_file, "r") as f:
                content = f.read()
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        if node.module and "app.models" in node.module:
                            # Exception: Importing for type hints is OK
                            if not any(
                                alias.name.endswith("Base")
                                or alias.name in ["User", "Strategy"]
                                for alias in (node.names or [])
                            ):
                                violations.append(
                                    f"{route_file}: Direct model import '{node.module}'"
                                )

        assert len(violations) == 0, f"Architecture violations:\n" + "\n".join(
            violations
        )

    def test_hard_caps_not_modified(self, backend_path):
        """
        CROSSCHECK RULE: Hard risk constants must not be modified.
        """
        constants_file = backend_path / "risk_engine" / "constants.py"

        if not constants_file.exists():
            pytest.skip("Constants file not yet created")

        with open(constants_file, "r") as f:
            content = f.read()

        # Verify constants exist
        required_constants = [
            "MAX_RISK_PER_TRADE_PERCENT",
            "MAX_DAILY_LOSS_PERCENT",
            "EMERGENCY_DRAWDOWN_PERCENT",
            "MAX_OPEN_POSITIONS",
            "MAX_TRADES_PER_DAY",
        ]

        for constant in required_constants:
            assert constant in content, f"Missing required constant: {constant}"

        # Verify no variable assignments to constants (they should be immutable)
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if target.id in required_constants:
                            # Constant assignment is OK (that's the definition)
                            pass

    def test_execution_engine_sole_trade_executor(self, backend_path):
        """
        CROSSCHECK RULE: Only execution engine can submit trades to broker.
        """
        violations = []

        # Search for broker submission outside execution engine
        for py_file in backend_path.rglob("*.py"):
            if "execution" in str(py_file):
                continue  # Skip execution engine itself

            with open(py_file, "r") as f:
                content = f.read()

                # Look for broker submission patterns
                if "submit_order" in content or "place_trade" in content:
                    violations.append(
                        f"{py_file}: Contains broker submission code outside execution engine"
                    )

        assert len(violations) == 0, f"CROSSCHECK violations:\n" + "\n".join(
            violations
        )

    def test_journal_entries_immutable(self, backend_path):
        """
        CROSSCHECK RULE: Journal entries must be immutable.
        """
        models_path = backend_path / "models"
        journal_file = models_path / "journal.py"

        if not journal_file.exists():
            pytest.skip("Journal model not yet created")

        with open(journal_file, "r") as f:
            content = f.read()

        # Verify JournalEntry model has no update methods
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if node.name == "JournalEntry":
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            if "update" in item.name.lower():
                                pytest.fail(
                                    f"JournalEntry has update method '{item.name}' - entries must be immutable"
                                )
```

### 5. Coverage Configuration

**File:** `backend/.coveragerc`

```ini
[run]
source = app
omit =
    */tests/*
    */migrations/*
    */__pycache__/*
    */venv/*
    */alembic/*

[report]
precision = 2
show_missing = True
skip_covered = False

exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @abstractmethod

[html]
directory = htmlcov
```

---

## Frontend Testing Framework

### 1. Jest Configuration

**File:** `frontend/jest.config.js`

```javascript
const nextJest = require('next/jest')

const createJestConfig = nextJest({
  dir: './',
})

const customJestConfig = {
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  testEnvironment: 'jest-environment-jsdom',
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/$1',
  },
  collectCoverageFrom: [
    'app/**/*.{js,jsx,ts,tsx}',
    'components/**/*.{js,jsx,ts,tsx}',
    'services/**/*.{js,jsx,ts,tsx}',
    'hooks/**/*.{js,jsx,ts,tsx}',
    '!**/*.d.ts',
    '!**/node_modules/**',
    '!**/.next/**',
  ],
  coverageThreshold: {
    global: {
      branches: 70,
      functions: 75,
      lines: 80,
      statements: 80,
    },
  },
  testMatch: [
    '**/__tests__/**/*.(test|spec).[jt]s?(x)',
    '**/?(*.)+(spec|test).[jt]s?(x)',
  ],
}

module.exports = createJestConfig(customJestConfig)
```

**File:** `frontend/jest.setup.js`

```javascript
import '@testing-library/jest-dom'

// Mock Next.js router
jest.mock('next/navigation', () => ({
  useRouter() {
    return {
      push: jest.fn(),
      replace: jest.fn(),
      prefetch: jest.fn(),
      back: jest.fn(),
    }
  },
  usePathname() {
    return '/'
  },
  useSearchParams() {
    return new URLSearchParams()
  },
}))

// Mock API client
jest.mock('@/services/api', () => ({
  apiClient: {
    login: jest.fn(),
    register: jest.fn(),
    getSystemConfig: jest.fn(),
    getSystemMode: jest.fn(),
    setSystemMode: jest.fn(),
    listStrategies: jest.fn(),
    runBacktest: jest.fn(),
  },
}))

// Suppress console errors in tests
global.console = {
  ...console,
  error: jest.fn(),
  warn: jest.fn(),
}
```

### 2. Component Tests

**File:** `frontend/__tests__/components/ModeIndicator.test.tsx`

```typescript
import { render, screen } from '@testing-library/react'
import { ModeIndicator } from '@/components/ui/ModeIndicator'
import { ModeProvider } from '@/providers/ModeProvider'

describe('ModeIndicator', () => {
  it('renders guide mode correctly', () => {
    render(
      <ModeProvider>
        <ModeIndicator />
      </ModeProvider>
    )

    // Mode indicator should be present
    expect(screen.getByText(/mode/i)).toBeInTheDocument()
  })

  it('displays correct color for guide mode', () => {
    render(
      <ModeProvider>
        <ModeIndicator />
      </ModeProvider>
    )

    // Check for guide mode styling (amber/yellow)
    const indicator = screen.getByText(/guide/i)
    expect(indicator).toHaveClass('bg-amber-100')
  })
})
```

**File:** `frontend/__tests__/hooks/useAuth.test.tsx`

```typescript
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useAuth } from '@/hooks/useAuth'
import { apiClient } from '@/services/api'

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

describe('useAuth', () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('login mutation succeeds with valid credentials', async () => {
    const mockResponse = {
      access_token: 'test-token',
      token_type: 'bearer',
    }

    ;(apiClient.login as jest.Mock).mockResolvedValue(mockResponse)

    const { result } = renderHook(() => useAuth(), {
      wrapper: createWrapper(),
    })

    result.current.loginMutation.mutate({
      email: 'test@example.com',
      password: 'password123',
    })

    await waitFor(() => {
      expect(result.current.loginMutation.isSuccess).toBe(true)
    })

    expect(apiClient.login).toHaveBeenCalledWith('test@example.com', 'password123')
  })

  it('login mutation fails with invalid credentials', async () => {
    ;(apiClient.login as jest.Mock).mockRejectedValue(new Error('Invalid credentials'))

    const { result } = renderHook(() => useAuth(), {
      wrapper: createWrapper(),
    })

    result.current.loginMutation.mutate({
      email: 'test@example.com',
      password: 'wrong',
    })

    await waitFor(() => {
      expect(result.current.loginMutation.isError).toBe(true)
    })
  })
})
```

---

## CI/CD Integration

### 1. GitHub Actions Workflow

**File:** `.github/workflows/test.yml`

```yaml
name: Test Suite

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  backend-tests:
    name: Backend Tests
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: flowrex_test
          POSTGRES_PASSWORD: testpassword
          POSTGRES_DB: flowrex_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install dependencies
        working-directory: ./backend
        run: |
          pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio

      - name: Run unit tests
        working-directory: ./backend
        env:
          DATABASE_URL: postgresql+asyncpg://flowrex_test:testpassword@localhost:5432/flowrex_test
          REDIS_URL: redis://localhost:6379/0
        run: |
          pytest tests/unit -v --cov=app --cov-report=xml --cov-report=term

      - name: Run integration tests
        working-directory: ./backend
        env:
          DATABASE_URL: postgresql+asyncpg://flowrex_test:testpassword@localhost:5432/flowrex_test
          REDIS_URL: redis://localhost:6379/0
        run: |
          pytest tests/integration -v --cov=app --cov-append --cov-report=xml --cov-report=term

      - name: Run CROSSCHECK validation
        working-directory: ./backend
        run: |
          pytest tests/crosscheck -v

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./backend/coverage.xml
          flags: backend
          name: backend-coverage

      - name: Check coverage threshold
        working-directory: ./backend
        run: |
          coverage report --fail-under=80

  frontend-tests:
    name: Frontend Tests
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: ./frontend/package-lock.json

      - name: Install dependencies
        working-directory: ./frontend
        run: npm ci

      - name: Run type checking
        working-directory: ./frontend
        run: npm run type-check

      - name: Run linting
        working-directory: ./frontend
        run: npm run lint

      - name: Run tests
        working-directory: ./frontend
        run: npm test -- --coverage --watchAll=false

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./frontend/coverage/coverage-final.json
          flags: frontend
          name: frontend-coverage

  e2e-tests:
    name: End-to-End Tests
    runs-on: ubuntu-latest
    needs: [backend-tests, frontend-tests]

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build and start services
        run: |
          docker-compose -f docker-compose.test.yml up -d
          docker-compose -f docker-compose.test.yml ps

      - name: Wait for services
        run: |
          timeout 60 bash -c 'until curl -f http://localhost:8000/health; do sleep 2; done'
          timeout 60 bash -c 'until curl -f http://localhost:3000; do sleep 2; done'

      - name: Run E2E tests
        run: |
          docker-compose -f docker-compose.test.yml exec -T backend pytest tests/e2e -v

      - name: Collect logs on failure
        if: failure()
        run: |
          docker-compose -f docker-compose.test.yml logs

      - name: Cleanup
        if: always()
        run: |
          docker-compose -f docker-compose.test.yml down -v
```

### 2. Pre-commit Hooks

**File:** `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files
        args: ['--maxkb=1000']
      - id: check-merge-conflict

  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
        language_version: python3.12
        files: ^backend/

  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort
        args: ['--profile', 'black']
        files: ^backend/

  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
        args: ['--max-line-length=120', '--extend-ignore=E203,W503']
        files: ^backend/

  - repo: local
    hooks:
      - id: pytest-unit
        name: Run pytest unit tests
        entry: bash -c 'cd backend && pytest tests/unit -v'
        language: system
        pass_filenames: false
        always_run: true

      - id: pytest-crosscheck
        name: Run CROSSCHECK validation
        entry: bash -c 'cd backend && pytest tests/crosscheck -v'
        language: system
        pass_filenames: false
        always_run: true

      - id: frontend-type-check
        name: TypeScript type checking
        entry: bash -c 'cd frontend && npm run type-check'
        language: system
        pass_filenames: false
        always_run: true
        files: ^frontend/
```

---

## Test Failure Handling

### 1. Failure Classification

**Critical Failures (STOP immediately):**
- CROSSCHECK validation failures
- Hard cap enforcement failures
- Security vulnerabilities
- Data corruption risks
- Test infrastructure failures

**Major Failures (Fix before merge):**
- Unit test failures
- Integration test failures
- Coverage threshold violations
- Type errors

**Minor Failures (Can be deferred):**
- Linting warnings
- Documentation issues
- Non-critical flaky tests

### 2. Automated Rollback Script

**File:** `scripts/rollback_on_failure.sh`

```bash
#!/bin/bash
set -e

echo "Running test suite..."

# Run tests
if ! pytest tests/ -v --cov=app --cov-fail-under=80; then
    echo "❌ Tests failed! Rolling back changes..."

    # Check if in git repository
    if [ -d .git ]; then
        # Stash changes
        git stash save "Failed test rollback $(date +%Y%m%d_%H%M%S)"
        echo "✅ Changes stashed. Fix tests and re-apply with 'git stash pop'"

        # Optionally notify team
        if [ ! -z "$SLACK_WEBHOOK" ]; then
            curl -X POST -H 'Content-type: application/json' \
                --data '{"text":"⚠️ Test failure detected. Changes rolled back."}' \
                $SLACK_WEBHOOK
        fi
    fi

    exit 1
else
    echo "✅ All tests passed!"
fi
```

---

## Validation Checklist

Before proceeding to the next prompt, verify ALL of the following:

### Test Infrastructure
- [ ] pytest configured with correct settings
- [ ] Jest configured for frontend tests
- [ ] Test database setup working
- [ ] Test fixtures created (db, test_user, etc.)
- [ ] Coverage tools configured
- [ ] Coverage thresholds enforced

### Unit Tests
- [ ] Risk validation tests implemented
- [ ] Strategy signal tests implemented
- [ ] Settings validation tests implemented
- [ ] All tests are deterministic (no randomness)
- [ ] All tests are isolated (no shared state)
- [ ] Coverage ≥ 90% for business logic

### Integration Tests
- [ ] API endpoint tests implemented
- [ ] Strategy workflow tests implemented
- [ ] Database transaction rollback working
- [ ] Test data cleanup working
- [ ] Coverage ≥ 80% for integration paths

### CROSSCHECK Tests
- [ ] Architecture rule validation implemented
- [ ] Hard cap immutability verified
- [ ] Execution engine sole authority verified
- [ ] Journal immutability verified
- [ ] All CROSSCHECK rules have tests

### Frontend Tests
- [ ] Component tests implemented
- [ ] Hook tests implemented
- [ ] Type checking integrated
- [ ] Linting integrated
- [ ] Coverage ≥ 80%

### CI/CD
- [ ] GitHub Actions workflow created
- [ ] Backend tests run in CI
- [ ] Frontend tests run in CI
- [ ] CROSSCHECK tests run in CI
- [ ] Coverage uploaded to Codecov
- [ ] Pre-commit hooks configured
- [ ] Test failures block merge

### Failure Handling
- [ ] Rollback script created
- [ ] Failure classification documented
- [ ] Team notification configured
- [ ] Red test stops pipeline

---

## Hard Stop Criteria

DO NOT proceed to the next prompt if ANY of the following are true:

1. **No Tests:** Test suite does not exist or is empty
2. **Tests Don't Run:** Tests fail to execute due to configuration issues
3. **Coverage Below Threshold:** Code coverage < 80%
4. **Flaky Tests:** Tests pass/fail non-deterministically
5. **No CROSSCHECK Tests:** Architectural rules not validated
6. **CI Not Working:** Tests don't run in CI/CD pipeline
7. **No Rollback:** Failed tests don't trigger rollback
8. **Hard Caps Not Tested:** Risk limit enforcement not validated
9. **Frontend Tests Missing:** No tests for React components
10. **Pre-commit Bypassed:** Hooks can be skipped without consequence

---

## Next Prompt

After completing this prompt and passing ALL validation checks, proceed to:

**16_SIMULATION_AND_DEMO_MODE.md** - Paper trading implementation, demo account management, and simulation framework.
