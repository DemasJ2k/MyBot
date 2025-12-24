# Prompt 02: Backend Core - Authentication & Database

## Objective

Build core backend infrastructure: async database with SQLAlchemy, user authentication with JWT, password hashing with bcrypt, protected API routes, security middleware, and comprehensive testing.

## Prerequisites

- Prompt 01 completed
- All Docker services running and healthy
- Backend responds at http://localhost:8000/health
- PostgreSQL and Redis accessible

## Implementation

### 1. Application Configuration

Create `backend/app/config.py`:

```python
from pydantic_settings import BaseSettings
from pydantic import field_validator
import os

class Settings(BaseSettings):
    app_env: str = "development"
    app_secret_key: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    database_url: str = "sqlite+aiosqlite:///./flowrex_dev.db"
    redis_url: str = "redis://localhost:6379/0"
    debug: bool = True
    csrf_protection_enabled: bool = True

    @field_validator("app_secret_key", "jwt_secret_key")
    @classmethod
    def validate_secrets(cls, v: str, info) -> str:
        if not v and os.getenv("APP_ENV") == "development":
            import secrets
            return secrets.token_hex(32)
        if not v:
            raise ValueError(f"{info.field_name} must be set")
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env in ("production", "prod")

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
```

### 2. Database Setup

Create `backend/app/database.py`:

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from typing import AsyncGenerator
from app.config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug, future=True, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except:
            await session.rollback()
            raise
        finally:
            await session.close()
```

### 3. Base Models

Create `backend/app/models/base.py`:

```python
from datetime import datetime
from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
```

Create `backend/app/models/user.py`:

```python
from typing import Optional
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin

class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

Create `backend/app/models/__init__.py`:

```python
from app.models.base import Base, TimestampMixin
from app.models.user import User
__all__ = ["Base", "TimestampMixin", "User"]
```

### 4. Pydantic Schemas

Create `backend/app/schemas/user_schema.py`:

```python
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be ≥8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Must contain uppercase")
        if not any(c.islower() for c in v):
            raise ValueError("Must contain lowercase")
        if not any(c.isdigit() for c in v):
            raise ValueError("Must contain digit")
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(UserBase):
    id: int
    is_active: bool
    is_verified: bool
    created_at: datetime
    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenRefresh(BaseModel):
    refresh_token: str
```

### 5. Password Hashing

Create `backend/app/auth/password.py`:

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
```

### 6. JWT Utilities

Create `backend/app/auth/jwt.py`:

```python
from datetime import datetime, timedelta
from typing import Dict, Any
from jose import jwt
from app.config import settings

