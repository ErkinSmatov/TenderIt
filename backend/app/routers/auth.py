import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.services.auth_service import (
    clear_auth_cookies,
    create_access_token,
    create_refresh_token,
    hash_password,
    set_auth_cookies,
    verify_password,
)
from app.services.email_service import send_password_reset_email
from app.services.redis_service import (
    consume_reset_token,
    create_reset_token,
    get_redis,
    get_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
    store_refresh_token,
)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()

# Single constant for both unknown email and wrong password — prevents user enumeration
_AUTH_ERROR = "Неверный email или пароль"
_SESSION_EXPIRED = "Сессия истекла"


@router.post("/register", status_code=201, response_model=TokenResponse)
@limiter.limit("5/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
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
    await store_refresh_token(redis, user.id, refresh_token)

    return TokenResponse(user_id=user.id, email=user.email)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
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
    await store_refresh_token(redis, user.id, refresh_token)

    return TokenResponse(user_id=user.id, email=user.email)


@router.post("/refresh", status_code=204)
@limiter.limit("20/minute")
async def refresh(
    request: Request,
    response: Response,
    redis=Depends(get_redis),
):
    """Issue a new access + refresh token pair, rotating the refresh token.

    - Reads the refresh_token httpOnly cookie.
    - Validates JWT signature, expiry, and type == "refresh".
    - Compares against the stored Redis value (replay protection).
    - Atomically replaces the stored token (pipeline delete + setex).
    - Sets new cookies and returns 204.
    """
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail=_SESSION_EXPIRED)

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail=_SESSION_EXPIRED)

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail=_SESSION_EXPIRED)

    user_id = int(payload["sub"])

    stored = await get_refresh_token(redis, user_id)
    if stored is None or stored != token:
        raise HTTPException(status_code=401, detail=_SESSION_EXPIRED)

    new_access = create_access_token(user_id)
    new_refresh = create_refresh_token(user_id)

    await rotate_refresh_token(redis, user_id, new_refresh)
    set_auth_cookies(response, new_access, new_refresh)
    # Return None — FastAPI merges cookies from injected `response` into the 204 response


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    user: User = Depends(get_current_user),
    redis=Depends(get_redis),
):
    """Revoke the refresh token in Redis and clear auth cookies. Returns 204."""
    await revoke_refresh_token(redis, user.id)
    clear_auth_cookies(response)
    # Return None — FastAPI merges cookies from injected `response` into the 204 response


@router.post("/forgot-password", status_code=202)
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """Trigger a password-reset email.

    Always returns 202 with the same body regardless of whether the email is
    registered — prevents user enumeration (T-02-04-02).
    """
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is not None:
        token = await create_reset_token(redis, user.id)
        link = f"{settings.frontend_url}/reset-password?token={token}"
        await send_password_reset_email(user.email, link)
    return {"message": "Если email зарегистрирован, ссылка отправлена"}


@router.post("/reset-password", status_code=204)
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """Consume a single-use reset token and update the user's password.

    The token is consumed atomically via GETDEL (T-02-04-01).
    Returns 204 on success; 400 if the token is invalid, expired, or already used.
    """
    user_id = await consume_reset_token(redis, body.token)
    if user_id is None:
        raise HTTPException(status_code=400, detail="Ссылка недействительна или истекла")

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="Ссылка недействительна или истекла")

    user.hashed_password = hash_password(body.new_password)
    await db.commit()
    return Response(status_code=204)

