---
phase: 05-eds-signing-submission
plan: "01"
subsystem: backend
tags: [applications, state-machine, goszakup-proxy, redis, alembic, idor, tdd]
dependency_graph:
  requires:
    - "04-02 (Document Vault routes — /api/documents/attachable used by wizard)"
    - "03-01 (Tender model, Tender.id FK for applications table)"
    - "02-01 (User model, JWT auth — get_current_user)"
  provides:
    - "Application ORM model + migration 0004"
    - "POST/GET /api/applications endpoints (APPL-01, APPL-05)"
    - "application_service full state machine (all transitions for 05-03, 05-04)"
    - "GoszakupPortalClient (login + public_application, step 12)"
    - "Redis session/confirm helpers with correct TTLs"
    - "goszakup_proxy router shell (05-03 adds step 1-11 endpoints)"
  affects:
    - "05-03 (wizard proxy endpoints — calls application_service + GoszakupPortalClient)"
    - "05-04 (ARQ polling worker — calls list_waiting_applications, mark_submitted etc)"
tech_stack:
  added:
    - "SQLAlchemy JSONB + ARRAY(Integer) columns for lots_data/document_ids"
    - "fakeredis.aioredis for Redis helper unit tests"
    - "respx for httpx mocking (GoszakupPortalClient tests)"
  patterns:
    - "TDD: RED commit → GREEN commit for Tasks 2 and 3"
    - "IDOR protection: get_user_application filters WHERE id AND user_id, returns 404 not 403"
    - "Partial PostgreSQL index: idx_applications_status WHERE status IN ('waiting','submitting')"
    - "Per-call httpx.AsyncClient (never shared singleton) in GoszakupPortalClient"
    - "JSON-serialized JSONB: lots_data stored as list[dict] with Decimal → str conversion"
key_files:
  created:
    - backend/alembic/versions/0004_create_applications.py
    - backend/app/models/application.py
    - backend/app/schemas/application.py
    - backend/app/services/application_service.py
    - backend/app/services/goszakup_portal_client.py
    - backend/app/routers/applications.py
    - backend/app/routers/goszakup_proxy.py
    - backend/tests/test_applications.py
    - backend/tests/test_goszakup_proxy.py
  modified:
    - backend/app/models/user.py (added telegram_chat_id BigInteger)
    - backend/app/models/__init__.py (registered Application)
    - backend/app/services/redis_service.py (added goszakup session/confirm helpers)
    - backend/app/main.py (registered applications + goszakup_proxy routers)
decisions:
  - "TEXT status column (not PG ENUM) — D-05-04: easy v2 extension without ALTER TYPE"
  - "Per-call AsyncClient in GoszakupPortalClient — avoids event-loop lifetime issues"
  - "lots_data Decimal → str in service layer — avoids JSONB serialization errors with Decimal"
  - "goszakup_proxy.py created as empty router shell — 05-03 adds endpoints without touching main.py"
metrics:
  duration_minutes: 40
  completed_date: "2026-07-09"
  tasks_completed: 3
  files_created: 9
  files_modified: 4
  tests_added: 21
---

# Phase 5 Plan 01: Backend Foundation (DB + Services + Routers) Summary

## One-liner

Applications table (Alembic 0004), full state-machine service, IDOR-safe REST endpoints, GoszakupPortalClient (login + step-12 submit), and Redis session/confirm helpers — TDD, all 21 tests green.

## What Was Built

### Task 1: Migration 0004 + Application ORM model
- `alembic/versions/0004_create_applications.py`: creates `applications` table with JSONB `lots_data`, `ARRAY(Integer)` `document_ids`, TEXT `status` (not PG ENUM), two BigInteger portal ID columns, timestamps. Partial index `idx_applications_status WHERE status IN ('waiting','submitting')` for ARQ polling efficiency.
- Adds `users.telegram_chat_id BIGINT` (D-05-06 Telegram notify flow).
- `app/models/application.py`: `Application(Base)` ORM model matching DDL exactly.
- `app/models/__init__.py`: registers `Application` so Alembic autogenerate sees it.

### Task 2: GoszakupPortalClient + Redis helpers (TDD)
- `goszakup_portal_client.py`: `GoszakupPortalClient` with two async methods:
  - `login_with_signed_xml(signed_xml) → str` — POSTs to `/user/sendsign/kz`, extracts `PHPSESSID` from `Set-Cookie`, raises `ValueError` if absent. `follow_redirects=True` handles multi-step goszakup login redirects.
  - `public_application(tender_buy_id, application_id, phpsessid, csrf) → dict` — Step 12 final submit. POSTs `public_app=Y&agree_price=false&…` to `/ru/application/ajax_public_application/{tBuyId}/{appId}`. Neither `phpsessid` nor `csrf` are ever logged (T-05-03 mitigation).
