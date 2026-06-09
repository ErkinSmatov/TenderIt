---
plan: 02-02
phase: 02-auth-company-profile
status: complete
wave: 1
completed: 2026-06-09
subsystem: auth
tags: [jwt, auth, fastapi, nextjs, redis, slowapi, argon2]
dependency_graph:
  requires:
    - 02-01  # User model, settings.jwt_secret, test infra
  provides:
    - POST /api/auth/register — 201 + httpOnly cookies
    - POST /api/auth/login — 200 + httpOnly cookies
    - Frontend /login /register /dashboard routes
    - middleware.ts JWT gate
  affects:
    - 02-03  # Subsequent wave can use get_current_user dependency
    - 02-04  # Logout + refresh (extends auth router)
tech_stack:
  added: []
  patterns:
    - PyJWT HS256 access (15 min) + refresh (7 d) token pair in httpOnly cookies
    - pwdlib Argon2 password hashing via PasswordHash.recommended()
    - slowapi Limiter 5/min per IP on both /register and /login
    - redis SETEX refresh_token:{user_id} TTL 604800
    - NullPool SQLAlchemy engine in tests (prevents asyncpg event-loop teardown errors)
    - jose jwtVerify in middleware.ts (Edge Runtime compatible)
    - Zustand auth store (isAuthenticated, userId, setAuth, clearAuth)
    - RHF + zodResolver on auth forms
key_files:
  created:
    - backend/app/schemas/auth.py
    - backend/app/services/auth_service.py
    - backend/app/services/redis_service.py
    - backend/app/deps.py
    - backend/app/routers/auth.py
    - backend/tests/test_auth_register_login.py
    - frontend/src/middleware.ts
    - frontend/src/lib/api.ts
    - frontend/src/store/authStore.ts
    - frontend/src/app/(auth)/login/page.tsx
    - frontend/src/app/(auth)/register/page.tsx
    - frontend/src/app/(dashboard)/layout.tsx
    - frontend/src/app/(dashboard)/dashboard/page.tsx
    - frontend/.env.local.example
  modified:
    - backend/app/main.py
    - backend/tests/conftest.py
decisions:
  - "pwdlib.PasswordHash.recommended() used (not PasswordHasher — API differs from RESEARCH.md sample)"
  - "NullPool engine override in tests: session-scoped async fixtures + per-test event loops cause asyncpg background cleanup to fail; NullPool eliminates connection reuse and teardown tasks"
  - "auth_client and client fixtures are session-scoped; uuid-suffixed emails ensure test idempotency across runs against non-reset Postgres"
  - "reset_rate_limiter autouse fixture: slowapi in-memory counters bleed between tests; must reset before each test"
  - "_AUTH_ERROR constant shared across 3 raise sites in login: no-enumeration for unknown email + wrong password + inactive user"
  - "Dummy hash verify on unknown email path: equalises Argon2 timing for T-02-02-06 (email timing oracle)"
metrics:
  duration_minutes: 45
  tasks_completed: 2
  files_created: 14
  files_modified: 2
---

# Phase 02 Plan 02: Auth Vertical Slice — Register, Login, Protected Route

**One-liner:** JWT access+refresh httpOnly cookie auth with Argon2 hashing, 5/min rate limiting per IP, and jose-gated Next.js /dashboard route.

## Endpoint Contracts Implemented

| Method | Path | Status | Body | Cookies Set |
|--------|------|--------|------|-------------|
| POST | /api/auth/register | 201 | `{user_id, email}` | access_token (15 min) + refresh_token (7 d) |
| POST | /api/auth/register | 409 | `{detail: "Email уже зарегистрирован"}` | — |
| POST | /api/auth/register | 422 | Pydantic validation error | — |
| POST | /api/auth/register | 429 | Rate limit exceeded | — |
| POST | /api/auth/login | 200 | `{user_id, email}` | access_token (15 min) + refresh_token (7 d) |
| POST | /api/auth/login | 401 | `{detail: "Неверный email или пароль"}` | — |
| POST | /api/auth/login | 429 | Rate limit exceeded | — |

Cookie attributes: `httpOnly=True; Secure=<not debug>; SameSite=Lax`

## Redis Key Shape for Refresh Tokens

```
Key:   refresh_token:{user_id}   (e.g. refresh_token:42)
Value: raw JWT refresh token string
TTL:   604800 seconds (7 days)
```

Implemented in `backend/app/services/redis_service.py`:
- `store_refresh_token(redis, user_id, token)` → SETEX
- `revoke_refresh_token(redis, user_id)` → DEL (used by logout in wave 2)

## Rate Limit Configuration

| Endpoint | Limit | Backend | Key |
|----------|-------|---------|-----|
| POST /api/auth/register | 5/minute | slowapi in-memory | remote IP via get_remote_address |
| POST /api/auth/login | 5/minute | slowapi in-memory | remote IP via get_remote_address |

