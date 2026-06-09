---
plan: 02-05
phase: 02-auth-company-profile
status: complete
wave: 4
completed: 2026-06-09
subsystem: company-profile
tags: [fastapi, pydantic, sqlalchemy, nextjs, react-hook-form, zod, bin-validation]
dependency_graph:
  requires:
    - 02-01  # CompanyProfile model, validate_bin, DB migration
    - 02-02  # get_current_user dependency, get_db, auth cookies
  provides:
    - GET /api/company/profile
    - PUT /api/company/profile
    - Frontend /profile page (load + edit)
    - CompanyProfileForm component
  affects:
    - Phase 5  # EDS signing will reference company BIN for signing context
tech_stack:
  added: []
  patterns:
    - pydantic v2 @field_validator calling external validate_bin (422 on failure)
    - SQLAlchemy async select-then-update-or-insert upsert (user_id unique constraint guard)
    - CompanyProfileResponse model_config from_attributes for ORM serialization
    - user_id from JWT dependency only — never from request body (T-02-05-02)
    - RHF + zodResolver client-side BIN format check (regex only); checksum delegated to backend
    - api.put error surfacing — 422 BIN errors set under bin field via setError
key_files:
  created:
    - backend/app/schemas/company.py
    - backend/app/services/company_service.py
    - backend/app/routers/company.py
    - backend/tests/test_company_profile.py
    - frontend/src/components/profile/CompanyProfileForm.tsx
    - frontend/src/app/(dashboard)/profile/page.tsx
  modified:
    - backend/app/main.py  # registered company router
    - frontend/src/app/(dashboard)/dashboard/page.tsx  # added /profile link
decisions:
  - "Redis mocked via patch('app.routers.auth.store_refresh_token') in authed_client fixture — consistent with test_auth_register_login.py approach"
  - "authed_client fixture is module-scoped (not session-scoped) to isolate DB state per test module"
  - "GET returns CompanyProfileResponse() with all None fields when no profile exists — 200 not 404"
  - "Client-side BIN validation is regex only (/^\\d{12}$/); checksum validation is backend-only per RESEARCH.md responsibility map"
  - "compute_valid_bin() helper in test file synthesises BIN algorithmically (same two-cycle checksum) to avoid hardcoding BINs that might be real entities"
metrics:
  duration_minutes: 30
  tasks_completed: 2
  files_created: 6
  files_modified: 2
---

# Phase 02 Plan 05: Company Profile — Endpoint + Frontend Page

**One-liner:** BIN-validated upsert endpoint (GET/PUT /api/company/profile) with auth-scoped user isolation, plus RHF+zod profile form with backend error surfacing.

## Endpoint Contracts Implemented

| Method | Path | Auth | Request Body | Response |
|--------|------|------|-------------|----------|
| GET | /api/company/profile | JWT cookie | — | `{bin, company_name, legal_address, updated_at}` (all null if no profile) |
| PUT | /api/company/profile | JWT cookie | `{bin, company_name, legal_address}` | Same shape, populated |
| PUT | /api/company/profile | JWT cookie | Invalid BIN | 422 `{detail: [{loc: ["body","bin"], msg: "Некорректный БИН"}]}` |
| GET/PUT | /api/company/profile | No token | — | 401 `{detail: "Not authenticated"}` |

## Upsert Algorithm and Constraint Enforcement

```python
# company_service.upsert_company_profile
result = await db.execute(select(CompanyProfile).where(CompanyProfile.user_id == user_id))
profile = result.scalar_one_or_none()

if profile:
    profile.bin = data.bin           # update existing row
    ...
else:
    profile = CompanyProfile(user_id=user_id, ...)  # insert new row
    db.add(profile)

await db.commit()
await db.refresh(profile)
return profile
```

One-to-one enforced at DB level: `CompanyProfile.user_id` has a `UniqueConstraint`. The select-first pattern prevents duplicate rows under normal conditions. If a race causes two inserts, the DB unique constraint raises `IntegrityError` (MVP-acceptable; retry path deferred to Phase 5).

**user_id is always server-derived** from the JWT-validated `get_current_user` dependency — never accepted from the request body. This enforces T-02-05-02 (cross-user profile modification).

## BIN Validation Approach

