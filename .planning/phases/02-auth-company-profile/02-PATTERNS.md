# Phase 2: Auth & Company Profile — Pattern Map

**Mapped:** 2026-05-29
**Files analyzed:** 18 new/modified files
**Analogs found:** 10 / 18 (8 have no codebase analog — use RESEARCH.md patterns)

---

## Codebase Analog Inventory

The project is an early scaffold. The concrete analogs that exist are:

| File | Role | Notes |
|------|------|-------|
| `backend/app/config.py` | config | Pydantic v2 SettingsConfigDict, singleton `settings` |
| `backend/app/db.py` | db foundation | async engine, async_sessionmaker, DeclarativeBase |
| `backend/app/main.py` | app factory | lifespan, `create_app()`, `include_router()` |
| `backend/app/routers/health.py` | router | APIRouter, single async GET, return dict |
| `backend/alembic/env.py` | migration config | async Alembic, URL from settings, `import app.models` |
| `backend/tests/conftest.py` | test fixture | ASGITransport + AsyncClient session-scoped fixture |
| `backend/tests/test_health.py` | integration test | `@pytest.mark.asyncio`, assert status + JSON body |
| `backend/spikes/spike_goszakup.py` | utility script | httpx async pattern, error handling, settings usage |

---

## File Classification

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---------------------|------|-----------|----------------|---------------|
| `backend/app/models/user.py` | model | CRUD | `backend/app/db.py` (Base) | partial — same Base, no model analog |
| `backend/app/models/company_profile.py` | model | CRUD | `backend/app/db.py` (Base) | partial — same Base, no model analog |
| `backend/app/models/__init__.py` | config | — | `backend/app/routers/__init__.py` | role-match (package init with exports) |
| `backend/app/schemas/auth.py` | schema | request-response | none | no analog |
| `backend/app/schemas/company.py` | schema | request-response | none | no analog |
| `backend/app/routers/auth.py` | router | request-response | `backend/app/routers/health.py` | role-match |
| `backend/app/routers/company.py` | router | CRUD | `backend/app/routers/health.py` | role-match |
| `backend/app/services/auth_service.py` | service | transform | none | no analog |
| `backend/app/services/company_service.py` | service | CRUD | none | no analog |
| `backend/app/services/email_service.py` | service | event-driven | none | no analog |
| `backend/app/deps.py` | middleware/dependency | request-response | `backend/app/db.py` (`get_db`) | partial — same dependency injection pattern |
| `backend/alembic/versions/<migration>.py` | migration | batch | `backend/alembic/env.py` | role-match |
| `frontend/src/middleware.ts` | middleware | request-response | none | no analog |
| `frontend/src/lib/api.ts` | utility | request-response | none | no analog |
| `frontend/src/store/authStore.ts` | store | event-driven | none | no analog |
| `frontend/src/app/(auth)/login/page.tsx` | component/page | request-response | `frontend/src/app/page.tsx` | partial — same Next.js page export shape |
| `frontend/src/app/(auth)/register/page.tsx` | component/page | request-response | `frontend/src/app/page.tsx` | partial |
| `frontend/src/app/(dashboard)/profile/page.tsx` | component/page | CRUD | `frontend/src/app/page.tsx` | partial |

---

## Pattern Assignments

### `backend/app/models/user.py` and `backend/app/models/company_profile.py` (model, CRUD)

**Analog:** `backend/app/db.py`

**Base import pattern** (db.py lines 1-11):
```python
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass
```

**Model pattern to copy** (from RESEARCH.md Pattern 2 — no codebase analog exists):
```python
from __future__ import annotations
from datetime import datetime
from typing import Optional

from sqlalchemy import String, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_verified: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    company_profile: Mapped[Optional["CompanyProfile"]] = relationship(
        back_populates="user", lazy="selectin", uselist=False
    )
```

**Critical constraint:** Always set `lazy="selectin"` on every relationship — default lazy loading raises `MissingGreenlet` in async SQLAlchemy. Never omit it.

---

### `backend/app/models/__init__.py` (package init)

**Analog:** `backend/app/routers/__init__.py` (empty file — same pattern)

**Required content** (explicit imports so Alembic autogenerate sees the tables):
```python
from app.models.user import User  # noqa: F401
from app.models.company_profile import CompanyProfile  # noqa: F401

__all__ = ["User", "CompanyProfile"]
```