- `redis_service.py` additions: `store_goszakup_session` (TTL 72000s, T-05-06), `get_goszakup_session`, `set_confirm_pending` (TTL 900s), `update_confirm` (SET without TTL change), `get_confirm`.

### Task 3: application_service + schemas + routers + registration (TDD)
- `schemas/application.py`: `LotOffer`, `ApplicationCreate` (non-empty lots_data validator — T-05-05), `ApplicationResponse` (from_attributes=True).
- `services/application_service.py`: complete state machine — `create_application`, `list_user_applications`, `get_user_application` (IDOR-safe), `mark_ready`, `list_waiting_applications`, `mark_submitting`, `mark_submitted`, `mark_error`, `increment_retry`, `to_response`.
- `routers/applications.py`: `POST /api/applications` (201, user_id from JWT T-05-02), `GET /api/applications`, `GET /api/applications/{id}` (IDOR 404 T-05-01).
- `routers/goszakup_proxy.py`: empty router shell with docstring explaining D-05-01 architecture. Plan 05-03 adds step 1-11 endpoints without touching `main.py`.
- `main.py`: both routers registered with correct prefixes and tags.

## Tests

| File | Tests | Status |
|------|-------|--------|
| test_applications.py | 8 | GREEN |
| test_goszakup_proxy.py | 13 | GREEN |
| **Total** | **21** | **GREEN** |

Key test coverage:
- `POST /api/applications` → 201 + status="draft" (APPL-01)
- `POST /api/applications` with empty lots_data → 422 (T-05-05)
- `GET /api/applications` user isolation (APPL-05)
- `GET /api/applications/{id}` IDOR → 404 not 403 (T-05-01)
- `GoszakupPortalClient.public_application` URL + body + JSON return (respx mock)
- `login_with_signed_xml` PHPSESSID extraction + ValueError on missing
- Redis TTL assertions: 72000s session, 900s confirm

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocker] Alembic migration 0004 needed to run before tests**
- **Found during:** Task 3 RED phase
- **Issue:** Test DB was at revision 0003; User model now includes `telegram_chat_id` causing `UndefinedColumnError` during test setup
- **Fix:** Ran `alembic upgrade head` to apply migration 0004 to the local test DB
- **Files modified:** DB schema (not source code)

**2. [Rule 1 - Bug] Decimal serialization for JSONB lots_data**
- **Found during:** Task 3 GREEN implementation
- **Issue:** Pydantic `LotOffer.unit_price` and `total_price` are `Decimal` — asyncpg/JSONB cannot serialize `Decimal` directly
- **Fix:** `application_service.create_application()` converts each `LotOffer` to a plain dict with `str(decimal_value)` before storing in JSONB column
- **Files modified:** `backend/app/services/application_service.py`

## Known Stubs

None — all endpoints are fully functional. The `goszakup_proxy.py` router is intentionally empty (a shell), explicitly documented to be filled by plan 05-03.

## Threat Flags

No new security-relevant surface beyond what the plan's `<threat_model>` describes:
- T-05-01 mitigated: IDOR-safe `get_user_application(WHERE id AND user_id)` → 404
- T-05-02 mitigated: `user_id=current_user.id` in `create_application_route`
- T-05-03 mitigated: `phpsessid`/`csrf` never appear in log statements in `goszakup_portal_client.py`
- T-05-05 mitigated: `lots_data_must_be_non_empty` Pydantic validator in `ApplicationCreate`
- T-05-06 mitigated: `_GOSZAKUP_SESSION_TTL = 72000` hard TTL on every Redis write

## TDD Gate Compliance

- Task 2: `test(05-01)` RED commit `2fed8c3` → `feat(05-01)` GREEN commit `2872386` ✓
- Task 3: `test(05-01)` RED commit `7b8c5c3` → `feat(05-01)` GREEN commit `6d9824e` ✓

## Self-Check: PASSED

Files verified:
- backend/alembic/versions/0004_create_applications.py ✓
- backend/app/models/application.py ✓
- backend/app/models/user.py (telegram_chat_id) ✓
- backend/app/schemas/application.py ✓
- backend/app/services/application_service.py ✓
- backend/app/services/goszakup_portal_client.py ✓
- backend/app/routers/applications.py ✓
- backend/app/routers/goszakup_proxy.py ✓
- backend/app/main.py (both routers registered) ✓
- backend/tests/test_applications.py (8 tests GREEN) ✓
- backend/tests/test_goszakup_proxy.py (13 tests GREEN) ✓

Commits verified:
- 8122c74 feat(05-01): Migration 0004 + Application model ✓
- 2fed8c3 test(05-01): RED goszakup proxy tests ✓
- 2872386 feat(05-01): GoszakupPortalClient + Redis helpers ✓
- 7b8c5c3 test(05-01): RED applications tests ✓
- 6d9824e feat(05-01): application_service + routers + registration ✓
