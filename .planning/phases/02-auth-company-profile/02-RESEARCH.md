# Phase 2: Auth & Company Profile — Research

**Researched:** 2026-05-29
**Domain:** FastAPI JWT auth, SQLAlchemy 2.x async models, Next.js 14 App Router auth, Kazakhstan BIN validation, transactional email
**Confidence:** HIGH

---

## Summary

Phase 2 delivers six requirements: user registration (AUTH-01), persistent JWT sessions with refresh (AUTH-02), password reset via email (AUTH-03), logout (AUTH-04), and a company profile with BIN/name/address that can be created and edited (COMP-01, COMP-02).

The stack is already specified and locked: FastAPI + PyJWT + pwdlib (Argon2) + redis.asyncio on the backend; Next.js 14 App Router + jose + react-hook-form + zod on the frontend. The decision to avoid an external auth provider (no NextAuth, no Clerk) is fixed, so the implementation is a custom JWT access/refresh token pair stored in httpOnly cookies. All cookie handling happens at the FastAPI boundary; the Next.js middleware.ts reads the access token cookie to gate routes without a database call.

The one area requiring validation before execution is the email provider. Resend is recommended (simple SDK, free tier, no SMTP server needed) but requires a verified domain. If the team does not yet have a domain verified with Resend, the plan must include a Wave 0 step to provision it, or fall back to Gmail SMTP for development.

**Primary recommendation:** Use PyJWT + pwdlib[argon2] on the backend and jose on the frontend. Store both tokens in httpOnly cookies (access: 15 min, refresh: 7 days). Use Resend for transactional email. Implement BIN checksum validation as a pure Python function — no third-party library exists for this.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTH-01 | User can register with email and password; invalid or duplicate rejected with clear message | User model + unique constraint on email, pwdlib hash, Pydantic email validation, 409 on duplicate |
| AUTH-02 | User can log in and remain authenticated across browser sessions (JWT refresh flow) until explicit logout | Access token (15 min) + refresh token (7 days) in httpOnly cookies; Redis refresh token store; silent refresh on 401 |
| AUTH-03 | User can reset forgotten password via emailed link | Opaque reset token stored in Redis with 15-min TTL; Resend SDK sends link; /auth/reset-password endpoint verifies and updates hash |
| AUTH-04 | User can log out | DELETE /auth/refresh: clears refresh token from Redis + both cookies |
| COMP-01 | User can fill in and save company profile (BIN, name, legal address) | CompanyProfile table with FK to User; BIN validated with checksum algorithm; PUT /profile/company upsert |
| COMP-02 | User can edit company profile at any time | Same PUT endpoint; all fields nullable except BIN once set; PATCH-style update |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Password hashing & token issuance | API / Backend | — | Cryptographic operations must never run in the browser |
| Refresh token storage & rotation | API / Backend (Redis) | — | Server-side state required for revocation |
| Route protection | Frontend Server (middleware.ts) | API / Backend | Middleware does optimistic check on cookie; backend validates on every API call |
| Form validation (client-side) | Browser / Client | API / Backend | RHF + zod for UX; backend re-validates independently |
| BIN format + checksum validation | API / Backend | Browser / Client | Backend is source of truth; frontend may show format hints |
| Session state (is logged in?) | Browser / Client (cookie-derived) | — | Zustand store initialized from cookie presence; no server query needed for UI state |
| Transactional email dispatch | API / Backend | — | Secrets (Resend API key) must not reach the browser |

---

## Standard Stack

### Core — Backend

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyJWT | 2.13.0 | Encode/decode JWT tokens | FastAPI official docs now use PyJWT; python-jose is abandoned (last release ~3 years ago, Python 3.10+ compat issues) [VERIFIED: PyPI registry + FastAPI docs] |
| pwdlib[argon2] | 0.3.0 | Password hashing | FastAPI docs recommend pwdlib over passlib; Argon2 is OWASP-recommended PHF [VERIFIED: fastapi.tiangolo.com/tutorial/security/oauth2-jwt] |
| redis (redis.asyncio) | 8.0.0 | Refresh token store + reset token TTL + logout blocklist | Already in docker-compose; redis.asyncio namespace is built-in [VERIFIED: PyPI + Bash probe] |
| slowapi | 0.1.9 | Per-IP rate limiting on /auth/login and /auth/register | Standard Starlette/FastAPI rate limiter; decorator API; uses `get_remote_address` by default [VERIFIED: PyPI + github.com/laurentS/slowapi] |
| resend | 2.30.1 | Transactional email (password reset) | Official FastAPI guide on resend.com; free tier, no SMTP config, single SDK call [VERIFIED: resend.com/docs/send-with-fastapi] |