## Frontend Route Map

| Path | Component | Type | Guard |
|------|-----------|------|-------|
| /login | (auth)/login/page.tsx | Client | None (public) |
| /register | (auth)/register/page.tsx | Client | None (public) |
| /dashboard | (dashboard)/dashboard/page.tsx | Client | middleware.ts JWT check |
| /profile | — | — | middleware.ts JWT check |
| /tenders | — | — | middleware.ts JWT check |

Middleware matcher: `/((?!api|_next/static|_next/image|favicon.ico).*)` — covers all app routes.

## Deviations from PATTERNS.md

### Auto-fixed Issues

**1. [Rule 1 - Bug] pwdlib API mismatch**
- **Found during:** Task 1, GREEN phase
- **Issue:** RESEARCH.md and PATTERNS.md both reference `from pwdlib import PasswordHasher` — but installed pwdlib 0.3.0 exports `PasswordHash`, not `PasswordHasher`
- **Fix:** Changed to `from pwdlib import PasswordHash; hasher = PasswordHash.recommended()`
- **Files modified:** backend/app/services/auth_service.py
- **Commit:** aca61fd

**2. [Rule 2 - Missing Critical] NullPool engine for tests**
- **Found during:** Task 1, GREEN phase
- **Issue:** session-scoped async fixtures + pytest-asyncio per-test event loops caused asyncpg background cleanup tasks to hit `RuntimeError: Event loop is closed` — 3 out of 8 tests failed non-deterministically
- **Fix:** Added `use_nullpool_engine` session-scoped autouse fixture in conftest.py that replaces the global SQLAlchemy engine with a NullPool variant; added `reset_rate_limiter` autouse fixture; changed `auth_client` to session-scoped to share one asyncpg pool
- **Files modified:** backend/tests/conftest.py
- **Commit:** aca61fd

**3. [Rule 2 - Security] Timing equalisation on unknown email**
- **Found during:** Task 1, threat model review (T-02-02-06)
- **Issue:** Without running verify_password on unknown email path, login returns faster for non-existent users — timing oracle for email enumeration
- **Fix:** Added dummy hash verify on the unknown-email path in `login()` handler
- **Files modified:** backend/app/routers/auth.py
- **Commit:** aca61fd

## Threat Mitigations Applied

| Threat ID | Mitigation | Verified |
|-----------|-----------|----------|
| T-02-02-01 | slowapi @limiter.limit("5/minute") on /login | test_rate_limit_register_429 passes |
| T-02-02-02 | slowapi @limiter.limit("5/minute") on /register | same test |
| T-02-02-03 | algorithms=["HS256"] explicit in deps.py | grep check passes |
| T-02-02-04 | httpOnly=True on both cookies | set_cookie uses httponly=True |
| T-02-02-05 | samesite="lax"; CORS restricted to frontend_url | main.py CORSMiddleware |
| T-02-02-06 | Same _AUTH_ERROR for unknown email + wrong pwd; dummy hash timing | test_login_unknown_email_401_same_message |
| T-02-02-07 | jwt_secret from env var; .env.local.example has placeholder | .env files not committed |
| T-02-02-08 | min_length=8; Argon2id default cost | RegisterRequest.password Field(min_length=8) |

## Manual Smoke Test

Not executed (no running server in CI context). Recommended steps:
1. `docker compose up redis` + `cd backend && uvicorn app.main:app --reload`
2. `cd frontend && cp .env.local.example .env.local && npm run dev`
3. Open http://localhost:3000/register, fill form, submit
4. DevTools Network: verify Set-Cookie headers on 201 response
5. Browser navigates to /dashboard — verify cookie sent in Request Headers

## Known Stubs

- `/dashboard` shows `UserID: —` on page refresh (Zustand store is in-memory, not hydrated from cookie on load). This is expected for wave 1 — a `getUserFromCookie()` server component will wire this in wave 2 when the profile endpoint exists.
- Logout link `href="/api/auth/logout"` returns 404 until wave 2 (POST /api/auth/logout planned in 02-04).

## Self-Check: PASSED

Files created (spot check):
- backend/app/routers/auth.py ✓
- backend/app/schemas/auth.py ✓
- backend/app/services/auth_service.py ✓
- backend/app/services/redis_service.py ✓
- backend/app/deps.py ✓
- frontend/src/middleware.ts ✓
- frontend/src/lib/api.ts ✓
- frontend/src/store/authStore.ts ✓

Commits (spot check):
- 7098f42 test(02-02): TDD RED ✓
- aca61fd feat(02-02): backend auth ✓
- e9b4343 feat(02-02): frontend ✓

Test results: 8/8 passed (pytest), 0 TypeScript errors (next build)
