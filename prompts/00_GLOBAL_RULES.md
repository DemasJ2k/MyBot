# Global Rules and Standards

## Purpose

This document defines universal rules, standards, and conventions that apply to ALL code you write throughout the Flowrex build. These are non-negotiable and must be followed consistently.

---

## Code Style Standards

### Python (Backend)

**Formatting**:
- Use **Black** formatter with default settings (88 character line length)
- Use **isort** for import sorting (Black-compatible profile)
- 4 spaces for indentation (no tabs)
- 2 blank lines between top-level functions/classes
- 1 blank line between methods in a class

**Import Organization**:
```python
# Standard library imports
import os
import sys
from datetime import datetime
from typing import List, Optional

# Third-party imports
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import Column, String, Integer
from pydantic import BaseModel

# Local imports
from app.database import get_db
from app.models.user import User
from app.auth.dependencies import get_current_user
```

**Type Hints** (REQUIRED):
```python
# All function signatures must have type hints
def calculate_position_size(
    account_balance: float,
    risk_percent: float,
    entry_price: float,
    stop_loss: float
) -> float:
    """Calculate position size based on risk parameters."""
    risk_amount = account_balance * (risk_percent / 100)
    price_difference = abs(entry_price - stop_loss)
    return risk_amount / price_difference

# Use Optional for nullable values
def get_user_by_email(email: str) -> Optional[User]:
    """Find user by email, return None if not found."""
    pass

# Use List, Dict, Tuple from typing
def get_recent_signals(limit: int = 10) -> List[Signal]:
    """Get list of recent signals."""
    pass
```

**Docstrings** (Required for all public functions):
```python
def validate_trade_plan(plan: TradePlan, settings: UserSettings) -> RiskDecision:
    """
    Validate trade plan against user risk settings.

    Args:
        plan: Trade plan with entry, SL, TP
        settings: User risk preferences and limits

    Returns:
        RiskDecision with approval status and reasoning

    Raises:
        ValueError: If plan has invalid values
    """
    pass
```

**Async/Await**:
- Use async/await for all database operations
- Use async/await for all HTTP requests
- Use async/await for all I/O operations

```python
# Correct
async def get_candles(symbol: str) -> List[Candle]:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            return normalize_candles(data)

# Wrong - synchronous HTTP call
def get_candles(symbol: str) -> List[Candle]:
    response = requests.get(url)  # BAD - blocking
    return response.json()
```

---

### TypeScript/React (Frontend)

**Formatting**:
- Use **Prettier** with default settings
- 2 spaces for indentation
- Semicolons required
- Single quotes for strings
- Trailing commas in objects/arrays

**File Naming**:
- Components: PascalCase (`TradingChart.tsx`, `SignalCard.tsx`)
- Utilities: camelCase (`formatPrice.ts`, `calculatePnl.ts`)
- Pages: lowercase (`page.tsx` in Next.js App Router)

**Component Structure**:
```typescript
// Imports grouped
import { useState, useEffect } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { Button } from '@/components/common/Button'
import { api } from '@/services/api'

// Types defined at top
interface SignalCardProps {
  signal: Signal
  onExecute: (signalId: number) => void
  onDismiss: (signalId: number) => void
}

// Component
export function SignalCard({ signal, onExecute, onDismiss }: SignalCardProps) {
  const [isExecuting, setIsExecuting] = useState(false)

  // Early returns for loading/error states
  if (!signal) {
    return <div>No signal data</div>
  }

  // Event handlers
  const handleExecute = async () => {
    setIsExecuting(true)
    try {
      await onExecute(signal.id)
    } catch (error) {
      console.error('Execution failed:', error)
    } finally {
      setIsExecuting(false)
    }
  }

  // Render
  return (
    <div className="signal-card">
      {/* Component JSX */}
    </div>
  )
}
```