**Why this matters:** `backend/alembic/env.py` line 15 does `import app.models` — if `__init__.py` is empty, autogenerate produces an empty migration (Pitfall 4 in RESEARCH.md).

---

### `backend/app/routers/auth.py` and `backend/app/routers/company.py` (router, request-response / CRUD)

**Analog:** `backend/app/routers/health.py`

**Router skeleton pattern** (health.py lines 1-8):
```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def health_check():
    return {"status": "ok", "service": "tenderit-api"}
```

**Expanded pattern for auth router** (add dependency injection and response model):
```python
from fastapi import APIRouter, Depends, Response, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse
from app.services import auth_service
from app.deps import get_current_user

router = APIRouter()


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    ...


@router.post("/login")
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    ...
```

**Registration in main.py** — copy the pattern from `backend/app/main.py` lines 21:
```python
application.include_router(health.router, prefix="/health", tags=["health"])
# New routers follow same pattern:
application.include_router(auth.router, prefix="/api/auth", tags=["auth"])
application.include_router(company.router, prefix="/api/company", tags=["company"])
```

---

### `backend/app/deps.py` (dependency, request-response)

**Analog:** `backend/app/db.py` — the `get_db` function (lines 24-27) establishes the FastAPI dependency injection pattern used across all routers:

```python
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

**`get_current_user` follows the same yield-dependency shape:**
```python
from fastapi import Depends, HTTPException, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from app.config import settings
from app.db import get_db
from app.models.user import User


