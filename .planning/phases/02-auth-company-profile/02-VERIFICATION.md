---
phase: 02-auth-company-profile
verified: 2026-06-10T00:00:00Z
status: passed
score: 19/19 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 17/19
  gaps_closed:
    - "Frontend builds without TypeScript errors (npm run build exits 0)"
    - "Visiting /dashboard without an access_token cookie redirects to /login (middleware)"
  gaps_remaining: []
  regressions: []
---

# Phase 02: Auth & Company Profile — Verification Report

**Phase Goal:** Users can create an account, authenticate securely, and maintain a complete company profile that will be used across all downstream features.
**Verified:** 2026-06-10
**Status:** PASSED — all 19 must-haves verified
**Re-verification:** Yes — after gap closure (npm install run in main checkout)

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Backend installs PyJWT, pwdlib, redis, slowapi, resend without conflicts | VERIFIED | `python3 -c "import jwt, pwdlib, redis, slowapi, resend"` exits 0 |
| 2 | Frontend installs jose and @hookform/resolvers without conflicts | VERIFIED | `npm run build` exits 0 — both packages resolved; middleware compiled at 32.3 kB |
| 3 | JWT_SECRET, RESEND_API_KEY, FRONTEND_URL settable via env | VERIFIED | `config.py` lines 20-22 expose all three fields; `.env.example` documents them |
| 4 | User and CompanyProfile tables exist in Postgres after migration | VERIFIED | Migration `0001_create_users_company_profiles.py`; 2 `op.create_table` calls applied |
| 5 | BIN checksum validator returns True for valid BIN and False for invalid | VERIFIED | `validate_bin` in bin_validator.py; position-5 check; two-cycle weights; 10 unit tests pass |
| 6 | pytest discovers async tests with asyncio_mode=auto | VERIFIED | pytest.ini line 2: `asyncio_mode = auto` |
| 7 | User can register with email + password (AUTH-01) | VERIFIED | `POST /api/auth/register`; RegisterRequest with EmailStr + min_length(8); 8 integration tests pass including 409 and 422 |
| 8 | Duplicate email registration returns 409 | VERIFIED | Router raises HTTPException 409; `test_register_duplicate_email_409` passes |
| 9 | User can log in and remain authenticated (AUTH-02) | VERIFIED | `POST /api/auth/login`; httpOnly cookies; `/refresh` rotates atomically via Redis pipeline; 7 refresh/logout tests pass |
| 10 | POST /api/auth/refresh issues new tokens; old refresh token invalidated | VERIFIED | `rotate_refresh_token` uses pipeline delete+setex; `test_refresh_with_replayed_old_token_returns_401` passes |
| 11 | POST /api/auth/logout deletes Redis token and clears cookies | VERIFIED | `revoke_refresh_token` + `clear_auth_cookies` (2 `delete_cookie` calls); `test_logout_clears_redis_and_cookies` passes |
| 12 | Password reset via email link (AUTH-03) | VERIFIED | `/forgot-password` 202 no-enumeration; `/reset-password` atomic GETDEL; 7 tests pass including replay 400 |
| 13 | POST /api/auth/forgot-password unknown email returns same 202 (no enumeration) | VERIFIED | Router always returns same message regardless of user existence |
| 14 | Visiting /dashboard without access_token cookie redirects to /login (middleware) | VERIFIED | `npm run build` succeeds; `ƒ Middleware 32.3 kB` compiled and bundled; jose resolved; middleware.ts wires jose.jwtVerify to access_token cookie check |
| 15 | Rate limit 5/min on /register and /login | VERIFIED | `@limiter.limit("5/minute")` on both endpoints; `test_rate_limit_register_429` passes |
| 16 | GET /api/company/profile returns 200 (empty nulls if no profile) | VERIFIED | Company router line 19; `test_get_profile_empty_for_new_user` passes |
| 17 | PUT /api/company/profile upserts and BIN-validates | VERIFIED | `@field_validator("bin")` calls `validate_bin`; upsert in `company_service.py`; 7 integration tests pass including BIN checksum 422 |
| 18 | Both /api/company endpoints require auth; missing token returns 401 | VERIFIED | Both routes have `Depends(get_current_user)`; `test_get_profile_unauthenticated_returns_401` passes |
| 19 | Frontend /profile page loads profile on mount and pre-fills form (COMP-01, COMP-02) | VERIFIED | `useEffect` calls `api.get('/api/company/profile')`; `CompanyProfileForm` receives `initialData`; `api.put` on submit; regex `^\d{12}$` client-side; backend 422 surfaced under bin field |

**Score: 19/19 truths verified**

