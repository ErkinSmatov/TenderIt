---
plan: 02-03
phase: 02-auth-company-profile
status: complete
wave: 2
completed: 2026-06-09
subsystem: auth
tags: [jwt, refresh-tokens, redis, fastapi, nextjs, replay-protection, logout]
dependency_graph:
  requires:
    - 02-02  # register/login endpoints, redis_service, auth_service, get_current_user
  provides:
    - POST /api/auth/refresh — rotate refresh token, return new access+refresh cookies (204)
    - POST /api/auth/logout — revoke refresh token in Redis, clear cookies (204)
    - LogoutButton client component for dashboard
    - api.ts single-retry guard with clearAuth on terminal 401
  affects:
    - 02-04  # Company profile endpoints can rely on full auth lifecycle
tech_stack:
  added:
    - fakeredis>=2.0.0 (dev dependency for Redis isolation in tests)
  patterns:
    - Atomic refresh token rotation via Redis pipeline (DELETE + SETEX in one round-trip)
    - jti claim (secrets.token_hex(16)) in every JWT to prevent same-second token collision
    - FastAPI dependency injection for Redis in all auth endpoints (testable via overrides)
    - Function-scoped FakeRedis fixture to avoid cross-test event-loop binding errors
    - Logout: server-side revocation + client cookie deletion + Zustand store clear
    - api.ts didRetry flag prevents infinite 401 refresh loop (T-02-03-04 mitigation)
key_files:
  created:
    - backend/tests/test_auth_refresh_logout.py
    - frontend/src/components/auth/LogoutButton.tsx
  modified:
    - backend/app/services/redis_service.py
    - backend/app/services/auth_service.py
    - backend/app/routers/auth.py
    - backend/pyproject.toml
    - frontend/src/lib/api.ts
    - frontend/src/app/(dashboard)/layout.tsx
decisions:
  - "jti claim (random 16-byte hex) added to all tokens: prevents identical JWTs when two tokens are created within the same second (same exp, same sub) — without jti, the rotation test would fail because T1 == T2"
  - "FakeRedis fixture is function-scoped (not session-scoped): session-scoped FakeRedis instances are bound to the first event loop and trigger RuntimeError on subsequent per-test loops in pytest-asyncio"
  - "register/login endpoints refactored from inline get_redis() loop to redis=Depends(get_redis): enables dependency_overrides to inject FakeRedis in tests"
  - "clear_auth_cookies uses path='/' on delete_cookie to match the path set on creation"
  - "Refresh endpoint omits db dependency: user identity comes from the validated JWT sub claim, no DB lookup needed"
metrics:
  duration_minutes: 40
  tasks_completed: 2
  files_created: 2
  files_modified: 6
---

# Phase 02 Plan 03: Refresh Rotation, Logout, Frontend Wiring

**One-liner:** Atomic Redis pipeline token rotation with replay protection, server-side logout, and api.ts single-retry guard — completing AUTH-02 and AUTH-04.

## Endpoint Contracts

| Method | Path | Auth Required | Status | Cookies Set | Description |
|--------|------|---------------|--------|-------------|-------------|
| POST | /api/auth/refresh | refresh_token cookie | 204 | new access_token + refresh_token | Rotate refresh token |
| POST | /api/auth/refresh | missing/invalid cookie | 401 | — | "Сессия истекла" |
| POST | /api/auth/logout | access_token cookie (via get_current_user) | 204 | both cookies cleared | Revoke + clear |
| POST | /api/auth/logout | no auth cookie | 401 | — | Not authenticated |

Rate limit on `/refresh`: 20/minute per IP (more permissive than /login, browsers auto-refresh).

## Rotation Algorithm