async def get_current_user(
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(
            access_token, settings.secret_key, algorithms=["HS256"]
        )
        user_id = int(payload["sub"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user
```

**Critical constraint:** Always pass `algorithms=["HS256"]` to `jwt.decode()` — omitting it leaves the none-algorithm vulnerability open (Pitfall 2).

---

### `backend/app/services/auth_service.py` (service, transform)

**No codebase analog.** Use RESEARCH.md Pattern 1 and Pattern 5.

**Key excerpts from RESEARCH.md to copy directly:**

JWT token creation (Pattern 1):
```python
import jwt
from datetime import datetime, timedelta, timezone

from app.config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "exp": expire},
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def create_refresh_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": str(user_id), "exp": expire, "type": "refresh"},
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    secure = not settings.debug  # False in dev (no local HTTPS), True in prod
    response.set_cookie(
        "access_token", access_token,
        httponly=True, secure=secure, samesite="lax", max_age=900,
    )
    response.set_cookie(
        "refresh_token", refresh_token,
        httponly=True, secure=secure, samesite="lax", max_age=604800,
    )
```

Password hashing (pwdlib, no codebase analog):
```python
from pwdlib import PasswordHasher

hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    return hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return hasher.verify(plain, hashed)
```

---

### `backend/app/services/company_service.py` (service, CRUD)

**No codebase analog.** Contains BIN validation (pure function) and profile upsert.

**BIN validation** (RESEARCH.md Pattern 4 — copy verbatim):
```python
def validate_bin(bin_str: str) -> bool:
    """Validate Kazakhstan 12-digit BIN format and checksum."""
    if not bin_str or not bin_str.isdigit() or len(bin_str) != 12:
        return False
    # Position 5 (index 4) must be 4, 5, or 6 for legal entities (not IIN)
    if bin_str[4] not in ("4", "5", "6"):
        return False
    digits = [int(d) for d in bin_str]
    weights1 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    total = sum(d * w for d, w in zip(digits[:11], weights1))
    check = total % 11
    if check == 10:
        weights2 = [3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2]
        total2 = sum(d * w for d, w in zip(digits[:11], weights2))
        check = total2 % 11
        if check == 10:
            check = 0
    return check == digits[11]
```

Note: RESEARCH.md Pattern 4 omits the position-5 check. It is added here per Pitfall 5.

---

### `backend/app/services/email_service.py` (service, event-driven)

**No codebase analog.** Uses Resend SDK. Guard with `settings.debug` to skip actual send in dev:

```python
import resend
from app.config import settings


async def send_password_reset_email(to_email: str, reset_link: str) -> None:
    if settings.debug:
        # In dev: log the link instead of sending email (no Resend key required)
        print(f"[DEV] Password reset link for {to_email}: {reset_link}")
        return
    resend.api_key = settings.resend_api_key
    resend.Emails.send({
        "from": "noreply@tenderit.kz",
        "to": to_email,
        "subject": "Сброс пароля TenderIt",
        "html": f'<p>Перейдите по ссылке: <a href="{reset_link}">{reset_link}</a></p>',
    })
```

---

### `backend/app/config.py` (modified — add new settings fields)

**Analog:** `backend/app/config.py` (lines 1-21) — extend the existing Settings class, same pattern:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    database_url: str = "postgresql+asyncpg://tenderit:tenderit_dev@localhost:5432/tenderit"
    redis_url: str = "redis://localhost:6379"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin_dev"
    debug: bool = True
    # Existing field — rotate before staging deploy:
    secret_key: str = "change-me-in-production"
    # New fields for Phase 2:
    resend_api_key: str = ""
    frontend_url: str = "http://localhost:3000"


settings = Settings()
```

---

### `backend/alembic/versions/<migration>.py` (migration, batch)

**Analog:** `backend/alembic/env.py` — the env.py is already wired for async Alembic. Generate with:

```bash
cd backend && alembic revision --autogenerate -m "create_users_company_profiles"
```

The generated file will contain `upgrade()` / `downgrade()`. Verify it creates both `users` and `company_profiles` tables. If `upgrade()` is empty, `models/__init__.py` is not exporting the models (see models `__init__.py` section above).

---

### `frontend/src/middleware.ts` (middleware, request-response)

**No codebase analog.** Copy directly from RESEARCH.md Pattern 3:

```typescript
import { jwtVerify } from 'jose'
import { NextRequest, NextResponse } from 'next/server'

const SECRET = new TextEncoder().encode(process.env.JWT_SECRET!)
const protectedRoutes = ['/dashboard', '/profile', '/tenders']

export async function middleware(req: NextRequest) {
  const path = req.nextUrl.pathname
  const isProtected = protectedRoutes.some(r => path.startsWith(r))

  if (!isProtected) return NextResponse.next()

  const token = req.cookies.get('access_token')?.value
  if (!token) return NextResponse.redirect(new URL('/login', req.url))

  try {
    await jwtVerify(token, SECRET)
    return NextResponse.next()
  } catch {
    return NextResponse.redirect(new URL('/login', req.url))
  }
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)'],
}
```

**Critical constraint:** Use `jose`, never `jsonwebtoken`. The `jsonwebtoken` npm package uses Node.js crypto and crashes in the Edge Runtime where `middleware.ts` executes.

---

### `frontend/src/lib/api.ts` (utility, request-response)

**No codebase analog.** Typed fetch wrapper with 401 → silent refresh flow:

```typescript
const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: 'include',  // send httpOnly cookies cross-origin
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })

  if (res.status === 401) {
    // Attempt silent refresh
    const refreshed = await fetch(`${BASE}/api/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
    })
    if (!refreshed.ok) throw new Error('Session expired')
    // Retry original request once
    return apiFetch<T>(path, init)
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'API error')
  }

  return res.json() as Promise<T>
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path),
  post: <T>(path: string, body: unknown) =>
    apiFetch<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    apiFetch<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
}
```

---

### `frontend/src/store/authStore.ts` (store, event-driven)

**No codebase analog.** Zustand store — minimal surface, initialized from cookie presence:

```typescript
import { create } from 'zustand'

interface AuthState {
  isAuthenticated: boolean
  userId: number | null
  setAuth: (userId: number) => void
  clearAuth: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: false,
  userId: null,
  setAuth: (userId) => set({ isAuthenticated: true, userId }),
  clearAuth: () => set({ isAuthenticated: false, userId: null }),
}))
```

---

### `frontend/src/app/(auth)/login/page.tsx`, `register/page.tsx`, `forgot-password/page.tsx`, `reset-password/page.tsx` (component, request-response)

**Analog:** `frontend/src/app/page.tsx` — establishes the Next.js App Router default export page shape:

```typescript
export default function Home() {
  return (
    <div>...</div>
  )
}
```

**Auth pages follow this shape + RHF + zod** (RESEARCH.md Pattern 6):
```typescript
'use client'

import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { api } from '@/lib/api'

const loginSchema = z.object({
  email: z.string().email('Некорректный email'),
  password: z.string().min(8, 'Минимум 8 символов'),
})
type LoginFormValues = z.infer<typeof loginSchema>

