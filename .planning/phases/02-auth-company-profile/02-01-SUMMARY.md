---
plan: 02-01
phase: 02-auth-company-profile
status: complete
wave: 0
completed: 2026-06-09
---

# Plan 02-01 Summary — Foundation Wave

## What Was Built

### Settings & Dependencies (Task 1)
- `backend/app/config.py`: Added `jwt_secret` (str, default `"change-me-in-production"`), `resend_api_key` (str, default `""`), `frontend_url` (str, default `"http://localhost:3000"`)
- `backend/.env.example`: Added `JWT_SECRET=`, `RESEND_API_KEY=`, `FRONTEND_URL=http://localhost:3000` with generation hint
- `backend/pyproject.toml`: Added `pyjwt==2.13.0`, `pwdlib[argon2]==0.3.0`, `redis==8.0.0`, `slowapi==0.1.9`, `resend==2.30.1`
- `backend/pytest.ini`: `asyncio_mode = auto`, `testpaths = tests`, `addopts = -ra`
- `frontend/package.json`: Added `jose@^6.2.3`, `@hookform/resolvers@^5.4.0`

### Models (Task 2)
- `backend/app/models/user.py`: `User` model — `id`, `email` (unique, indexed), `hashed_password`, `is_active`, `is_verified`, `created_at` (server_default). Relationship to `CompanyProfile` with `lazy="selectin"`
- `backend/app/models/company_profile.py`: `CompanyProfile` model — `id`, `user_id` (FK unique), `bin` (12), `company_name` (500), `legal_address` (1000), `updated_at`. Relationship to `User` with `lazy="selectin"`
- `backend/app/models/__init__.py`: Explicit imports of both models — ensures Alembic autogenerate sees `Base.metadata`

### Migration, BIN Validator, Test Infra (Task 3)
- `backend/alembic/versions/0001_create_users_company_profiles.py`: Creates `users` and `company_profiles` tables. Revision: `861194df635a`. Applied to dev Postgres ✅
- `backend/app/services/bin_validator.py`: `validate_bin(bin_str: str) -> bool` — validates 12-digit BIN; rejects non-digit, wrong length, position-5 ∉ {4,5,6}; runs two-cycle mod-11 checksum algorithm (KZ official spec)
- `backend/tests/test_bin_validation.py`: 10 tests — known-good BINs `"190540000014"` and `"190640000018"`, plus edge cases (empty, short, long, non-digit, bad position-5, wrong checksum, space in string)
- `backend/tests/conftest.py`: Added `db_session` fixture (function-scoped, async, rolls back on teardown). Preserved existing session-scoped `client` fixture

## Test Results
```
10 passed in 0.01s  (tests/test_bin_validation.py)
alembic current: 861194df635a (head)
```

## Deviations from RESEARCH.md
- None. All patterns followed as specified (lazy="selectin", models/__init__.py explicit imports, two-cycle checksum).

## Self-Check: PASSED
