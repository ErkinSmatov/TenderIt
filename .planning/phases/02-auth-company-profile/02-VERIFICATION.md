---
phase: 02-auth-company-profile
verified: 2026-06-10T00:00:00Z
status: gaps_found
score: 17/19 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Frontend builds without TypeScript errors (npm run build exits 0)"
    status: failed
    reason: "node_modules is incomplete — @hookform/resolvers and jose are declared in package.json but not installed. Build fails with 'Module not found: Can't resolve @hookform-resolvers/zod' on register/page.tsx, reset-password/page.tsx, and CompanyProfileForm.tsx"
    artifacts:
      - path: "frontend/node_modules/@hookform"
        issue: "Directory missing — @hookform/resolvers@^5.4.0 not installed"
      - path: "frontend/node_modules/jose"
        issue: "Directory missing — jose@^6.2.3 not installed"
    missing:
      - "Run `npm install` in frontend/ to materialise packages from package.json into node_modules"
  - truth: "Visiting /dashboard without an access_token cookie redirects to /login (middleware)"
    status: failed
    reason: "middleware.ts uses `from 'jose'` which is not installed. If jose is not in node_modules the Edge runtime cannot load middleware, making the JWT protection gate non-functional at build/deploy time. This is the same root cause as the build failure."
    artifacts:
      - path: "frontend/src/middleware.ts"
        issue: "Imports from 'jose' — package not installed in node_modules"
    missing:
      - "Run `npm install` in frontend/ — this resolves both the build failure and the middleware gap simultaneously"
---

# Phase 02: Auth & Company Profile — Verification Report

**Phase Goal:** Users can create an account, authenticate securely, and maintain a complete company profile that will be used across all downstream features.
**Verified:** 2026-06-10
**Status:** GAPS FOUND — 1 root-cause failure (missing npm install) blocks 2 truths
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Backend installs PyJWT, pwdlib, redis, slowapi, resend without conflicts | VERIFIED | `python3 -c "import jwt, pwdlib, redis, slowapi, resend"` exits 0 |
| 2 | Frontend installs jose and @hookform/resolvers without conflicts | FAILED | Both packages missing from node_modules; package.json declares them but `npm install` was not run in the working tree |
| 3 | JWT_SECRET, RESEND_API_KEY, FRONTEND_URL settable via env | VERIFIED | `config.py` lines 20-22 expose all three fields; `.env.example` lines 11-13 document them |
| 4 | User and CompanyProfile tables exist in Postgres after migration | VERIFIED | Migration file `0001_create_users_company_profiles.py` exists with 2 `op.create_table` calls; `Base.metadata.tables` contains `['company_profiles', 'users']` |
| 5 | BIN checksum validator returns True for valid BIN and False for invalid | VERIFIED | `validate_bin` at line 15 of bin_validator.py; position-5 check at line 26; two-cycle weights at lines 30-36; 10 unit tests pass |
| 6 | pytest discovers async tests with asyncio_mode=auto | VERIFIED | pytest.ini line 2: `asyncio_mode = auto` |
| 7 | User can register with email + password (AUTH-01) | VERIFIED | `POST /api/auth/register` at router line 47; RegisterRequest with EmailStr + min_length(8); 8 integration tests pass including duplicate 409 and validation 422 |
| 8 | Duplicate email registration returns 409 | VERIFIED | Router raises HTTPException 409 on existing user; `test_register_duplicate_email_409` passes |
| 9 | User can log in and remain authenticated (AUTH-02) | VERIFIED | `POST /api/auth/login`; httpOnly cookies set; `/refresh` rotates atomically via Redis pipeline; 7 refresh/logout tests pass |
| 10 | POST /api/auth/refresh issues new tokens; old refresh token invalidated | VERIFIED | `rotate_refresh_token` uses pipeline delete+setex; `test_refresh_with_replayed_old_token_returns_401` passes |
| 11 | POST /api/auth/logout deletes Redis token and clears cookies | VERIFIED | `revoke_refresh_token` + `clear_auth_cookies` (2 `delete_cookie` calls); `test_logout_clears_redis_and_cookies` passes |
| 12 | Password reset via email link (AUTH-03) | VERIFIED | `/forgot-password` 202 no-enumeration; `/reset-password` atomic GETDEL; 7 tests pass including replay 400 |
| 13 | POST /api/auth/forgot-password unknown email returns same 202 (no enumeration) | VERIFIED | Router always returns `"Если email зарегистрирован, ссылка отправлена"` regardless of user existence |
| 14 | Visiting /dashboard without access_token cookie redirects to /login (middleware) | FAILED | middleware.ts implementation is correct (lines 1-17 verified), but `jose` is not in node_modules — middleware cannot load at build/deploy time |
| 15 | Rate limit 5/min on /register and /login | VERIFIED | `@limiter.limit("5/minute")` on both endpoints (router lines 48, 78); `test_rate_limit_register_429` passes |
| 16 | GET /api/company/profile returns 200 (empty nulls if no profile) | VERIFIED | Company router line 19; `test_get_profile_empty_for_new_user` passes; all-null CompanyProfileResponse returned |
| 17 | PUT /api/company/profile upserts and BIN-validates | VERIFIED | `@field_validator("bin")` calls `validate_bin`; upsert in `company_service.py`; 7 integration tests pass including BIN checksum 422 and idempotent update |
| 18 | Both /api/company endpoints require auth; missing token returns 401 | VERIFIED | Both routes have `Depends(get_current_user)` (company.py lines 21, 40); `test_get_profile_unauthenticated_returns_401` passes |
| 19 | Frontend /profile page loads profile on mount and pre-fills form (COMP-01, COMP-02) | VERIFIED | `useEffect` calls `api.get('/api/company/profile')` (profile/page.tsx line 21); `CompanyProfileForm` receives `initialData`; `api.put` on submit; regex `^\d{12}$` client-side; backend 422 surfaced under bin field |

