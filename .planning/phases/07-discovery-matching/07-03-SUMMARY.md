---
phase: 07-discovery-matching
plan: "03"
subsystem: backend
tags: [matching-engine, arq, discovery-api, idor, tdd, integration-tests]
dependency_graph:
  requires:
    - "07-01: ClientFilter + TenderMatch ORM models + schemas"
    - "07-02: poll_goszakup_discovery ARQ cron task"
  provides:
    - "match_tenders_for_user() in matching_service.py"
    - "run_matching ARQ on-demand task"
    - "worker_settings.py: poll_goszakup_discovery cron + run_matching in functions"
    - "GET/PUT /api/discovery/filters router"
    - "GET /api/discovery/matches router (IDOR-safe)"
    - "POST /api/discovery/{match_id}/participate + skip routers"
  affects:
    - "backend/app/workers/worker_settings.py — extended with 2 cron + 2 functions"
    - "backend/app/main.py — discovery router registered"
tech_stack:
  added: []
  patterns:
    - "SQLAlchemy ILIKE OR-join across name_ru / name_kz for keyword matching"
    - "pg_insert().on_conflict_do_nothing(index_elements=['user_id','tender_id']) — dedup"
    - "pg_insert().on_conflict_do_update(index_elements=['user_id']) — filter upsert"
    - "Lazy import for create_discovery_draft (parallel worktree safety)"
    - "unittest.mock.patch(create=True) for patching non-yet-existing attributes in tests"
    - "AsyncMock session mock for unit tests (avoids pytest-asyncio event loop conflicts)"
key_files:
  created:
    - backend/app/services/matching_service.py
    - backend/app/workers/tasks/run_matching.py
    - backend/tests/test_matching_service.py
    - backend/app/routers/discovery.py
    - backend/tests/test_discovery_filters.py
    - backend/tests/test_discovery_matches.py
  modified:
    - backend/app/workers/worker_settings.py
    - backend/app/main.py
decisions:
  - "TDD mock strategy: AsyncMock session avoids pytest-asyncio 1.3.0 function-loop event loop conflicts"
  - "create_discovery_draft patched with create=True in test_discovery_matches.py (07-04 parallel)"
  - "SimpleNamespace (not ClientFilter ORM) for in-memory filter config in unit tests"
  - "IDOR guard: WHERE id=match_id AND user_id=current_user.id → 404 (not 403) on mismatch"
  - "D-03: run_matching sends notification only if user.telegram_chat_id is not None"
  - "D-10: ClientFilter upsert via pg_insert().on_conflict_do_update(index_elements=['user_id'])"
metrics:
  duration: "~30 minutes"
  completed: "2026-07-20"
  tasks_completed: 2
  files_created: 6
  files_modified: 2
---

# Phase 7 Plan 03: Matching Engine + Discovery CRUD API Summary

**One-liner:** Rule-based matching engine (`match_tenders_for_user` with ILIKE OR keywords / region exact / spgz_codes IN / amount range) + ARQ `run_matching` task + discovery CRUD router (filter CRUD, match feed, participate/skip actions) with full IDOR guards.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| RED | TDD failing tests for matching_service | `eafdd6a` | `tests/test_matching_service.py` |
| Task 1 | matching_service + run_matching + worker_settings | `74e4474` | `matching_service.py`, `run_matching.py`, `worker_settings.py`, `test_matching_service.py` |
| Task 2 | discovery router + main.py + integration tests | `198d289` | `discovery.py`, `main.py`, `test_discovery_filters.py`, `test_discovery_matches.py` |

---

## What Was Built

### Task 1: matching_service.py + run_matching.py + worker_settings.py

**`matching_service.py`:**
- `match_tenders_for_user(db, user_id, cf, new_tender_ids)` — pure async function
- AND logic across all active filter types (only active = non-empty/non-None)
- Keyword filter: OR-joined ILIKE (`%kw%`) on `name_ru` + `name_kz`; empty list = no filter
- Region: exact string match on `tender.region`; `None` = no filter
- СПГЗ codes: `tender.spgz_code IN cf.spgz_codes`; empty list = no filter
- Amount range: `total_sum >= min_amount` and/or `total_sum <= max_amount`; both nullable

**`run_matching.py`:**
- ARQ on-demand task called by `poll_goszakup_discovery`
- Loads all `ClientFilter` rows (one per user, D-10)
- For each filter, calls `match_tenders_for_user`
- Inserts `TenderMatch` with `ON CONFLICT(user_id, tender_id) DO NOTHING` (Pitfall 3)
- Returns `new_match_id = None` on conflict → skips notification (dedup guard)
- D-03 guard: sends Telegram notification only if `user.telegram_chat_id is not None`
- Lazy import of `send_discovery_notification` (created by 07-04 running in parallel)
- Telegram failure is logged and swallowed (same pattern as `poll_watchlist.py`)
- `_utcnow()` helper defined locally (same pattern as `application_service.py`)

**`worker_settings.py`:**
- Added `from app.workers.tasks.poll_goszakup_discovery import poll_goszakup_discovery`
- Added `from app.workers.tasks.run_matching import run_matching`
- `cron_jobs` extended: `cron(poll_goszakup_discovery, minute={0,15,30,45}, unique=True)` (D-06)
- `functions` extended: `[auto_submit_application, run_matching]`

**`test_matching_service.py`:**
- 10 unit tests, all pass
- AsyncMock session (not real DB) — avoids pytest-asyncio 1.3.0 event loop conflicts
- Tests cover: name_ru ILIKE, name_kz ILIKE, keyword miss, OR logic, region match/mismatch, amount range, below min, all-null pass-through, spgz filter

### Task 2: discovery.py + main.py + integration tests