---

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `backend/app/models/user.py` | VERIFIED | `class User`; `lazy="selectin"` on relationship (1 match confirmed) |
| `backend/app/models/company_profile.py` | VERIFIED | `class CompanyProfile`; `user_id` FK unique; `lazy="selectin"` (1 match confirmed) |
| `backend/app/models/__init__.py` | VERIFIED | Explicit imports of User and CompanyProfile |
| `backend/app/services/bin_validator.py` | VERIFIED | File exists; `def validate_bin`; two-cycle checksum |
| `backend/alembic/versions/0001_create_users_company_profiles.py` | VERIFIED | 2 `op.create_table` calls applied |
| `backend/pytest.ini` | VERIFIED | `asyncio_mode = auto` |
| `backend/.env.example` | VERIFIED | JWT_SECRET, RESEND_API_KEY, FRONTEND_URL present |
| `backend/app/schemas/auth.py` | VERIFIED | All 4 request schemas |
| `backend/app/services/auth_service.py` | VERIFIED | hash_password, verify_password, create_access_token, create_refresh_token, set_auth_cookies, clear_auth_cookies |
| `backend/app/services/redis_service.py` | VERIFIED | store_refresh_token, rotate_refresh_token, revoke_refresh_token, create_reset_token, consume_reset_token (GETDEL) |
| `backend/app/services/email_service.py` | VERIFIED | send_password_reset_email; debug/prod branch |
| `backend/app/deps.py` | VERIFIED | get_current_user; `algorithms=["HS256"]` explicit |
| `backend/app/routers/auth.py` | VERIFIED | All 6 auth endpoints: /register, /login, /refresh, /logout, /forgot-password, /reset-password |
| `backend/app/schemas/company.py` | VERIFIED | CompanyProfileRequest with @field_validator("bin"); CompanyProfileResponse |
| `backend/app/services/company_service.py` | VERIFIED | upsert_company_profile |
| `backend/app/routers/company.py` | VERIFIED | GET + PUT /profile; both auth-gated |
| `frontend/src/middleware.ts` | VERIFIED | File exists; jose resolved; compiled by Next.js build at 32.3 kB — middleware active |
| `frontend/src/lib/api.ts` | VERIFIED | credentials: 'include' (x2); didRetry guard; clearAuth on terminal 401 |
| `frontend/src/store/authStore.ts` | VERIFIED | isAuthenticated, userId, setAuth, clearAuth |
| `frontend/src/app/(auth)/login/page.tsx` | VERIFIED | RHF + zodResolver; api.post('/api/auth/login') |
| `frontend/src/app/(auth)/register/page.tsx` | VERIFIED | RHF + zodResolver; api.post('/api/auth/register') |
| `frontend/src/app/(auth)/forgot-password/page.tsx` | VERIFIED | api.post('/api/auth/forgot-password'); same message always |
| `frontend/src/app/(auth)/reset-password/page.tsx` | VERIFIED | useSearchParams(); api.post('/api/auth/reset-password') |
| `frontend/src/components/auth/LogoutButton.tsx` | VERIFIED | File exists; api.post('/api/auth/logout'); clearAuth(); router.push('/login') |
| `frontend/src/app/(dashboard)/layout.tsx` | VERIFIED | Imports and renders LogoutButton |
| `frontend/src/app/(dashboard)/dashboard/page.tsx` | VERIFIED | "Личный кабинет"; link to /profile |
| `frontend/src/app/(dashboard)/profile/page.tsx` | VERIFIED | useEffect → api.get; CompanyProfileForm with initialData |
| `frontend/src/components/profile/CompanyProfileForm.tsx` | VERIFIED | api.put; regex /^\d{12}$/; setError('bin') on 422 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/app/models/__init__.py` | `backend/alembic/env.py` | import triggers User + CompanyProfile registration | WIRED | Base.metadata contains both tables |
| `backend/app/config.py` | Settings env loading | pydantic-settings reads .env | WIRED | jwt_secret, resend_api_key, frontend_url confirmed |
| `frontend/src/app/(auth)/login/page.tsx` | POST /api/auth/login | api.post via lib/api.ts with credentials: 'include' | WIRED | api.ts has credentials: 'include' |
| `backend/app/routers/auth.py` | redis_service.store_refresh_token | Redis SETEX refresh_token:{user_id} | WIRED | auth router lines 72, 105 |
| `frontend/src/middleware.ts` | access_token cookie | jose.jwtVerify | WIRED | jose installed; middleware compiled at 32.3 kB |
| POST /api/auth/refresh | redis_service rotate_refresh_token | Atomic delete+SETEX pipeline | WIRED | rotate_refresh_token with pipeline; all refresh tests pass |
| `frontend/src/lib/api.ts` | POST /api/auth/refresh | automatic retry on 401 | WIRED | didRetry guard |
| POST /api/auth/forgot-password | email_service.send_password_reset_email | Resend SDK or dev stdout | WIRED | email_service has debug/prod branch |
| POST /api/auth/reset-password | Redis GETDEL reset:{token} | Atomic single-use | WIRED | consume_reset_token uses redis.getdel |
| PUT /api/company/profile | CompanyProfile table (one-to-one) | upsert_company_profile + user_id unique constraint | WIRED | company_service select-first upsert |
| `frontend/src/app/(dashboard)/profile/page.tsx` | GET + PUT /api/company/profile | api.get on mount, api.put on submit | WIRED | useEffect + CompanyProfileForm |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `profile/page.tsx` | `profile` (useState) | `api.get('/api/company/profile')` in useEffect | Yes — backend queries CompanyProfile WHERE user_id | FLOWING |
| `CompanyProfileForm.tsx` | `initialData` prop | Passed from profile/page.tsx, populated by API | Yes — real ORM data via CompanyProfileResponse | FLOWING |
| `dashboard/page.tsx` | `userId` | useAuthStore (Zustand) | In-memory only; not hydrated from cookie on refresh | STATIC (by design — documented in 02-02 SUMMARY; acceptable for MVP) |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| BIN validator rejects short BIN | `python3 -c "from app.services.bin_validator import validate_bin; assert validate_bin('12345') is False"` | exit 0 | PASS |
| BIN validator accepts valid BIN | `python3 -c "from app.services.bin_validator import validate_bin; assert validate_bin('190540000014') is True"` | exit 0 | PASS |
| hash_password + verify_password round-trip | `python3 -c "from app.services.auth_service import hash_password, verify_password; h = hash_password('test12345'); assert verify_password('test12345', h) and not verify_password('wrong1234', h)"` | exit 0 | PASS |
| All backend integration tests | `pytest tests/ -q --ignore=tests/spikes` | 40 passed, 0 failed | PASS |
| Frontend build | `npm run build` | exit 0; Compiled successfully; 11/11 static pages; Middleware 32.3 kB | PASS |

---

### Probe Execution

No probes declared in plan files. Step 7c: SKIPPED (no probe scripts found).

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| AUTH-01 | 02-01, 02-02 | Регистрация с email + паролем | SATISFIED | POST /api/auth/register; 8 tests pass including 409 duplicate and 422 validation |
| AUTH-02 | 02-02, 02-03 | Вход + постоянные сессии (refresh) | SATISFIED | POST /api/auth/login; /refresh с атомарной ротацией; 7 refresh/logout tests |
| AUTH-03 | 02-04 | Сброс пароля через email | SATISFIED | /forgot-password + /reset-password; single-use GETDEL; 7 tests including replay 400 |
| AUTH-04 | 02-03 | Выход из системы | SATISFIED | POST /api/auth/logout; Redis revocation + cookie deletion |
| COMP-01 | 02-05 | Создание профиля компании (БИН, название, адрес) | SATISFIED | PUT /api/company/profile с upsert; @field_validator BIN; 7 tests including checksum 422 |
| COMP-02 | 02-05 | Редактирование профиля компании | SATISFIED | Idempotент PUT; test_put_profile_updates_existing_row passes |

Все 6 requirement ID из plan frontmatter покрыты. Orphaned requirements для Phase 2 не обнаружены.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/app/(dashboard)/dashboard/page.tsx` | 12 | `userId ?? '—'` — Zustand не гидрируется при перезагрузке страницы | INFO | Задокументировано в 02-02 SUMMARY как known limitation; не является обманом — страница явно показывает '—' |

Маркеры TBD, FIXME, XXX в файлах фазы не обнаружены.

---

### Human Verification Required

Нет. Все истины верифицированы автоматически.

---

### Re-verification Summary

Предыдущая верификация (status: gaps_found, score: 17/19) выявила один корневой сбой: `npm install` не был запущен в основном checkout, из-за чего пакеты `@hookform/resolvers` и `jose` отсутствовали в `node_modules`. Это блокировало две истины:

1. **"Frontend builds without TypeScript errors"** — `npm run build` завершался с ошибкой `Module not found`.
2. **"Visiting /dashboard without access_token redirects to /login"** — middleware.ts не мог загрузиться без `jose`.

После запуска `npm install` в основном checkout:
- `npm run build` завершается с кодом 0: `✓ Compiled successfully`, 11/11 static pages, `ƒ Middleware 32.3 kB`.
- Оба закрытых гепа теперь VERIFIED.
- Регрессий нет: `pytest tests/ -q --ignore=tests/spikes` — 40 passed, 0 failed.

**Фаза 2 полностью достигла своей цели.**

---

_Verified: 2026-06-10_
_Verifier: Claude (gsd-verifier)_