```
POST /api/auth/refresh:
  1. Read refresh_token from httpOnly cookie
  2. jwt.decode(token, jwt_secret, algorithms=["HS256"])
     → ExpiredSignatureError / InvalidSignatureError → 401
  3. Assert payload["type"] == "refresh" → else 401
  4. user_id = int(payload["sub"])
  5. stored = await redis.get(f"refresh_token:{user_id}")
     → None or stored != token → 401 (replay protection)
  6. new_access = create_access_token(user_id)  # includes jti
     new_refresh = create_refresh_token(user_id)  # includes jti
  7. Redis pipeline:
       PIPE.DELETE refresh_token:{user_id}
       PIPE.SETEX  refresh_token:{user_id} 604800 new_refresh
       await PIPE.EXECUTE()   ← atomic, no window where both tokens are valid
  8. set_auth_cookies(response, new_access, new_refresh)
  9. return None  → FastAPI merges cookies into 204 response
```

## Replay Protection

Token `T1` is stored in Redis at login. When `/refresh` is called with `T1`:
- Redis contains `T1` → match → issue `T2`, atomically replace `T1` with `T2`
- Calling `/refresh` again with `T1` → Redis contains `T2` → `T1 != T2` → **401**

Verified by `test_refresh_with_replayed_old_token_returns_401`.

## Frontend Retry Guard

```typescript
// api.ts — prevents infinite recursion on persistent 401
async function apiFetch<T>(path, init?, didRetry = false): Promise<T> {
  const res = await fetch(...)
  if (res.status === 401) {
    if (didRetry) {
      useAuthStore.getState().clearAuth()
      throw new Error('Session expired')
    }
    const refreshed = await fetch('/api/auth/refresh', { method: 'POST', credentials: 'include' })
    if (!refreshed.ok) {
      useAuthStore.getState().clearAuth()
      throw new Error('Session expired')
    }
    return apiFetch(path, init, true)  // didRetry = true → no further recursion
  }
  ...
}
```

## LogoutButton Component

`frontend/src/components/auth/LogoutButton.tsx` — client component (`'use client'`):
1. `await api.post('/api/auth/logout', {})` — server revokes Redis key
2. `useAuthStore.getState().clearAuth()` — clear Zustand store (even if server call fails)
3. `router.push('/login')` — redirect

Rendered in `(dashboard)/layout.tsx` as a client island inside the server component header.

## Integration Test Coverage

| Test | Covers |
|------|--------|
| `test_refresh_success_rotates_tokens` | Happy path — new tokens differ, 204 |
| `test_refresh_with_replayed_old_token_returns_401` | T-02-03-01 replay protection |
| `test_refresh_without_cookie_returns_401` | Missing cookie guard |
| `test_refresh_with_expired_token_returns_401` | Expired JWT rejection |
| `test_refresh_with_access_token_in_refresh_cookie_returns_401` | T-02-03-02 type confusion |
| `test_logout_clears_redis_and_cookies` | T-02-03-03 server-side revocation |
| `test_logout_without_auth_returns_401` | Auth guard on logout |

Total: **7 tests** in `test_auth_refresh_logout.py` + **8 tests** in `test_auth_register_login.py` = **15 auth integration tests** in wave 1+2.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] JWT tokens identical within same second**
- **Found during:** Task 1, GREEN phase — `test_refresh_success_rotates_tokens` failed because new_access == old_access
- **Issue:** `create_access_token` and `create_refresh_token` produce deterministic output from `(user_id, exp_timestamp)` — two tokens created within the same second have identical payloads and thus identical signed values
- **Fix:** Added `"jti": secrets.token_hex(16)` claim to both `create_access_token` and `create_refresh_token` — each call now produces a cryptographically unique token
- **Files modified:** `backend/app/services/auth_service.py`
- **Commit:** 2b808fc

**2. [Rule 1 - Bug] Session-scoped FakeRedis causes event-loop binding error**
- **Found during:** Task 1, GREEN phase — 5 of 7 tests failed with `RuntimeError: <Queue...> is bound to a different event loop`
- **Issue:** pytest-asyncio creates a new event loop per test by default; a session-scoped `fakeredis.aioredis.FakeRedis` instance is bound to the first test's event loop and errors on subsequent tests
- **Fix:** Changed `fake_redis_instance` and `refresh_client` fixtures from `scope="session"` to function-scoped (`scope` omitted, default `function`). Each test gets its own FakeRedis instance with fresh state and the correct event loop
- **Files modified:** `backend/tests/test_auth_refresh_logout.py`
- **Commit:** 2b808fc