**Type Safety**:
```typescript
// Define all API response types
export interface Signal {
  id: number
  symbol: string
  direction: 'long' | 'short'
  entry_price: number
  stop_loss: number
  take_profit: number | null
  confidence: number
  reasoning: string
  status: 'pending' | 'executed' | 'dismissed' | 'expired'
  created_at: string
}

// Use types for function parameters and return values
async function getSignals(status?: Signal['status']): Promise<Signal[]> {
  const response = await api.get<Signal[]>('/signals', { params: { status } })
  return response.data
}

// No 'any' types (use 'unknown' if truly unknown)
// BAD
function processData(data: any) { ... }

// GOOD
function processData(data: unknown) {
  if (typeof data === 'object' && data !== null) {
    // Type guard
  }
}
```

---

## Naming Conventions

### Variables and Functions

**Python**:
```python
# Variables: snake_case
account_balance = 10000
daily_loss_limit = 5.0
max_position_size = 1.0

# Functions: snake_case (verb_noun pattern)
def calculate_risk_amount(balance: float, risk_percent: float) -> float:
    pass

def validate_trade_plan(plan: TradePlan) -> bool:
    pass

def get_user_by_id(user_id: int) -> Optional[User]:
    pass

# Classes: PascalCase (noun)
class RiskEngine:
    pass

class StrategyAnalyst:
    pass

# Constants: SCREAMING_SNAKE_CASE
MAX_RISK_PER_TRADE = 2.0
DATABASE_URL = "postgresql://..."
API_RATE_LIMIT = 100
```

**TypeScript**:
```typescript
// Variables: camelCase
const accountBalance = 10000
const dailyLossLimit = 5.0

// Functions: camelCase (verb + noun)
function calculatePositionSize(entry: number, stop: number): number { }
function formatPrice(price: number, decimals: number): string { }

// Components: PascalCase (noun)
function SignalCard() { }
function TradingChart() { }

// Constants: SCREAMING_SNAKE_CASE
const MAX_RETRIES = 3
const API_BASE_URL = '/api/v1'

// Enums: PascalCase
enum TradeDirection {
  Long = 'long',
  Short = 'short'
}
```

### Files and Directories

**Backend**:
```
backend/
├── app/
│   ├── models/         # Database models (user.py, trade.py)
│   ├── schemas/        # Pydantic schemas (user_schema.py)
│   ├── api/v1/         # API routes (auth_routes.py, signal_routes.py)
│   ├── services/       # Business logic (signal_service.py)
│   ├── utils/          # Helper functions (indicators.py, validators.py)
│   └── core/           # Core utilities (config.py, exceptions.py)
```

**Frontend**:
```
frontend/
├── app/                # Next.js pages
├── components/         # React components (PascalCase.tsx)
├── hooks/              # Custom hooks (useAuth.ts)
├── services/           # API clients (api.ts, ws.ts)
├── types/              # TypeScript types (index.ts)
└── utils/              # Helper functions (formatters.ts)
```

---

## Error Handling Patterns

### Python

**Use try-except blocks**:
```python
async def get_candles_from_api(symbol: str) -> List[Candle]:
    """Fetch candles with proper error handling."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                return normalize_candles(data)

    except aiohttp.ClientError as e:
        logger.error(f"HTTP error fetching candles for {symbol}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch data for {symbol}"
        )

    except ValueError as e:
        logger.error(f"Data normalization error for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Invalid data format from provider"
        )

    except Exception as e:
        logger.error(f"Unexpected error fetching candles: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
```

**Custom exceptions**:
```python
# Define in app/core/exceptions.py
class RiskLimitExceeded(Exception):
    """Raised when trade violates risk limits."""
    pass

class InsufficientBalance(Exception):
    """Raised when account balance too low."""
    pass

# Use in code
if daily_loss > max_daily_loss:
    raise RiskLimitExceeded(
        f"Daily loss {daily_loss}% exceeds limit {max_daily_loss}%"
    )
```

### TypeScript