def create_access_token(data: Dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

def create_refresh_token(data: Dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
```

### 7. Auth Dependencies

Create `backend/app/auth/dependencies.py`:

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError
from app.database import get_db
from app.models.user import User
from app.auth.jwt import decode_token

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: AsyncSession = Depends(get_db)) -> User:
    exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise exception
        user_id = payload.get("sub")
        if not user_id:
            raise exception
    except JWTError:
        raise exception

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise exception
    return user
```

### 8. Custom Exceptions

Create `backend/app/core/exceptions.py`:

```python
from fastapi import HTTPException, status

class InvalidCredentialsException(HTTPException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

class UserAlreadyExistsException(HTTPException):
    def __init__(self):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
```

### 9. CSRF Middleware

Create `backend/app/middleware/csrf.py`:

```python
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import settings

class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return await call_next(request)
        if not settings.csrf_protection_enabled or request.url.path.startswith("/api/v1/auth/login"):
            return await call_next(request)
        if not request.headers.get("X-CSRF-Token"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing")
        return await call_next(request)
```

### 10. Auth Routes

Create `backend/app/api/v1/auth_routes.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.schemas.user_schema import UserCreate, UserLogin, UserResponse, TokenResponse, TokenRefresh
from app.auth.password import hash_password, verify_password
from app.auth.jwt import create_access_token, create_refresh_token, decode_token
from app.auth.dependencies import get_current_user
from app.core.exceptions import InvalidCredentialsException, UserAlreadyExistsException

router = APIRouter(tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise UserAlreadyExistsException()
    user = User(email=user_data.email, full_name=user_data.full_name, hashed_password=hash_password(user_data.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(credentials.password, user.hashed_password) or not user.is_active:
        raise InvalidCredentialsException()
    return TokenResponse(
        access_token=create_access_token({"sub": str(user.id)}),
        refresh_token=create_refresh_token({"sub": str(user.id)}),
        expires_in=1800
    )

@router.post("/refresh", response_model=TokenResponse)
async def refresh(token_data: TokenRefresh, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(token_data.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = payload.get("sub")
        result = await db.execute(select(User).where(User.id == int(user_id)))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Invalid user")
        return TokenResponse(
            access_token=create_access_token({"sub": str(user.id)}),
            refresh_token=create_refresh_token({"sub": str(user.id)}),
            expires_in=1800
        )
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return user

@router.post("/logout")
async def logout():
    return {"message": "Logged out"}
```

### 11. API Router

Create `backend/app/api/v1/router.py`:

```python
from fastapi import APIRouter
from app.api.v1 import auth_routes

api_router = APIRouter()
api_router.include_router(auth_routes.router, prefix="/auth")
```

### 12. Update Main App

Update `backend/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.config import settings
from app.api.v1.router import api_router
from app.middleware.csrf import CSRFMiddleware

limiter = Limiter(key_func=get_remote_address, storage_uri=settings.redis_url, default_limits=["200/minute"])
app = FastAPI(title="Flowrex Backend", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(SlowAPIMiddleware)
if settings.is_production:
    app.add_middleware(CSRFMiddleware)

app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/")
async def root():
    return {"message": "Flowrex API"}
```

### 13. Alembic Setup

Create `backend/alembic.ini`:

```ini
[alembic]
script_location = alembic
prepend_sys_path = .

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =

[logger_alembic]
level = INFO
handlers =

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

Create `backend/alembic/env.py`:

```python
from logging.config import fileConfig
from sqlalchemy import pool
from alembic import context
import asyncio
from app.config import settings
from app.models.base import Base
from app.models import user

config = context.config
fileConfig(config.config_file_name)
target_metadata = Base.metadata

def run_migrations_offline():
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    from sqlalchemy.ext.asyncio import create_async_engine
    connectable = create_async_engine(settings.database_url)
    async with connectable.connect() as connection:
        await connection.run_sync(lambda conn: context.configure(connection=conn, target_metadata=target_metadata))
        await connection.run_sync(lambda conn: context.run_migrations())
    await connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

Create `backend/alembic/versions/001_create_users.py`:

```python
"""create users table

Revision ID: 001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None

def upgrade():
    op.create_table('users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

def downgrade():
    op.drop_index('ix_users_email')
    op.drop_table('users')
```

Create `backend/alembic/script.py.mako`:

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}

def upgrade():
    ${upgrades if upgrades else "pass"}

def downgrade():
    ${downgrades if downgrades else "pass"}
```

### 14. Tests

Create `backend/tests/conftest.py`:

```python
import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from httpx import AsyncClient
from app.main import app
from app.database import get_db
from app.models.base import Base

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def test_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()

@pytest.fixture
async def client(test_db):
    app.dependency_overrides[get_db] = lambda: test_db
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

Create `backend/tests/unit/test_auth.py`:

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register(client):
    r = await client.post("/api/v1/auth/register", json={"email": "test@test.com", "password": "Test1234"})
    assert r.status_code == 201
    assert r.json()["email"] == "test@test.com"

@pytest.mark.asyncio
async def test_login(client):
    await client.post("/api/v1/auth/register", json={"email": "login@test.com", "password": "Test1234"})
    r = await client.post("/api/v1/auth/login", json={"email": "login@test.com", "password": "Test1234"})
    assert r.status_code == 200
    assert "access_token" in r.json()

@pytest.mark.asyncio
async def test_me(client):
    await client.post("/api/v1/auth/register", json={"email": "me@test.com", "password": "Test1234"})
    login = await client.post("/api/v1/auth/login", json={"email": "me@test.com", "password": "Test1234"})
    token = login.json()["access_token"]
    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
```

## Validation

Run these commands. ALL must pass:

```bash
cd backend

# 1. Run migration
alembic upgrade head

# 2. Run tests
pytest tests/unit/test_auth.py -v

# 3. Test API
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@test.com","password":"TestPass123"}'

curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@test.com","password":"TestPass123"}'
```

## Completion Criteria

**DO NOT PROCEED** unless:
- ✅ Migration runs
- ✅ All tests pass
- ✅ Can register/login via API
- ✅ CROSSCHECK.md Prompt 02 validated

Document in COMPLETION_LOG.md, then proceed to Prompt 03.
