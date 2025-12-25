from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.schemas.user_schema import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
    TokenRefresh,
)
from app.auth.password import hash_password, verify_password
from app.auth.jwt import create_access_token, create_refresh_token, decode_token
from app.auth.dependencies import get_current_user, security
from app.auth.blacklist import blacklist_token, is_token_blacklisted
from app.core.exceptions import InvalidCredentialsException, UserAlreadyExistsException
from app.core.rate_limiter import limiter
from app.config import settings
import secrets

router = APIRouter(tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise UserAlreadyExistsException()
    user = User(
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=hash_password(user_data.password)
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, credentials: UserLogin, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise InvalidCredentialsException()
    if not user.is_active:
        raise InvalidCredentialsException()
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        key="csrftoken",
        value=csrf_token,
        httponly=False,
        samesite="lax",
        secure=settings.is_production,
    )
    return TokenResponse(
        access_token=create_access_token({"sub": str(user.id), "csrf": csrf_token}),
        refresh_token=create_refresh_token({"sub": str(user.id), "csrf": csrf_token}),
        expires_in=1800
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh(request: Request, token_data: TokenRefresh, response: Response, db: AsyncSession = Depends(get_db)):
    try:
        if await is_token_blacklisted(token_data.refresh_token):
            raise HTTPException(status_code=401, detail="Token revoked")
        payload = decode_token(token_data.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = payload.get("sub")
        result = await db.execute(select(User).where(User.id == int(user_id)))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Invalid user")
        csrf_token = payload.get("csrf") or secrets.token_urlsafe(32)
        response.set_cookie(
            key="csrftoken",
            value=csrf_token,
            httponly=False,
            samesite="lax",
            secure=settings.is_production,
        )
        return TokenResponse(
            access_token=create_access_token({"sub": str(user.id), "csrf": csrf_token}),
            refresh_token=create_refresh_token({"sub": str(user.id), "csrf": csrf_token}),
            expires_in=1800
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return user


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    token_data: TokenRefresh | None = None
):
    # Blacklist both access token and optional refresh token
    await blacklist_token(credentials.credentials)
    if token_data and token_data.refresh_token:
        await blacklist_token(token_data.refresh_token)
    return {"message": "Logged out"}