**Try-catch for async operations**:
```typescript
async function executeSignal(signalId: number): Promise<void> {
  try {
    const response = await api.post(`/signals/${signalId}/execute`)
    toast.success('Signal executed successfully')
    return response.data
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const message = error.response?.data?.detail || 'Execution failed'
      toast.error(message)
      throw new Error(message)
    }
    throw error
  }
}
```

**Error boundaries for React components**:
```typescript
// Create ErrorBoundary component
class ErrorBoundary extends React.Component<Props, State> {
  state = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Error caught by boundary:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return <ErrorFallback error={this.state.error} />
    }
    return this.props.children
  }
}
```

---

## Logging Standards

### Python

**Use structured logging**:
```python
import logging

logger = logging.getLogger(__name__)

# Different log levels
logger.debug(f"Fetching candles for {symbol} {timeframe}")
logger.info(f"Signal generated: {signal.id} for {signal.symbol}")
logger.warning(f"Low data quality for {symbol}: missing {missing_count} candles")
logger.error(f"Failed to execute order: {error}", exc_info=True)
logger.critical(f"Database connection lost, attempting reconnect")

# Include context in logs
logger.info(
    "Trade executed",
    extra={
        "trade_id": trade.id,
        "symbol": trade.symbol,
        "direction": trade.direction,
        "size": trade.position_size
    }
)
```

**Never log sensitive data**:
```python
# BAD - logs API key
logger.info(f"Connecting to broker with key: {api_key}")

# GOOD - redact sensitive data
logger.info(f"Connecting to broker with key: {api_key[:4]}...{api_key[-4:]}")
```

### TypeScript

**Console logging**:
```typescript
// Development only
if (process.env.NODE_ENV === 'development') {
  console.log('Signal data:', signal)
}

// Use proper log levels
console.info('User logged in:', user.email)
console.warn('Connection unstable, attempting reconnect')
console.error('Failed to fetch signals:', error)
```

---

## Security Requirements

### NEVER:
1. **Hard-code secrets**:
   ```python
   # BAD
   API_KEY = "sk_live_abc123..."

   # GOOD
   API_KEY = os.getenv("TWELVEDATA_API_KEY")
   if not API_KEY:
       raise ValueError("TWELVEDATA_API_KEY environment variable not set")
   ```

2. **Log sensitive data**:
   ```python
   # BAD
   logger.info(f"User password: {password}")

   # GOOD
   logger.info(f"User {user.email} password updated")
   ```

3. **Return sensitive data in API responses**:
   ```python
   # BAD
   return {"user": user, "password": user.hashed_password}

   # GOOD
   return {"user": UserSchema.from_orm(user)}  # Excludes hashed_password
   ```

4. **Trust user input**:
   ```python
   # BAD
   db.execute(f"SELECT * FROM users WHERE email = '{email}'")  # SQL injection!

   # GOOD
   db.execute("SELECT * FROM users WHERE email = :email", {"email": email})
   ```

### ALWAYS:
1. **Validate input**:
   ```python
   from pydantic import BaseModel, validator

   class CreateSignalRequest(BaseModel):
       symbol: str
       timeframe: str

       @validator('symbol')
       def validate_symbol(cls, v):
           if not v or len(v) > 20:
               raise ValueError("Invalid symbol")
           return v.upper()

       @validator('timeframe')
       def validate_timeframe(cls, v):
           allowed = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']
           if v not in allowed:
               raise ValueError(f"Timeframe must be one of {allowed}")
           return v
   ```

2. **Hash passwords**:
   ```python
   from passlib.context import CryptContext

   pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

   # Hash on registration
   hashed_password = pwd_context.hash(plain_password)

   # Verify on login
   if not pwd_context.verify(plain_password, user.hashed_password):
       raise HTTPException(status_code=401, detail="Invalid credentials")
   ```

3. **Use HTTPS in production**:
   ```python
   # Nginx configuration
   if settings.is_production:
       # Enforce HTTPS
       # Redirect HTTP to HTTPS
       pass
   ```

---

## Testing Requirements