**Score: 17/19 truths verified**

---

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `backend/app/models/user.py` | VERIFIED | `class User` with all required columns; `lazy="selectin"` on relationship |
| `backend/app/models/company_profile.py` | VERIFIED | `class CompanyProfile`; `user_id` FK unique; `lazy="selectin"` |
| `backend/app/models/__init__.py` | VERIFIED | Explicit imports of User and CompanyProfile; Alembic autogenerate works |
| `backend/app/services/bin_validator.py` | VERIFIED | `def validate_bin`; position-5 check; two-cycle checksum |
| `backend/alembic/versions/0001_create_users_company_profiles.py` | VERIFIED | 2 `op.create_table` calls; applied |
| `backend/pytest.ini` | VERIFIED | `asyncio_mode = auto` |
| `backend/.env.example` | VERIFIED | JWT_SECRET, RESEND_API_KEY, FRONTEND_URL present |
| `backend/app/schemas/auth.py` | VERIFIED | RegisterRequest, LoginRequest, ForgotPasswordRequest, ResetPasswordRequest |
| `backend/app/services/auth_service.py` | VERIFIED | hash_password, verify_password, create_access_token, create_refresh_token, set_auth_cookies, clear_auth_cookies |
| `backend/app/services/redis_service.py` | VERIFIED | get_redis, store_refresh_token, get_refresh_token, rotate_refresh_token, revoke_refresh_token, create_reset_token, consume_reset_token (GETDEL) |
| `backend/app/services/email_service.py` | VERIFIED | send_password_reset_email; debug/prod branch via settings.debug |
| `backend/app/deps.py` | VERIFIED | get_current_user; `algorithms=["HS256"]` explicit |
| `backend/app/routers/auth.py` | VERIFIED | All 6 auth endpoints: /register, /login, /refresh, /logout, /forgot-password, /reset-password |
| `backend/app/schemas/company.py` | VERIFIED | CompanyProfileRequest with @field_validator("bin"); CompanyProfileResponse |
| `backend/app/services/company_service.py` | VERIFIED | upsert_company_profile; select-then-update-or-insert |
| `backend/app/routers/company.py` | VERIFIED | GET + PUT /profile; both auth-gated |
| `frontend/src/middleware.ts` | STUB/BROKEN | Code is correct but jose not installed — cannot load at runtime |
| `frontend/src/lib/api.ts` | VERIFIED | credentials: 'include' (x2); didRetry guard; clearAuth on terminal 401 |
| `frontend/src/store/authStore.ts` | VERIFIED | isAuthenticated, userId, setAuth, clearAuth |
| `frontend/src/app/(auth)/login/page.tsx` | VERIFIED | 'use client'; RHF + zodResolver; api.post('/api/auth/login') |
| `frontend/src/app/(auth)/register/page.tsx` | VERIFIED | 'use client'; RHF + zodResolver; api.post('/api/auth/register') |
| `frontend/src/app/(auth)/forgot-password/page.tsx` | VERIFIED | 'use client'; api.post('/api/auth/forgot-password'); same message always |
| `frontend/src/app/(auth)/reset-password/page.tsx` | VERIFIED | 'use client'; useSearchParams(); api.post('/api/auth/reset-password') |
| `frontend/src/components/auth/LogoutButton.tsx` | VERIFIED | 'use client'; api.post('/api/auth/logout'); clearAuth(); router.push('/login') |
| `frontend/src/app/(dashboard)/layout.tsx` | VERIFIED | Imports and renders LogoutButton |
| `frontend/src/app/(dashboard)/dashboard/page.tsx` | VERIFIED | "Личный кабинет"; userId from authStore; link to /profile |
| `frontend/src/app/(dashboard)/profile/page.tsx` | VERIFIED | 'use client'; useEffect → api.get; CompanyProfileForm with initialData |
| `frontend/src/components/profile/CompanyProfileForm.tsx` | VERIFIED | 'use client'; api.put; regex /^\d{12}$/; setError('bin') on 422 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/app/models/__init__.py` | `backend/alembic/env.py` | import triggers User + CompanyProfile registration | WIRED | Base.metadata contains both tables |
| `backend/app/config.py` | Settings env loading | pydantic-settings reads .env | WIRED | jwt_secret, resend_api_key, frontend_url confirmed at lines 20-22 |
| `frontend/src/app/(auth)/login/page.tsx` | POST /api/auth/login | api.post via lib/api.ts with credentials: 'include' | WIRED | Line 37; api.ts has credentials: 'include' |
| `backend/app/routers/auth.py` | redis_service.store_refresh_token | Redis SETEX refresh_token:{user_id} | WIRED | Lines 72, 105 in auth router |
| `frontend/src/middleware.ts` | access_token cookie | jose.jwtVerify | PARTIAL | Code correct; jose package not installed in node_modules |
| POST /api/auth/refresh | redis_service rotate_refresh_token | Atomic delete+SETEX pipeline | WIRED | rotate_refresh_token function with pipeline; all refresh tests pass |
| `frontend/src/lib/api.ts` | POST /api/auth/refresh | automatic retry on 401 | WIRED | Line 20; didRetry guard at line 13 |
| POST /api/auth/forgot-password | email_service.send_password_reset_email | Resend SDK or dev stdout | WIRED | Router line 181; email_service has debug/prod branch |
| POST /api/auth/reset-password | Redis GETDEL reset:{token} | Atomic single-use | WIRED | consume_reset_token uses redis.getdel |
| PUT /api/company/profile | CompanyProfile table (one-to-one) | upsert_company_profile + user_id unique constraint | WIRED | company_service select-first upsert; CompanyProfile.user_id unique |
| `frontend/src/app/(dashboard)/profile/page.tsx` | GET + PUT /api/company/profile | api.get on mount, api.put on submit | WIRED | profile/page.tsx useEffect line 21; CompanyProfileForm line 54 |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `profile/page.tsx` | `profile` (useState) | `api.get('/api/company/profile')` in useEffect | Yes — backend queries CompanyProfile WHERE user_id | FLOWING |
| `CompanyProfileForm.tsx` | `initialData` prop | Passed from profile/page.tsx, populated by API | Yes — real ORM data via CompanyProfileResponse | FLOWING |
| `dashboard/page.tsx` | `userId` | useAuthStore (Zustand) | In-memory only; not hydrated from cookie on refresh | STATIC (by design — documented stub in 02-02 SUMMARY; acceptable for MVP) |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| BIN validator rejects short BIN | `python3 -c "from app.services.bin_validator import validate_bin; assert validate_bin('12345') is False"` | exit 0 | PASS |
| BIN validator accepts valid BIN | `python3 -c "from app.services.bin_validator import validate_bin; assert validate_bin('190540000014') is True"` | exit 0 | PASS |
| hash_password + verify_password | `python3 -c "from app.services.auth_service import hash_password, verify_password; h = hash_password('test12345'); assert verify_password('test12345', h) and not verify_password('wrong1234', h)"` | exit 0 | PASS |
| All backend integration tests | `pytest tests/ -q` (42 total) | 42 passed, 0 failed | PASS |
| Frontend build | `npm run build` | **Build failed** — @hookform/resolvers/zod and jose not found | FAIL |

---

### Probe Execution

No probes declared in plan files. Step 7c: SKIPPED (no probe scripts found).

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| AUTH-01 | 02-01, 02-02 | Registration with email + password | SATISFIED | POST /api/auth/register; 8 tests pass including 409 duplicate and 422 validation |
| AUTH-02 | 02-02, 02-03 | Login + persistent sessions (refresh) | SATISFIED | POST /api/auth/login; /refresh with atomic rotation; 7 refresh/logout tests |
| AUTH-03 | 02-04 | Password reset via email | SATISFIED | /forgot-password + /reset-password; single-use GETDEL; 7 tests including replay 400 |
| AUTH-04 | 02-03 | Logout | SATISFIED | POST /api/auth/logout; Redis revocation + cookie deletion; test_logout_clears_redis_and_cookies passes |
| COMP-01 | 02-05 | Company profile create (BIN, name, address) | SATISFIED | PUT /api/company/profile with upsert; @field_validator BIN check; 7 tests including checksum 422 |
| COMP-02 | 02-05 | Company profile edit (any time, no duplicate) | SATISFIED | Idempotent PUT; test_put_profile_updates_existing_row passes; DB unique constraint on user_id |

All 6 requirement IDs from plan frontmatter accounted for. No orphaned requirements for Phase 2 in REQUIREMENTS.md.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/app/(dashboard)/dashboard/page.tsx` | 12 | `userId ?? '—'` — Zustand not hydrated on page refresh | INFO | Documented in 02-02 SUMMARY as a known limitation; no deceptive rendering — the page clearly shows '—' rather than stale data |
| `frontend/src/app/(dashboard)/layout.tsx` | — | Logout link `href="/api/auth/logout"` (old stub) was replaced with LogoutButton | INFO | LogoutButton is properly wired — not a stub |

No TBD, FIXME, or XXX markers found in any phase-modified file.

---

### Human Verification Required

No human verification items needed — all truths are either VERIFIED or FAILED by automated checks.

---

### Gaps Summary

**Root cause: one missing `npm install`.**

The frontend `node_modules` directory does not contain `@hookform/resolvers` or `jose`, even though both are declared in `package.json`. The 02-04 SUMMARY acknowledges this issue ("node_modules not installed in worktree") and states `npm install --prefer-offline` was run, but it was run in a worktree that is separate from the current working tree. The installation did not persist to the main checkout.

**Impact of the gap:**

1. `npm run build` fails with two `Module not found` errors.
2. `frontend/src/middleware.ts` imports from `'jose'` — without the package, the Next.js Edge runtime cannot instantiate the middleware, meaning the `/dashboard` JWT protection gate is non-functional.
3. `/register`, `/reset-password`, and `CompanyProfileForm` all import from `@hookform/resolvers/zod` and cannot render.

**Fix: one command** — run `npm install` in `frontend/`. All other code is correct and complete.

---

_Verified: 2026-06-10_
_Verifier: Claude (gsd-verifier)_