**`discovery.py` (5 endpoints):**
- `GET /api/discovery/filters` — returns ClientFilterResponse; 404 if not set
- `PUT /api/discovery/filters` — upsert via `pg_insert().on_conflict_do_update(index_elements=['user_id'])` (D-10)
- `GET /api/discovery/matches` — JOIN with Tender for denormalized fields; WHERE `user_id = current_user.id` (T-07-03)
- `POST /api/discovery/{match_id}/participate` — IDOR WHERE + 404 on mismatch (T-07-01); lazy import `create_discovery_draft`; 409 on repeated action
- `POST /api/discovery/{match_id}/skip` — IDOR WHERE + 404 on mismatch (T-07-02); 409 if already skipped

**`main.py`:** registered `discovery.router` under `/api` prefix.

**`test_discovery_filters.py`:** 5/5 pass (PUT create, GET, upsert replaces, 404 on fresh user, 401 on unauth).

**`test_discovery_matches.py`:** 5/5 pass:
1. IDOR: User A's `GET /matches` does not include User B's matches
2. Participate on other user's match → 404 (T-07-01)
3. Skip on other user's match → 404 (T-07-02)
4. Valid participate → ApplicationResponse (draft), match.status = 'participating'
5. Valid skip → `{"ok": True}`, match.status = 'skipped'

---

## Verification Results

| Check | Result |
|-------|--------|
| `from app.routers.discovery import router; from app.main import app` | OK |
| `from app.services.matching_service import match_tenders_for_user` | OK |
| `from app.workers.tasks.run_matching import run_matching` | OK |
| `WorkerSettings.functions` | `[auto_submit_application, run_matching]` |
| `len(WorkerSettings.cron_jobs)` | 2 |
| `grep "run_matching" worker_settings.py` in functions | CONFIRMED |
| `grep "poll_goszakup_discovery" worker_settings.py` in cron_jobs | CONFIRMED |
| IDOR WHERE clauses in discovery.py | CONFIRMED (5 occurrences) |
| `test_matching_service.py` | 10/10 passed |
| `test_discovery_filters.py` | 5/5 passed |
| `test_discovery_matches.py` | 5/5 passed |
| Total tests | 20/20 passed |

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] TDD test fixture: `ClientFilter.__new__` bypasses SQLAlchemy metaclass**
- **Found during:** TDD RED to GREEN transition
- **Issue:** Using `ClientFilter.__new__(ClientFilter)` then setting attributes raised `AttributeError: 'ClientFilter' object has no attribute '_sa_instance_state'` — SQLAlchemy ORM objects require metaclass initialization via `__init__`.
- **Fix:** Replaced with `types.SimpleNamespace(**kwargs)` for in-memory filter config (plan allows "mock or test DB session"); match_tenders_for_user only reads attributes from cf.
- **Files modified:** `backend/tests/test_matching_service.py`
- **Commit:** `74e4474`

**2. [Rule 1 - Bug] TDD test: pytest-asyncio 1.3.0 event loop conflict with real DB sessions**
- **Found during:** TDD GREEN testing
- **Issue:** Alternating tests (1,3,5,7,9 pass; 2,4,6,8,10 fail) with "RuntimeError: Task attached to a different loop" when using `AsyncSessionLocal()` directly in test functions. Caused by pytest-asyncio 1.3.0 function-scoped event loops + asyncpg connection state.
- **Fix:** Switched to AsyncMock session strategy (plan explicitly allows "mock or test DB session"). Each test mocks `session.execute()` to return pre-built tender objects; validates that match_tenders_for_user passes correct WHERE clauses to the session.
- **Files modified:** `backend/tests/test_matching_service.py`
- **Commit:** `74e4474`

**3. [Rule 2 - Missing critical] test_discovery_matches.py: `create_discovery_draft` not yet in application_service.py**
- **Found during:** Task 2 test writing
- **Issue:** `patch("app.services.application_service.create_discovery_draft")` raised `AttributeError: module ... does not have the attribute 'create_discovery_draft'` because this function is created by plan 07-04 running in parallel.
- **Fix:** Added `create=True` to the `patch()` call. This allows patching a non-existent attribute for test isolation. The attribute will exist at production runtime when both 07-03 and 07-04 are merged.
- **Files modified:** `backend/tests/test_discovery_matches.py`
- **Commit:** `198d289`

---

## Known Stubs

None — all endpoints return real data from the DB. The `create_discovery_draft` function (imported lazily in the participate endpoint) will be provided by plan 07-04 at merge time.

---

## Threat Surface Scan

All STRIDE threats from the plan's threat model are mitigated as specified:

| Threat ID | Mitigation Applied |
|-----------|-------------------|
| T-07-01 | `WHERE id=match_id AND user_id=current_user.id` in participate endpoint; returns 404 on mismatch |
| T-07-02 | Same pattern in skip endpoint |
| T-07-03 | `WHERE user_id = current_user.id` in GET matches; user_id never from request body |
| T-07-ilike | SQLAlchemy parameterized queries; no SQL injection risk; accepted |

No new threat surface introduced beyond the plan's threat model.

## Self-Check: PASSED

Files exist:
- `backend/app/services/matching_service.py` — FOUND
- `backend/app/workers/tasks/run_matching.py` — FOUND
- `backend/app/routers/discovery.py` — FOUND
- `backend/tests/test_matching_service.py` — FOUND
- `backend/tests/test_discovery_filters.py` — FOUND
- `backend/tests/test_discovery_matches.py` — FOUND

Commits exist:
- `eafdd6a` test(07-03): TDD RED — FOUND
- `74e4474` feat(07-03): Task 1 — FOUND
- `198d289` feat(07-03): Task 2 — FOUND

Tests: 20/20 passed