**3. [Rule 2 - DI Refactor] register/login endpoints used inline get_redis() loop**
- **Found during:** Task 1, test setup
- **Issue:** Original `register` and `login` handlers called `async for redis in get_redis()` directly, bypassing FastAPI's `dependency_overrides` mechanism. The `refresh_client` fixture injected FakeRedis via `app.dependency_overrides[get_redis]` but the register/login handlers still used real Redis
- **Fix:** Changed `register` and `login` to accept `redis=Depends(get_redis)`, consistent with the new `/refresh` and `/logout` endpoints. This makes all Redis usage in auth routes testable via dependency injection
- **Files modified:** `backend/app/routers/auth.py`
- **Commit:** 2b808fc

## Threat Mitigations Applied

| Threat ID | Mitigation | Verified |
|-----------|-----------|----------|
| T-02-03-01 | Atomic pipeline rotation; replay returns 401 | test_refresh_with_replayed_old_token_returns_401 ✅ |
| T-02-03-02 | payload.get("type") != "refresh" → 401 | test_refresh_with_access_token_in_refresh_cookie_returns_401 ✅ |
| T-02-03-03 | revoke_refresh_token deletes Redis key on logout | test_logout_clears_redis_and_cookies ✅ |
| T-02-03-04 | didRetry flag in apiFetch; second 401 throws terminal error | source check ✅ |
| T-02-03-05 | @limiter.limit("20/minute") on /refresh | source check ✅ |
| T-02-03-06 | Accept — MVP scope | N/A |

## Known Stubs

None — all functionality is fully wired.

## Commits

| Hash | Message | Task |
|------|---------|------|
| 0fdd851 | test(02-03): TDD RED — failing tests for /refresh and /logout endpoints | Task 1 RED |
| 2b808fc | feat(02-03): /refresh + /logout endpoints with Redis rotation and replay protection | Task 1 GREEN |
| (pending) | feat(02-03): LogoutButton client component + api.ts single-retry guard | Task 2 |

**Note:** Task 2 commit is pending — the Bash tool's sandbox policy blocked `git add` and `git commit` during the frontend commit step. All file changes for Task 2 are written to disk:
- `frontend/src/components/auth/LogoutButton.tsx` — new file
- `frontend/src/app/(dashboard)/layout.tsx` — updated
- `frontend/src/lib/api.ts` — updated

The orchestrator should run: `git add frontend/src/components/auth/LogoutButton.tsx "frontend/src/app/(dashboard)/layout.tsx" frontend/src/lib/api.ts && git commit -m "feat(02-03): LogoutButton client component + api.ts single-retry guard"`

## Self-Check: PARTIAL

Files created (spot check):
- backend/tests/test_auth_refresh_logout.py ✅
- backend/app/services/redis_service.py ✅ (rotate_refresh_token, get_refresh_token)
- backend/app/services/auth_service.py ✅ (clear_auth_cookies, jti in tokens)
- backend/app/routers/auth.py ✅ (/refresh, /logout routes)
- frontend/src/components/auth/LogoutButton.tsx ✅ (created on disk, uncommitted)
- frontend/src/lib/api.ts ✅ (modified on disk, uncommitted)
- frontend/src/app/(dashboard)/layout.tsx ✅ (modified on disk, uncommitted)

Test results: 7/7 passed (test_auth_refresh_logout.py), 26/26 passed (full test suite)

Commits:
- 0fdd851 test(02-03): TDD RED ✅
- 2b808fc feat(02-03): backend ✅
- Task 2 frontend commit: PENDING (sandbox write restriction)
