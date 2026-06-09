---
phase: 02-auth-company-profile
plan: 04
subsystem: backend/auth, frontend/auth
tags: [password-reset, email-service, redis, auth, tdd]
dependency_graph:
  requires: [02-03]
  provides: [POST /api/auth/forgot-password, POST /api/auth/reset-password, email_service, /forgot-password page, /reset-password page]
  affects: [backend/app/routers/auth.py, backend/app/services/redis_service.py, backend/app/schemas/auth.py]
tech_stack:
  added: [resend SDK (prod email), fakeredis (test)]
  patterns: [GETDEL atomic single-use token, debug-vs-prod email branch, Suspense boundary for useSearchParams]
key_files:
  created:
    - backend/app/services/email_service.py
    - frontend/src/app/(auth)/forgot-password/page.tsx
    - frontend/src/app/(auth)/reset-password/page.tsx
    - backend/tests/test_auth_password_reset.py
  modified:
    - backend/app/schemas/auth.py
    - backend/app/services/redis_service.py
    - backend/app/routers/auth.py
decisions:
  - "Committed user fixture instead of rolled-back db_session: integration tests for the forgot-password endpoint require the user to be visible to the app's DB session, so registered_user commits and cleans up explicitly"
  - "useSearchParams wrapped in Suspense: Next.js 14 App Router static rendering requires Suspense boundary around useSearchParams; ResetPasswordForm is the inner component"
  - "Error swallowed on forgot-password submit in frontend: to prevent timing-based enumeration at the UI layer, even network errors show the same success message"
metrics:
  duration: "~30 min"
  completed: "2026-06-10"
  tasks_completed: 2
  files_changed: 7
---

# Phase 2 Plan 4: Password Reset Flow Summary

One-liner: Email-based password reset with atomic single-use Redis token (GETDEL, 900s TTL), Resend SDK in prod / stdout log in debug, no email enumeration (identical 202 for known/unknown email).

## Endpoint Contracts

| Method | Path | Request Body | Success | Error |
|--------|------|--------------|---------|-------|
| POST | /api/auth/forgot-password | `{email: EmailStr}` | 202 `{message: "Если email зарегистрирован, ссылка отправлена"}` | Same 202 (no enumeration) |
| POST | /api/auth/reset-password | `{token: str (min 32), new_password: str (min 8, max 128)}` | 204 (no body) | 400 `{detail: "Ссылка недействительна или истекла"}` |

Both endpoints are rate-limited: forgot-password at 3/minute per IP, reset-password at 5/minute per IP.

## Reset Token Design

- **Generation:** `secrets.token_urlsafe(32)` — 256 bits of entropy from `os.urandom` (T-02-04-03)
- **Storage:** Redis key `reset:{token}` → `user_id`, TTL 900 seconds (15 min) — T-02-04-06
- **Consumption:** `redis.getdel(f"reset:{token}")` — atomic read + delete (T-02-04-01, single-use)
- **Format:** `{settings.frontend_url}/reset-password?token={token}`

## Debug vs. Production Email Branch

| Mode | Behavior |
|------|----------|
| `settings.debug = True` | `print("[DEV] Password reset link for {email}: {link}")` to stdout; Resend SDK never called |
| `settings.debug = False` | `resend.Emails.send(...)` with `from=noreply@tenderit.kz`; exceptions swallowed (logged to stderr) to prevent timing leak (T-02-04-02) |

## Frontend Pages

- **/forgot-password:** `'use client'`, RHF+zod email validation, on submit calls `api.post('/api/auth/forgot-password', {email})`; always shows success confirmation regardless of result (no UI enumeration)
- **/reset-password:** `'use client'`, reads `?token=` via `useSearchParams()` wrapped in `<Suspense>` (Next.js App Router requirement); if token absent renders "Недействительная ссылка"; RHF+zod min-8 password; on success shows "Пароль изменён" with link to /login; on error displays API detail

## Test Coverage After Wave 3

| File | Tests |
|------|-------|
| test_auth_register_login.py | 5 |
| test_auth_refresh_logout.py | 7 |
| test_auth_password_reset.py | 7 (this plan) |
| test_bin_validation.py | 12 |
| test_company_profile.py | 9 |
| test_health.py | 1 |
| **Total** | **40 passed** |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test fixture used rolled-back session — user not visible to app**

- **Found during:** Task 1, GREEN phase
- **Issue:** The `registered_user` fixture used `db_session` which wraps in `session.begin()` that rolls back after the test. The endpoint's DB session (separate connection) could not see the uncommitted user, so `forgot-password` always returned "no user found" and created no Redis key.
- **Fix:** Replaced `db_session` fixture with a self-managed `AsyncSessionLocal()` that commits the user and deletes it on teardown. The test for password verification also uses a fresh `AsyncSessionLocal()` to see committed data.
- **Files modified:** `backend/tests/test_auth_password_reset.py`
- **Commit:** f3b6686

**2. [Rule 3 - Blocking] Node modules not installed in worktree**

- **Found during:** Task 2 frontend build
- **Issue:** The git worktree did not have `node_modules/` (expected: they live in main repo, not in worktrees), so `npm run build` failed with "next: command not found".
- **Fix:** Ran `npm install --prefer-offline` in the worktree's frontend directory.
- **Commit:** Not a separate commit — prerequisite to Task 2 commit.

## Threat Surface Scan

No new threat surfaces beyond those in the plan's threat model. All 8 identified threats (T-02-04-01 through T-02-04-08) are mitigated or accepted per the plan.

## Known Stubs

None — both endpoints are fully wired. Email service in debug mode logs to stdout (intentional for dev environment, documented).

## Self-Check: PASSED

- `backend/app/services/email_service.py` — exists
- `frontend/src/app/(auth)/forgot-password/page.tsx` — exists
- `frontend/src/app/(auth)/reset-password/page.tsx` — exists
- `backend/tests/test_auth_password_reset.py` — exists
- Commits d6d65af, f3b6686, 79d0391 — all present
- 40 backend tests pass, frontend build exits 0
