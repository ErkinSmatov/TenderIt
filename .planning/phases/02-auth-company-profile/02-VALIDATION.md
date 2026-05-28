---
phase: 2
slug: auth-company-profile
status: active
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-29
---

# Phase 2 — Validation Strategy

> Per-phase validation contract. Run after every task commit to catch regressions early.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Backend framework** | pytest 7.x with pytest-asyncio |
| **Config file** | `backend/pytest.ini` (created in Wave 0, `asyncio_mode = auto`) |
| **Quick run (backend)** | `cd backend && python -m pytest tests/ -x -q` |
| **Full suite (backend)** | `cd backend && python -m pytest tests/ -v --cov=app` |
| **Frontend framework** | Next.js built-in — `next build` for type/lint check |
| **Estimated runtime** | ~15 seconds (backend); ~30 seconds (frontend build) |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/ -x -q`
- **After Wave 0 completes:** Run full suite + `alembic upgrade head` + `alembic check`
- **After each wave completes:** Run full suite + manual smoke test of affected endpoints

---

## Per-Task Verification Map

| Wave | Plan | Task | Key Verify Command | Expected Result |
|------|------|------|-------------------|-----------------|
| 0 | 02-01 | T1: Settings + deps | `python -c "from app.config import settings; print(settings.jwt_secret)"` | Prints value (from env), no error |
| 0 | 02-01 | T1: Frontend deps | `cd frontend && cat package.json \| grep jose` | `"jose"` present |
| 0 | 02-01 | T2: Models + migration | `alembic upgrade head && alembic check` | Exits 0; no pending migrations |
| 0 | 02-01 | T3: BIN validator | `cd backend && python -m pytest tests/test_bin_validation.py -v` | All tests green |
| 1 | 02-02 | T1: Auth endpoints | `cd backend && python -m pytest tests/test_auth_register_login.py -x -q` | All green; 201 on register, 200 on login, cookies set |
| 1 | 02-02 | T2: Frontend + middleware | `cd frontend && next build` | Exits 0; no TypeScript errors |
| 2 | 02-03 | T1: Refresh rotation | `cd backend && python -m pytest tests/test_auth_refresh_logout.py -x -q` | Green; old token rejected after rotation |
| 2 | 02-03 | T2: Logout | `cd backend && python -m pytest tests/test_auth_refresh_logout.py -x -q` | Green; 401 on subsequent request with old token |
| 3 | 02-04 | T1: Password reset backend | `cd backend && python -m pytest tests/test_auth_password_reset.py -x -q` | Green; token consumed after single use |
| 3 | 02-04 | T2: Password reset pages | `cd frontend && next build` | Exits 0 |
| 4 | 02-05 | T1: Company profile API | `cd backend && python -m pytest tests/test_company_profile.py -x -q` | Green; invalid BIN returns 422 |
| 4 | 02-05 | T2: Profile page | `cd frontend && next build` | Exits 0 |

---

## Full Phase Gate (run before marking Phase 2 complete)

```bash
# Backend: full suite with coverage
cd backend && python -m pytest tests/ -v --cov=app --cov-report=term-missing

# Database: migrations clean
alembic upgrade head && alembic check

# Frontend: type check + build
cd frontend && next build

# Manual smoke tests (in running dev stack):
# 1. POST /api/auth/register -> 201, email in DB
# 2. POST /api/auth/login -> 200, httpOnly cookies set
# 3. GET /api/company/profile (authenticated) -> 200 or 404 (before profile created)
# 4. PUT /api/company/profile with invalid BIN -> 422
# 5. PUT /api/company/profile with valid BIN -> 200
# 6. POST /api/auth/logout -> 200, subsequent requests return 401
```

---

## Security Assertions (ASVS L1)

These must hold after Wave 1 completes:

| Check | Assertion |
|-------|-----------|
| Rate limiting | POST /api/auth/login with wrong password 6x in 60s -> 429 |
| JWT algorithm pinned | PyJWT.decode with algorithms=["HS256"] -- RS256 rejected |
| httpOnly cookie | Browser DevTools: login response sets access_token cookie with HttpOnly flag |
| SameSite | Cookie has SameSite=Lax |
| Refresh token rotation | Using the same refresh token twice -> second use returns 401 |
| BIN position 5 | BIN starting with digit other than 4/5/6 at position 5 -> 422 |
| No email enumeration | POST /forgot-password with unknown email -> same 200 response as known email |

---

*Phase: 02-auth-company-profile*
*Validation strategy created: 2026-05-29*