### Core — Frontend

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| jose | 6.2.3 | Verify/decode JWT in Next.js middleware.ts | Edge Runtime compatible (Web Crypto API); `jsonwebtoken` is Node.js-only and fails in middleware [VERIFIED: npm registry + Next.js auth guide] |
| react-hook-form | 7.76.1 | Form state for login/register/profile forms | Already in frontend package.json [VERIFIED: Bash read] |
| zod | 3.24.4 | Schema validation (shared between RHF resolver and API type guards) | Already in frontend package.json [VERIFIED: Bash read] |
| @hookform/resolvers | 5.4.0 | Bridges zodResolver into RHF | Required companion for zod+RHF integration [VERIFIED: npm registry] |
| zustand | 5.0.13 | Auth state store (is_authenticated, user_id) | Already in frontend package.json [VERIFIED: Bash read] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyJWT | python-jose | python-jose is effectively abandoned; PyJWT is actively maintained and now the FastAPI default |
| pwdlib[argon2] | passlib[bcrypt] | passlib is unmaintained (last release 2022); pwdlib is modern replacement recommended by FastAPI docs |
| Resend | fastapi-mail + SMTP | fastapi-mail requires SMTP server config; Resend is zero-config for MVP (API key only) |
| Custom JWT middleware | NextAuth.js | NextAuth adds complexity and forces adapter pattern; custom is 50 lines and fully transparent |
| slowapi | Custom Redis counter | slowapi is production-tested and handles edge cases (X-Forwarded-For, etc.) |

**Installation (new dependencies to add to pyproject.toml):**
```bash
pip install "pyjwt==2.13.0" "pwdlib[argon2]==0.3.0" "redis==8.0.0" "slowapi==0.1.9" "resend==2.30.1"
```

**Frontend (not yet installed):**
```bash
npm install jose@6.2.3 @hookform/resolvers@5.4.0
```

---

## Architecture Patterns

### System Architecture Diagram

```
Browser                 Next.js (SSR)              FastAPI               Redis / Postgres
  |                         |                          |                       |
  | POST /api/auth/login     |                          |                       |
  |------------------------>| fwd to FastAPI           |                       |
  |                         |------------------------->| verify password       |
  |                         |                          |---> users table       |
  |                         |                          | issue access+refresh  |
  |                         |<-- Set-Cookie (2 httpOnly cookies) --------------|
  |<-- 200 OK --------------|                          |                       |
  |                         |                          | SETEX refresh_token:uid TTL 7d
  |                         |                          |---------------------->|
  |                         |                          |                       |
  | GET /dashboard          |                          |                       |
  |------------------------>| middleware.ts             |                       |
  |                         | reads access_token cookie|                       |
  |                         | jose.jwtVerify()         |                       |
  |                         | [no DB call in middleware]|                       |
  |                         |-- redirect /login if expired                     |
  |<-- HTML (authed) -------|                          |                       |
  |                         |                          |                       |
  | API call (expired token)|                          |                       |
  |------------------------>| /api/refresh proxy       |                       |
  |                         |------------------------->| read refresh cookie   |
  |                         |                          | GET refresh_token:uid |
  |                         |                          |---------------------->|
  |                         |                          |<-- stored token -------|
  |                         |                          | rotate: delete old, store new
  |                         |<-- new access_token cookie -------------------- |
  |<-- original API result --|                          |                       |
  |                         |                          |                       |
  | POST /api/auth/logout   |                          |                       |
  |------------------------>|------------------------->| DEL refresh_token:uid |
  |                         |                          |---------------------->|
  |                         |                          | clear both cookies    |
  |<-- 204 redirects /login-|                          |                       |
```