### Test File Naming
```
tests/
├── unit/               # Isolated unit tests
│   ├── test_auth.py
│   ├── test_risk_engine.py
│   └── test_strategies.py
├── integration/        # API integration tests
│   ├── test_auth_routes.py
│   ├── test_signal_lifecycle.py
│   └── test_backtest_flow.py
└── e2e/                # End-to-end tests
    └── test_complete_workflow.py
```

### Test Structure
```python
import pytest
from app.risk_engine.core import RiskEngine

@pytest.fixture
def risk_engine():
    """Create RiskEngine instance for testing."""
    return RiskEngine()

@pytest.fixture
def user_settings():
    """Create sample user settings."""
    return UserSettings(
        default_risk_percent=1.0,
        max_daily_risk_percent=3.0
    )

def test_validate_trade_within_limits(risk_engine, user_settings):
    """Test that valid trade is approved."""
    # Arrange
    plan = TradePlan(
        symbol="EURUSD",
        direction="long",
        entry_price=1.0850,
        stop_loss=1.0820,
        risk_percent=1.0
    )

    # Act
    decision = risk_engine.validate_trade_plan(plan, user_settings)

    # Assert
    assert decision.approved == True
    assert decision.reasoning is not None

def test_validate_trade_exceeds_hard_cap(risk_engine, user_settings):
    """Test that trade exceeding hard cap is rejected."""
    # Arrange
    plan = TradePlan(
        symbol="EURUSD",
        direction="long",
        entry_price=1.0850,
        stop_loss=1.0820,
        risk_percent=3.0  # Exceeds 2% hard cap
    )

    # Act
    decision = risk_engine.validate_trade_plan(plan, user_settings)

    # Assert
    assert decision.approved == False
    assert "hard cap" in decision.reasoning.lower()
```

### Test Coverage
- Aim for >80% code coverage
- Test happy path AND error cases
- Test edge cases (empty lists, None values, boundary conditions)
- Test async functions with `pytest-asyncio`

```python
import pytest

@pytest.mark.asyncio
async def test_fetch_candles_from_api():
    """Test async candle fetching."""
    provider = TwelveDataProvider(api_key="test_key")
    candles = await provider.get_candles("EURUSD", "1h", start_date, end_date)
    assert len(candles) > 0
    assert all(isinstance(c, Candle) for c in candles)
```

---

## Git Commit Standards

### Commit Message Format
```
<type>: <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code refactoring
- `test`: Add or update tests
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `chore`: Build process, dependencies, etc.

**Examples**:
```
feat: Add Fabio strategy implementation

Implement Auction Market Theory strategy with volume profile analysis,
LVN/HVN detection, and order flow confirmation.

Resolves #42

---

fix: Correct position size calculation in Risk Engine

Position size was not accounting for pip value on JPY pairs.
Now correctly adjusts for different pip values.

Fixes #103

---

refactor: Simplify signal generation service

Extract strategy running logic into separate functions for better
testability and maintainability.

---

test: Add unit tests for Fabio strategy

Test volume profile calculation, LVN detection, and signal generation.
Coverage increased to 85%.
```

### Branch Naming
```
feature/add-fabio-strategy
fix/position-size-calculation
refactor/signal-service
test/risk-engine-coverage
```

---

## Database Standards

### Model Definition
```python
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin

class Trade(Base, TimestampMixin):
    """Trade model."""

    __tablename__ = "trades"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Foreign keys
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    # Fields
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="trades")

    def __repr__(self) -> str:
        return f"<Trade(id={self.id}, symbol={self.symbol})>"
```

### Migration Naming
```
alembic/versions/
├── 20240115_000001_create_users_table.py
├── 20240115_000002_add_signals_table.py
├── 20240116_000001_add_risk_settings_to_users.py
```

---

## API Standards

### Endpoint Naming
```python
# RESTful patterns
GET    /api/v1/signals          # List signals
GET    /api/v1/signals/{id}     # Get single signal
POST   /api/v1/signals          # Create signal
PUT    /api/v1/signals/{id}     # Update signal
DELETE /api/v1/signals/{id}     # Delete signal

