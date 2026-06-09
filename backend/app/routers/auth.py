from fastapi import APIRouter, Depends, HTTPException, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.services.auth_service import (
    create_access_token,
    create_refresh_token,
    hash_password,
    set_auth_cookies,
    verify_password,
)
from app.services.redis_service import get_redis, store_refresh_token

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()

# Single constant for both unknown email and wrong password — prevents user enumeration
_AUTH_ERROR = "Неверный email или пароль"


@router.post("/register", status_code=201, response_model=TokenResponse)
@limiter.limit("5/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    # Check for duplicate email
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Email уже зарегистрирован")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    set_auth_cookies(response, access_token, refresh_token)

    # Store refresh token in Redis
    async for redis in get_redis():
        await store_refresh_token(redis, user.id, refresh_token)

    return TokenResponse(user_id=user.id, email=user.email)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    # Use constant-time check regardless of whether user exists
    # (always verify a hash to equalise timing — Pitfall T-02-02-06)
    if user is None:
        # Run a dummy hash verify to equalise timing vs wrong-password path
        verify_password(body.password, hash_password("dummy_timing_equaliser"))
        raise HTTPException(status_code=401, detail=_AUTH_ERROR)

    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail=_AUTH_ERROR)

    if not user.is_active:
        raise HTTPException(status_code=401, detail=_AUTH_ERROR)

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    set_auth_cookies(response, access_token, refresh_token)

    # Store refresh token in Redis
    async for redis in get_redis():
        await store_refresh_token(redis, user.id, refresh_token)

    return TokenResponse(user_id=user.id, email=user.email)