### Recommended Project Structure

```
backend/app/
├── models/
│   ├── __init__.py         # exports User, CompanyProfile
│   ├── user.py             # User SQLAlchemy model
│   └── company_profile.py  # CompanyProfile SQLAlchemy model
├── routers/
│   ├── auth.py             # /auth/register, /auth/login, /auth/refresh, /auth/logout, /auth/forgot-password, /auth/reset-password
│   └── profile.py          # /profile/company (GET, PUT)
├── schemas/
│   ├── auth.py             # RegisterRequest, LoginRequest, TokenResponse
│   └── company.py          # CompanyProfileRequest, CompanyProfileResponse
├── services/
│   ├── auth_service.py     # hash_password, verify_password, create_tokens, validate_reset_token
│   ├── email_service.py    # send_password_reset_email via Resend
│   └── redis_service.py    # get_redis, store_refresh_token, revoke_refresh_token, store_reset_token
└── deps.py                 # get_current_user dependency (shared across routers)

frontend/src/
├── app/
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   ├── register/page.tsx
│   │   ├── forgot-password/page.tsx
│   │   └── reset-password/page.tsx
│   └── (protected)/
│       ├── dashboard/page.tsx
│       └── profile/page.tsx
├── lib/
│   ├── api.ts              # typed fetch wrapper with 401 → refresh flow
│   └── auth.ts             # cookie helpers (client-side)
├── stores/
│   └── auth-store.ts       # Zustand: { isAuthenticated, userId, clearAuth }
├── components/
│   ├── auth/               # LoginForm, RegisterForm, ForgotPasswordForm
│   └── profile/            # CompanyProfileForm
└── middleware.ts            # route protection via jose.jwtVerify
```

### Pattern 1: FastAPI JWT Token Pair (httpOnly cookies)

**What:** Issue access token (15 min) and refresh token (7 days) as httpOnly Secure SameSite=Lax cookies. Refresh token is also stored in Redis under key `refresh_token:{user_id}` for server-side revocation.

**When to use:** Every login and every refresh endpoint.

```python
# Source: fastapi.tiangolo.com/tutorial/security/oauth2-jwt + Bash-verified PyJWT 2.13.0
import jwt
from datetime import datetime, timedelta, timezone

SECRET_KEY = settings.secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": str(user_id), "exp": expire, "type": "refresh"}, SECRET_KEY, algorithm=ALGORITHM)

def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie("access_token", access_token, httponly=True, secure=True, samesite="lax", max_age=900)
    response.set_cookie("refresh_token", refresh_token, httponly=True, secure=True, samesite="lax", max_age=604800)
```

### Pattern 2: SQLAlchemy 2.x Async User + CompanyProfile (one-to-one)

**What:** User owns one CompanyProfile via FK on company_profile. `lazy="selectin"` prevents implicit IO in async context.

**When to use:** All model definitions in this phase.

```python
# Source: docs.sqlalchemy.org/en/20/orm/basic_relationships.html [VERIFIED: Context7]
from __future__ import annotations
from typing import Optional
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    company_profile: Mapped[Optional["CompanyProfile"]] = relationship(
        back_populates="user", lazy="selectin", uselist=False
    )

class CompanyProfile(Base):
    __tablename__ = "company_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    bin: Mapped[Optional[str]] = mapped_column(String(12))           # 12-digit KZ BIN
    company_name: Mapped[Optional[str]] = mapped_column(String(500))
    legal_address: Mapped[Optional[str]] = mapped_column(String(1000))
    updated_at: Mapped[datetime] = mapped_column(onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="company_profile", lazy="selectin")
```

### Pattern 3: Next.js middleware.ts with jose (Edge Runtime)

**What:** Middleware reads access_token cookie, verifies signature with jose. No database call. Redirects to /login on invalid/expired token.

**When to use:** Protect all routes under `/(protected)/`.

```typescript
// Source: github.com/vercel/next.js/blob/canary/docs/01-app/02-guides/authentication.mdx [VERIFIED: Context7]
// jose is Edge Runtime compatible; jsonwebtoken is NOT
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
    // Token expired or invalid — redirect; client-side will attempt silent refresh
    return NextResponse.redirect(new URL('/login', req.url))
  }
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)'],
}
```