# Actions (POST)
POST   /api/v1/signals/{id}/execute
POST   /api/v1/signals/{id}/dismiss
POST   /api/v1/backtest/run
POST   /api/v1/optimization/run
```

### Response Format
```python
# Success (200, 201)
{
  "id": 42,
  "symbol": "EURUSD",
  "status": "pending",
  ...
}

# Error (400, 401, 404, 500)
{
  "detail": "Invalid symbol format",
  "error_code": "INVALID_SYMBOL"
}
```

---

## Documentation Standards

### Inline Comments
```python
# Use comments sparingly - code should be self-documenting
# Only comment WHY, not WHAT

# BAD
x = balance * 0.02  # Multiply balance by 0.02

# GOOD
max_risk_amount = balance * 0.02  # 2% hard cap per trade

# GOOD - explaining non-obvious logic
# We use 0.618 Fib level because it's the optimal trade entry (OTE)
# zone where price often reverses in trending markets
ote_level = fib_0_618
```

### Function Docstrings
```python
def calculate_atr(candles: List[Candle], period: int = 14) -> float:
    """
    Calculate Average True Range (ATR) indicator.

    ATR measures market volatility by calculating the average of true ranges
    over a specified period. True range is the greatest of:
    - Current high minus current low
    - Absolute value of current high minus previous close
    - Absolute value of current low minus previous close

    Args:
        candles: List of OHLCV candles (must have at least period + 1 candles)
        period: Number of periods for ATR calculation (default: 14)

    Returns:
        ATR value as float

    Raises:
        ValueError: If candles list is too short or period is invalid

    Example:
        >>> candles = get_candles("EURUSD", "1h")
        >>> atr = calculate_atr(candles, period=14)
        >>> print(f"ATR: {atr:.5f}")
        ATR: 0.00125
    """
    pass
```

---

## Configuration Management

### Environment Variables
```python
# app/config.py
from pydantic_settings import BaseSettings
from pydantic import field_validator

class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite+aiosqlite:///./flowrex_dev.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Security
    app_secret_key: str
    jwt_secret_key: str

    # APIs
    twelvedata_api_key: Optional[str] = None

    @field_validator("app_secret_key", "jwt_secret_key")
    @classmethod
    def validate_secrets(cls, v: str) -> str:
        if not v or v in ["changeme", "your_secret"]:
            raise ValueError("Secret must be set and not a placeholder")
        return v

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
```

---

## Performance Standards

### Database Queries
```python
# Use indexes
symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

# Avoid N+1 queries (use eager loading)
from sqlalchemy.orm import joinedload

users = await db.execute(
    select(User).options(joinedload(User.trades))
)

# Limit results
signals = await db.execute(
    select(Signal).limit(100)
)
```

### Caching
```python
# Use Redis for frequently accessed data
async def get_candles_cached(symbol: str, timeframe: str) -> List[Candle]:
    cache_key = f"candles:{symbol}:{timeframe}"

    # Check cache first
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    # Fetch from API if not cached
    candles = await fetch_from_api(symbol, timeframe)

    # Store in cache with TTL
    await redis.setex(cache_key, 30, json.dumps(candles))  # 30 second TTL

    return candles
```

---

## FINAL RULE

**When in doubt, STOP and ask**:
- Re-read these rules
- Check examples in current codebase
- Consult documentation (FastAPI, SQLAlchemy, Next.js)
- Don't guess - verify

**Quality over speed**:
- Take time to write it right
- Follow these standards consistently
- Write tests as you go
- Refactor when needed

**These rules exist for a reason**:
- Consistency makes code maintainable
- Standards prevent bugs
- Testing catches regressions
- Security protects users

Follow these rules, and you'll build a professional-grade system.

Violate these rules, and you'll create technical debt.

Choose wisely.