export default function LoginPage() {
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  })

  const onSubmit = async (data: LoginFormValues) => {
    await api.post('/api/auth/login', data)
    // redirect to dashboard
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <input type="email" {...register('email')} />
      {errors.email && <p>{errors.email.message}</p>}
      <input type="password" {...register('password')} />
      {errors.password && <p>{errors.password.message}</p>}
      <button disabled={isSubmitting}>Войти</button>
    </form>
  )
}
```

**Note:** Auth pages use `'use client'` directive. The `(auth)` route group has no layout implications (no auth guard) — the middleware.ts handles redirection for logged-in users hitting login.

---

### `frontend/src/app/(dashboard)/profile/page.tsx` (component, CRUD)

**Analog:** Same Next.js page shape as auth pages above. Same RHF + zod pattern but with initial data load from `api.get('/api/company')` and a PUT on submit.

---

### `backend/tests/test_auth.py`, `test_profile.py`, `test_bin_validation.py` (test, request-response / unit)

**Analog:** `backend/tests/test_health.py` and `backend/tests/conftest.py`

**Test structure pattern** (test_health.py lines 1-8):
```python
import pytest


@pytest.mark.asyncio
async def test_health_returns_200(client):
    response = await client.get("/health/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

**Conftest fixture pattern** (conftest.py lines 1-12):
```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture(scope="session")
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
```

**Extended conftest needed for Phase 2** — add Redis mock and authenticated client fixtures following the same session-scoped yield pattern. BIN validation tests are pure unit tests (no `client` fixture, no `@pytest.mark.asyncio` needed):

```python
from app.services.company_service import validate_bin

def test_valid_bin():
    # Use a real KZ BIN with valid checksum
    assert validate_bin("123456789012") == ...  # planner must supply real test BINs

def test_invalid_bin_wrong_length():
    assert validate_bin("12345") is False

def test_invalid_bin_position5():
    # Position 5 is '1' — not a legal entity BIN
    assert validate_bin("190110100001") is False
```

---

## Shared Patterns

### Settings Access
**Source:** `backend/app/config.py` lines 1-21
**Apply to:** All backend files that need configuration (services, routers, deps)
```python
from app.config import settings
# Use: settings.secret_key, settings.redis_url, settings.debug, settings.resend_api_key
```

### Database Session Dependency
**Source:** `backend/app/db.py` lines 24-27
**Apply to:** All router handler functions that touch the database
```python
from app.db import get_db
# In route: db: AsyncSession = Depends(get_db)
```

### FastAPI Router Registration
**Source:** `backend/app/main.py` line 21
**Apply to:** `backend/app/main.py` when adding auth and company routers
```python
application.include_router(router_module.router, prefix="/api/auth", tags=["auth"])
```

### AsyncIO Test Decorator
**Source:** `backend/tests/test_health.py` line 4
**Apply to:** All async test functions in Phase 2
```python
@pytest.mark.asyncio
async def test_something(client):
    ...
```

### Error Response Shape
**Source:** `backend/app/routers/health.py` — health returns `{"status": "ok"}`. Auth errors should use FastAPI's `HTTPException` which produces `{"detail": "..."}`. Always raise `HTTPException`, never return raw dicts for error states. This keeps the response shape predictable for the frontend `api.ts` error handler.

---

## No Analog Found (use RESEARCH.md patterns exclusively)

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `backend/app/schemas/auth.py` | schema | request-response | No Pydantic schema files exist yet in the project |
| `backend/app/schemas/company.py` | schema | request-response | No Pydantic schema files exist yet in the project |
| `backend/app/services/auth_service.py` | service | transform | No service files with business logic exist yet |
| `backend/app/services/company_service.py` | service | CRUD | No service files with business logic exist yet |
| `backend/app/services/email_service.py` | service | event-driven | No service files exist; no email pattern in codebase |
| `frontend/src/middleware.ts` | middleware | request-response | No middleware.ts exists in frontend yet |
| `frontend/src/lib/api.ts` | utility | request-response | No lib/ directory exists in frontend yet |
| `frontend/src/store/authStore.ts` | store | event-driven | No stores/ directory exists in frontend yet |

---

## Metadata

**Analog search scope:** `backend/app/`, `backend/alembic/`, `backend/tests/`, `frontend/src/app/`
**Files scanned:** 12 backend Python files, 3 frontend TypeScript files
**Pattern extraction date:** 2026-05-29