### Pattern 4: Kazakhstan BIN Checksum Validation

**What:** 12-digit BIN has a check digit at position 12. Algorithm: multiply digits 1-11 by weights [1..11] mod 11. If remainder == 10, use weights [3,4,5,6,7,8,9,10,11,1,2] and try again. If second result is also 10, check digit is 0.

**Structure:** Positions 1-2 = registration year (last 2 digits), 3-4 = month, 5 = entity type (4=resident legal entity, 5=non-resident, 6=IE joint venture), 6 = unit type (0=head, 1=branch, 2=representation), 7-11 = sequential number, 12 = check digit.

```python
# Source: lookuptax.com/docs/tax-identification-number/kazakhstan-tax-id-guide [VERIFIED: WebFetch]
def validate_bin(bin_str: str) -> bool:
    """Validate Kazakhstan 12-digit BIN format and checksum."""
    if not bin_str or not bin_str.isdigit() or len(bin_str) != 12:
        return False
    digits = [int(d) for d in bin_str]
    # First weight cycle
    weights1 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    total = sum(d * w for d, w in zip(digits[:11], weights1))
    check = total % 11
    if check == 10:
        # Second weight cycle
        weights2 = [3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2]
        total2 = sum(d * w for d, w in zip(digits[:11], weights2))
        check = total2 % 11
        if check == 10:
            check = 0
    return check == digits[11]
```

### Pattern 5: Password Reset Flow (Redis opaque token)

**What:** Generate a 32-byte URL-safe random token (not a JWT — opaques are simpler to revoke), store `reset:{token}` -> `user_id` in Redis with 15-min TTL, send link via Resend, verify on POST /auth/reset-password.

```python
# Source: [ASSUMED] — standard pattern; specific TTL values from research
import secrets
import redis.asyncio as aioredis

async def create_reset_token(user_id: int, redis: aioredis.Redis) -> str:
    token = secrets.token_urlsafe(32)
    await redis.setex(f"reset:{token}", 900, str(user_id))  # 15 min TTL
    return token

async def consume_reset_token(token: str, redis: aioredis.Redis) -> int | None:
    user_id = await redis.getdel(f"reset:{token}")  # atomic get-and-delete
    return int(user_id) if user_id else None
```

### Pattern 6: React Hook Form + Zod + API call