```
Client side (CompanyProfileForm.tsx):
  z.string().regex(/^\d{12}$/, 'Введите 12 цифр')
  → catches wrong length and non-digit chars before API call

Server side (CompanyProfileRequest @field_validator):
  validate_bin(v)  — full checksum + position-5 ∈ {4,5,6} check
  → returns 422 with loc=["body","bin"] on failure
```

Client does NOT replicate the checksum — backend is the source of truth (per RESEARCH.md Pitfall 5 and responsibility map). Checksum errors from backend are surfaced under the bin field in the form via `setError('bin', { message })`.

## Frontend Form Behavior

- `/profile` page: `useEffect` calls `api.get('/api/company/profile')` on mount; shows "Загрузка..." during fetch; passes `initialData` to `CompanyProfileForm`
- `CompanyProfileForm`: RHF `defaultValues` pre-fill null→'' for create; same form handles edit
- On submit: `api.put('/api/company/profile', data)` → "Профиль сохранён" banner on success
- On 422 from backend: message containing "БИН" → `setError('bin', { message })` → visible under BIN field
- `/dashboard` has a `<Link href="/profile">Профиль компании</Link>` for navigation

## Total Phase 2 Test Count

| Test File | Count | Status |
|-----------|-------|--------|
| test_bin_validation.py | 10 | passed |
| test_auth_register_login.py | 8 | passed |
| test_health.py | 1 | passed |
| test_company_profile.py | 7 | passed |
| **Total** | **26** | **26 passed, 2 skipped (API spike — no token)** |

## Manual Smoke Test

Not executed (no running server in CI context). Recommended steps:
1. `docker compose up redis` + `cd backend && uvicorn app.main:app --reload`
2. `cd frontend && cp .env.local.example .env.local && npm run dev`
3. Register at http://localhost:3000/register
4. Navigate to /dashboard → click "Профиль компании"
5. Fill in БИН (12 digits), company name, legal address → "Сохранить"
6. Verify "Профиль сохранён" banner appears
7. Reload /profile → fields pre-filled with saved values
8. Change company name → save → reload → updated value persists
9. Test invalid BIN (e.g. 123456789012) → verify "Некорректный БИН" under BIN field

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Redis connection error in authed_client fixture**
- **Found during:** Task 1, GREEN phase
- **Issue:** `authed_client` fixture registers a user via `/api/auth/register`. The auth router calls `store_refresh_token(redis, ...)` which requires a live Redis. Tests failed with `redis.exceptions.ConnectionError` since Redis is not running in CI.
- **Fix:** Added `patch("app.routers.auth.store_refresh_token", new=AsyncMock())` inside the `authed_client` fixture's register call, consistent with the approach used in `test_auth_register_login.py`.
- **Files modified:** backend/tests/test_company_profile.py
- **Commit:** d167bbd (included in GREEN commit)

## Threat Mitigations Applied

| Threat ID | Mitigation | Verified |
|-----------|-----------|----------|
| T-02-05-01 | @field_validator("bin") calls validate_bin(); 422 on bad checksum or position-5 | test_put_profile_invalid_bin_checksum_returns_422 passes |
| T-02-05-02 | user_id = current_user.id from JWT; never from body | grep: no user_id in CompanyProfileRequest |
| T-02-05-03 | No BIN in error responses; logs not structured in this phase | N/A |
| T-02-05-04 | GET WHERE user_id == current_user.id; no path param for other users | grep: select where user_id |
| T-02-05-05 | select-first upsert; DB unique constraint fallback | test_put_profile_updates_existing_row passes (idempotent) |
| T-02-05-06 | Storage is local Postgres only; no PII processor | CLAUDE.md KZ localization constraint |

## Known Stubs

None — all data is wired from DB through the API to the form. The profile loads from real storage.

## Self-Check: PASSED

Files created (spot check):
- backend/app/schemas/company.py ✓
- backend/app/services/company_service.py ✓
- backend/app/routers/company.py ✓
- backend/tests/test_company_profile.py ✓
- frontend/src/components/profile/CompanyProfileForm.tsx ✓
- frontend/src/app/(dashboard)/profile/page.tsx ✓

Commits:
- 8cf776e test(02-05): TDD RED ✓
- d167bbd feat(02-05): backend company profile ✓
- 4c60d0d feat(02-05): frontend profile page + form ✓

Test results: 26/26 passed (backend pytest), 0 TypeScript errors (next build)