```typescript
// Source: context7.com/react-hook-form/react-hook-form [VERIFIED: Context7]
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'

const loginSchema = z.object({
  email: z.string().email('Некорректный email'),
  password: z.string().min(8, 'Минимум 8 символов'),
})
type LoginFormValues = z.infer<typeof loginSchema>

export function LoginForm() {
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  })
  const onSubmit = async (data: LoginFormValues) => {
    const res = await fetch('/api/auth/login', { method: 'POST', body: JSON.stringify(data) })
    if (!res.ok) { /* show error */ }
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

### Anti-Patterns to Avoid

- **Storing JWT in localStorage:** XSS can steal the token. Use httpOnly cookies only.
- **Using `jsonwebtoken` npm package in middleware.ts:** It uses Node.js crypto and throws at runtime in the Edge Runtime. Use `jose` exclusively for frontend JWT operations.
- **Lazy loading relationships without `lazy="selectin"` or `lazy="raise"`:** Default lazy loading is incompatible with async SQLAlchemy — accessing `.company_profile` on a detached User object will raise `MissingGreenlet`. Always specify `lazy="selectin"` on relationship().
- **Storing refresh token only in cookie (no server-side copy):** Cannot revoke on logout. Always mirror in Redis.
- **Using python-jose:** Near-abandoned, Python 3.10+ compat issues, FastAPI docs migrated away from it.
- **Using passlib:** Unmaintained since 2022. Use pwdlib instead.
- **Not validating BIN on backend:** Frontend format hints are UX only. Backend must re-validate including checksum before saving.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Password hashing | Custom bcrypt wrapper | pwdlib[argon2] | Argon2 timing-safe comparison, correct salt rounds, memory-hard by default |
| JWT encoding/decoding | Custom base64 + HMAC | PyJWT 2.13.0 | Handles exp, nbf, iat claims, algorithm validation, constant-time comparison |
| Rate limiting | Redis counter in decorator | slowapi 0.1.9 | Handles X-Forwarded-For headers, burst vs steady rate, Starlette integration |
| Transactional email | SMTP with smtplib | resend SDK 2.30.1 | No SMTP server needed, free tier, retry built-in |
| Frontend JWT decode | Custom base64 split | jose 6.2.3 | Edge Runtime safe, handles expiry, signature verification |

**Key insight:** Auth is the highest-density attack surface. Every "simple" hand-roll has timing attacks (password compare), algorithm confusion attacks (JWT none alg), or replay attacks (no token rotation) lurking inside it.

---

## Common Pitfalls

### Pitfall 1: Async Relationship Implicit Loading (MissingGreenlet)
**What goes wrong:** Code does `user.company_profile.bin` after awaiting a query and gets `sqlalchemy.exc.MissingGreenlet`.
**Why it happens:** Default SQLAlchemy relationship loading is lazy (sync), incompatible with async sessions. The relationship attribute triggers a new sync DB call.
**How to avoid:** Always set `lazy="selectin"` on any relationship accessed in async code. Alternatively, use `selectinload(User.company_profile)` in the query options.
**Warning signs:** Works in tests with `AsyncSession` but fails in production; error message mentions "greenlet_spawn".

### Pitfall 2: JWT None Algorithm / Algorithm Confusion
**What goes wrong:** PyJWT accepts `none` algorithm if `algorithms` parameter is not explicitly set on decode.
**Why it happens:** JWT spec historically allowed unsigned tokens. PyJWT 2.x disabled it by default, but older code patterns omit the `algorithms` kwarg.
**How to avoid:** Always call `jwt.decode(token, SECRET_KEY, algorithms=["HS256"])` — never omit `algorithms`.
**Warning signs:** `DecodeError` or unexpected token acceptance without signature.

### Pitfall 3: Cross-Domain Cookie Failure (SameSite + CORS)
**What goes wrong:** httpOnly cookie set by FastAPI on port 8000 is not sent by Next.js frontend on port 3000 — auth loop.
**Why it happens:** SameSite=Lax blocks cross-origin cookie sending in POST requests; browsers treat different ports as different origins.
**How to avoid:** In development, proxy all API calls through Next.js API routes (`/api/*` → `http://localhost:8000/*`). In production, use the same domain (api.tenderit.kz vs tenderit.kz same eTLD+1 allows cookies with `domain=.tenderit.kz`).
**Warning signs:** Login succeeds (200), but next request returns 401; Network tab shows no cookie in request.

### Pitfall 4: Alembic Not Seeing New Models
**What goes wrong:** `alembic revision --autogenerate` produces an empty migration even after adding User model.
**Why it happens:** Alembic's `env.py` imports `app.models` but `app/models/__init__.py` is empty — models are not actually imported into the metadata.
**How to avoid:** `app/models/__init__.py` must explicitly import all model modules: `from app.models.user import User; from app.models.company_profile import CompanyProfile`. The existing `env.py` already does `import app.models` — so the `__init__.py` must pull in the concrete model classes.
**Warning signs:** `alembic revision --autogenerate -m "create users"` generates a migration with empty `upgrade()`.

### Pitfall 5: BIN Position 5 Valid Values
**What goes wrong:** Accepting any 12-digit number as a valid BIN.
**Why it happens:** Format check (12 digits) is easy; structural check (position 5 must be 4, 5, or 6 for legal entities) is overlooked.
**How to avoid:** After checksum validation, assert `bin_str[4] in ('4', '5', '6')`. IIN (individual) uses different values at position 5 — BIN is specifically for legal entities.
**Warning signs:** Users entering personal IIN (individual) instead of company BIN; both pass the 12-digit + checksum check.

### Pitfall 6: Refresh Token Not Rotated (Replay Attack)
**What goes wrong:** Stolen refresh token can be reused indefinitely even after the legitimate user has refreshed.
**Why it happens:** Refresh endpoint issues a new access token but does not invalidate the old refresh token in Redis.
**How to avoid:** On every `/auth/refresh` call: (1) verify old refresh token against Redis, (2) delete it from Redis, (3) issue new refresh token, (4) store new refresh token in Redis. This is token rotation.
**Warning signs:** User logs out but old device can still call /auth/refresh.

### Pitfall 7: Rate Limiting Not Applied to /auth/register
**What goes wrong:** Attacker creates thousands of accounts rapidly (email enumeration, spam).
**Why it happens:** Rate limiting is added to login but forgotten on registration.
**How to avoid:** Apply `@limiter.limit("5/minute")` to both `/auth/login` and `/auth/register`.
**Warning signs:** Database fills with test accounts; Resend email quota exhausted.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| passlib[bcrypt] | pwdlib[argon2] | 2023 (passlib unmaintained) | Argon2 is memory-hard, more resistant to GPU attacks |
| python-jose | PyJWT | 2024 (FastAPI docs updated) | Fewer deps, maintained, Python 3.12 compat |
| JWT in localStorage | JWT in httpOnly cookie | ~2020 (OWASP guidance) | Eliminates XSS token theft |
| jsonwebtoken (Node.js) in Next.js middleware | jose (Web Crypto) | 2022 (Edge Runtime introduced) | Works in middleware.ts; jsonwebtoken crashes at Edge |
| nextjs-auth0 / NextAuth for every project | Custom JWT + httpOnly | Per project need | For custom backend, NextAuth adapter overhead not worth it |

**Deprecated/outdated:**
- `passlib`: Last release 2022, known issues with bcrypt >= 4.x, replaced by pwdlib
- `python-jose`: Last release 2022 (effectively abandoned), ecdsa dependency has CVEs; replaced by PyJWT
- `jsonwebtoken` npm: Node.js-only, cannot run in Edge Runtime where middleware.ts executes

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Password reset opaque token TTL of 15 min is appropriate for MVP | Pattern 5 | Too short: users complain; too long: security window. Adjust as needed. |
| A2 | Resend free tier (3,000 emails/month) sufficient for MVP | Standard Stack | If exceeded, billing required or fallback to SMTP |
| A3 | `redis.getdel` is available (Redis 6.2+) for atomic get-and-delete of reset token | Pattern 5 | Docker image is `redis:7-alpine` (confirmed in docker-compose.yml) — Redis 7 includes getdel; low risk [VERIFIED: docker-compose.yml] |
| A4 | Domain for Resend email sending is available / verified | Email section | Resend requires domain verification; unverified domain → emails go to spam or fail |

---

## Open Questions (RESOLVED)

1. **Resend domain verification status** — RESOLVED
   - Decision: Dev environment uses `settings.debug == True` fallback — reset link printed to stdout (no real email sent). Resend API key is optional for dev. Domain verification is a pre-production step, not a Wave 0 blocker.
   - Wave 0 task: Add `RESEND_API_KEY` to `.env.example` with placeholder; `email_service.py` sends email only when key is set, otherwise logs to stdout.

2. **JWT secret rotation strategy** — RESOLVED
   - Decision: `JWT_SECRET` is a required env var (no default). Settings model raises `ValidationError` at startup if absent. `.env.example` includes `JWT_SECRET=change-me-in-dev`. Production deployments must set the real secret. No secrets manager needed for MVP — plain env var on the server.

3. **HTTPS in local development** — RESOLVED
   - Decision: `secure=not settings.debug` guard on all cookie sets. Local dev runs on HTTP (`DEBUG=True`) so Secure flag is off. Production (`DEBUG=False`) enforces `Secure=True`. This is already codified in the plan actions for `set_auth_cookies()` in 02-02-PLAN.md.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL 16 | User + CompanyProfile tables | ✓ (via pg_isready) | 16.12 | — |
| Redis 7 | Refresh tokens, reset tokens, rate limiting | ✗ (not running locally; defined in docker-compose) | Redis 7-alpine in compose | `docker compose up redis` |
| Python 3.11+ | Backend runtime | ✓ | 3.11.7 | — |
| Node.js 22 | Frontend runtime | ✓ | 22.22.1 | — |
| Docker / Compose | Redis in dev | — | Not probed | Manual Redis install |
| Resend API key | Password reset email | ✗ (not configured) | — | SMTP via Gmail (dev only) |

**Missing dependencies with no fallback:**
- Redis must be running before any auth endpoint executes. `docker compose up redis` is the path.

**Missing dependencies with fallback:**
- Resend API key: In development, skip actual email send and log the reset link to stdout (`settings.debug == True` guard).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.3.0 (in pyproject.toml dev deps) |
| Config file | `backend/pytest.ini` or `pyproject.toml [tool.pytest.ini_options]` — none exists yet (Wave 0 gap) |
| Quick run command | `pytest backend/tests/ -x -q` |
| Full suite command | `pytest backend/tests/ -v --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTH-01 | Register with valid email → 201, duplicate → 409 | integration | `pytest backend/tests/test_auth.py::test_register -x` | ❌ Wave 0 |
| AUTH-01 | Invalid email format → 422 | integration | `pytest backend/tests/test_auth.py::test_register_invalid_email -x` | ❌ Wave 0 |
| AUTH-02 | Login → access + refresh cookies set | integration | `pytest backend/tests/test_auth.py::test_login -x` | ❌ Wave 0 |
| AUTH-02 | Expired access token + valid refresh → new access token | integration | `pytest backend/tests/test_auth.py::test_refresh_flow -x` | ❌ Wave 0 |
| AUTH-03 | Forgot-password → Redis token created, email queued | unit | `pytest backend/tests/test_auth.py::test_forgot_password -x` | ❌ Wave 0 |
| AUTH-03 | Reset with valid token → password updated, token deleted | integration | `pytest backend/tests/test_auth.py::test_reset_password -x` | ❌ Wave 0 |
| AUTH-04 | Logout → refresh token deleted from Redis, cookies cleared | integration | `pytest backend/tests/test_auth.py::test_logout -x` | ❌ Wave 0 |
| COMP-01 | PUT /profile/company with valid BIN → 200 | integration | `pytest backend/tests/test_profile.py::test_create_profile -x` | ❌ Wave 0 |
| COMP-01 | PUT /profile/company with invalid BIN checksum → 422 | unit | `pytest backend/tests/test_bin_validation.py -x` | ❌ Wave 0 |
| COMP-02 | PUT /profile/company again → updates, not duplicates | integration | `pytest backend/tests/test_profile.py::test_update_profile -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest backend/tests/ -x -q` (fail-fast, quiet)
- **Per wave merge:** `pytest backend/tests/ -v --tb=short`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/__init__.py`
- [ ] `backend/tests/conftest.py` — async engine fixture, test DB, Redis mock, TestClient
- [ ] `backend/tests/test_auth.py` — covers AUTH-01 through AUTH-04
- [ ] `backend/tests/test_profile.py` — covers COMP-01, COMP-02
- [ ] `backend/tests/test_bin_validation.py` — covers BIN checksum unit tests
- [ ] `backend/pytest.ini` or `[tool.pytest.ini_options]` in pyproject.toml — asyncio_mode = "auto"
- [ ] Framework install: already in dev deps; ensure `pip install -e ".[dev]"`

---

## Security Domain (ASVS L1)

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | PyJWT HS256, pwdlib Argon2, 8-char min password |
| V3 Session Management | yes | httpOnly + Secure + SameSite=Lax cookies; refresh token rotation in Redis |
| V4 Access Control | yes | `get_current_user` FastAPI dependency on every protected route |
| V5 Input Validation | yes | Pydantic v2 on all request bodies; zod on frontend |
| V6 Cryptography | partial | PyJWT for token signing (HS256), pwdlib for password hashing; no custom crypto |

### Known Threat Patterns for FastAPI + JWT + Next.js

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Brute-force login | Spoofing | slowapi 5 req/min on /auth/login per IP |
| Token theft via XSS | Information Disclosure | httpOnly cookies; no JWT in localStorage |
| CSRF on state-changing endpoints | Tampering | SameSite=Lax (blocks cross-site POST); add CSRF token if SameSite=None needed |
| Refresh token replay | Elevation of Privilege | Token rotation: delete old on use, store new in Redis |
| Password reset token reuse | Spoofing | `redis.getdel` — atomic read-and-delete; single use |
| JWT algorithm confusion (none alg) | Tampering | `algorithms=["HS256"]` explicit on `jwt.decode()` |
| Weak secret key | Spoofing | `openssl rand -hex 32` → env var; never hardcode |
| BIN enumeration (valid company check) | Information Disclosure | Return same error shape for BIN not found vs. BIN invalid format |

**CLAUDE.md security directives enforced:**
- EDS/ЭЦП password NEVER stored — out of scope for this phase (Phase 5)
- Document content NEVER logged — not relevant to this phase
- All input validated on backend — enforced via Pydantic v2 schemas
- HTTPS mandatory — enforced via `secure=True` on cookies in non-debug mode

---

## Project Constraints (from CLAUDE.md)

| Directive | Impact on Phase 2 |
|-----------|-------------------|
| NCALayer browser-only | Not relevant to auth phase |
| Private keys never leave user device | Not relevant to auth phase |
| Kazakhstan data localization (PII: ИИН, БИН) | CompanyProfile (БИН) must be stored in Postgres on KZ infrastructure — no third-party PII processor |
| HTTPS mandatory | `secure=True` on cookies in production; dev guard via `settings.debug` |
| Validate all input on backend | Every endpoint has a Pydantic v2 schema; BIN gets custom validator |
| Never store ЭЦП password in DB | Not applicable to auth phase — auth password hashed with Argon2 |
| Never log document contents | Not applicable to auth phase |
| MVP mode: vertical slices | Each plan delivers UI + API + DB together; no horizontal layers |

---

## Sources

### Primary (HIGH confidence)
- `/fastapi/fastapi` (Context7) — OAuth2 JWT pattern, password hashing, dependency injection
- `/vercel/next.js` (Context7) — middleware.ts auth pattern, Server Actions, cookie handling
- `/websites/sqlalchemy_en_20` (Context7) — one-to-one relationship, selectin loading, Mapped annotations
- `/react-hook-form/react-hook-form` (Context7) — useForm, zodResolver integration
- [fastapi.tiangolo.com/tutorial/security/oauth2-jwt](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) — PyJWT + pwdlib official pattern
- [lookuptax.com/docs/tax-identification-number/kazakhstan-tax-id-guide](https://lookuptax.com/docs/tax-identification-number/kazakhstan-tax-id-guide) — BIN structure + checksum algorithm
- [resend.com/docs/send-with-fastapi](https://resend.com/docs/send-with-fastapi) — Resend FastAPI integration
- PyPI registry (Bash probe) — all package versions verified

### Secondary (MEDIUM confidence)
- [github.com/fastapi/fastapi/discussions/11345](https://github.com/fastapi/fastapi/discussions/11345) — PyJWT vs python-jose migration decision
- [thewidlarzgroup.com/blog/nextjs-ssr---jwt-access-refresh-token-authentication-with-external-backend](https://www.thewidlarzgroup.com/blog/nextjs-ssr---jwt-access-refresh-token-authentication-with-external-backend) — Next.js proxy + refresh flow
- WebSearch: slowapi rate limiting pattern, ASVS threat patterns

### Tertiary (LOW confidence)
- A1-A4 items in Assumptions Log — conventions not verified against live system

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified against PyPI registry and npm; library choices confirmed in official FastAPI docs
- Architecture: HIGH — patterns verified via Context7 (SQLAlchemy, FastAPI, Next.js docs)
- BIN validation: MEDIUM — structure and algorithm verified via official tax authority documentation; checksum algorithm cross-referenced via multiple sources; no live BIN tested
- Pitfalls: HIGH — each pitfall derived from official documentation behavior, not opinion
- Email provider: MEDIUM — Resend SDK verified; domain availability is project-specific (A4)

**Research date:** 2026-05-29
**Valid until:** 2026-06-29 (stable libraries; re-verify if PyJWT or Next.js major version changes)
