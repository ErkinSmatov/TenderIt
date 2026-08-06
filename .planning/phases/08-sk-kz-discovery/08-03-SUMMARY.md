---
phase: 08-sk-kz-discovery
plan: "03"
subsystem: backend/workers+tests
tags: [sk_kz, arq, cron, tests, respx, fakeredis]
dependency_graph:
  requires:
    - "backend/app/services/sk_kz_service.py (08-01)"
    - "backend/app/workers/tasks/poll_sk_kz_discovery.py (08-01)"
    - "backend/tests/test_goszakup_batch.py (analog — respx pattern)"
    - "backend/tests/test_poll_discovery.py (analog — fakeredis pattern)"
  provides:
    - "backend/app/workers/worker_settings.py — poll_sk_kz_discovery registered in cron_jobs"
    - "backend/tests/test_sk_kz_service.py — 5 unit tests for REST client"
    - "backend/tests/test_poll_sk_kz_discovery.py — 4 integration tests for ARQ cron task"
  affects:
    - "ARQ worker process (will now run poll_sk_kz_discovery every 15 min on restart)"
tech_stack:
  added: []
  patterns:
    - "respx.mock + side_effect capture for no-auth-header invariant testing"
    - "fakeredis.aioredis.FakeRedis + AsyncMock enqueue_job for ARQ task testing"
    - "patch target: app.workers.tasks.poll_sk_kz_discovery.fetch_sk_tenders_page / _upsert_tenders"
key_files:
  created:
    - backend/tests/test_sk_kz_service.py
    - backend/tests/test_poll_sk_kz_discovery.py
  modified:
    - backend/app/workers/worker_settings.py
decisions:
  - "Worktree reset to 1cf24db required — branch was spawned before wave 1 merges, git reset --hard applied per startup protocol to bring in 08-01 files"
  - "Test 5 (HTTP 500) accepts tenacity's 3-attempt retry delay (~3s) rather than mocking tenacity internals — simpler, confirms actual retry behavior"
  - "test_poll_uses_24h_lookback_on_first_run uses diff < 10s tolerance (not exact match) to avoid flaky failures from test execution timing"
metrics:
  duration: "~20min"
  completed: "2026-08-06T07:00:00Z"
  tasks_completed: 3
  tasks_total: 3
  files_created: 2
  files_modified: 1
---

# Phase 08 Plan 03: WorkerSettings Cron Registration + Full Test Suite Summary

**One-liner:** Registered poll_sk_kz_discovery as an ARQ cron job (every 15 min, unique=True) and wrote 9 tests covering the no-auth invariant, old-item filter, atomicity guarantee, and 24h lookback.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Register poll_sk_kz_discovery in WorkerSettings | bda540c | backend/app/workers/worker_settings.py |
| 2 | test_sk_kz_service.py — unit tests for REST client | 46acd14 | backend/tests/test_sk_kz_service.py |
| 3 | test_poll_sk_kz_discovery.py — cron task integration tests | 1418777 | backend/tests/test_poll_sk_kz_discovery.py |

## What Was Built

### `backend/app/workers/worker_settings.py` (modified)

Two changes:
1. Import line added: `from app.workers.tasks.poll_sk_kz_discovery import poll_sk_kz_discovery`
2. Cron entry added in `cron_jobs` list after `poll_goszakup_discovery`:
   ```python
   cron(poll_sk_kz_discovery, minute={0, 15, 30, 45}, unique=True)
   ```
3. Module docstring and inline comment updated to document the new cron job.

`WorkerSettings.cron_jobs` now has 3 entries: `poll_watchlist_tenders`, `poll_goszakup_discovery`, `poll_sk_kz_discovery`.

### `backend/tests/test_sk_kz_service.py` (new, 5 tests)

Unit tests for `fetch_sk_tenders_page` using `respx.mock`:
- `test_fetch_page_returns_recent_items` — 3 recent items returned
- `test_fetch_page_filters_old_items` — old item excluded; only 1 of 2 returned
- `test_fetch_page_empty_response` — empty array returns `[]`
- `test_fetch_page_sends_no_auth_header` — side_effect capture confirms `Authorization: NONE`
- `test_fetch_page_500_raises` — tenacity reraises `HTTPStatusError` after 3 attempts

### `backend/tests/test_poll_sk_kz_discovery.py` (new, 4 tests)

Integration tests for `poll_sk_kz_discovery` ARQ task using `fakeredis.aioredis.FakeRedis` + `AsyncMock`:
- `test_poll_sets_redis_key_after_success` — `sk_kz:last_polled_at` set to TZ-aware ISO string
- `test_poll_does_not_update_redis_on_upsert_error` — atomicity: key unchanged on `Exception("DB error")`
- `test_poll_uses_24h_lookback_on_first_run` — `since ≈ now - 24h` (diff < 10s, not 7 days)
- `test_poll_empty_response_does_not_enqueue` — Redis key updated but `enqueue_job` not called

## Deviations from Plan

### Worktree Base Reset (Startup Protocol)

**Found during:** Task 1 setup

**Issue:** Worktree branch `worktree-agent-ac1a373800780493f` was initialized from commit `5f816b7` (planning commit, before wave 1 merges). The expected base was `1cf24db` (post-wave-1 tracking update that includes 08-01 files). Without reset, `poll_sk_kz_discovery.py` was absent from the worktree's working tree — import verification failed with `ModuleNotFoundError`.

**Fix:** Applied `git reset --hard 1cf24dbec6401a3bfba8f336de2eb53a1e84d841` per startup protocol worktree_branch_check. Wave 1 files (sk_kz_service.py, poll_sk_kz_discovery.py) became available.

**Rule:** Startup protocol (not a deviation from plan logic).

## Known Stubs

None. All test files are complete implementations. `worker_settings.py` change is minimal and complete.

## Threat Surface Scan

No new security-relevant surface:
- T-08-08: `unique=True` implemented in the new `cron()` entry — prevents overlapping runs.
- Test files introduce no network endpoints, auth paths, or schema changes.

## Verification Results

```
pytest tests/test_sk_kz_service.py -x -v     → 5 passed
pytest tests/test_poll_sk_kz_discovery.py -x -v  → 4 passed
pytest tests/test_poll_discovery.py tests/test_goszakup_batch.py -x  → 10 passed (unaffected)
python3 -c "from app.workers.worker_settings import WorkerSettings; names=[j.coroutine.__name__ for j in WorkerSettings.cron_jobs]; assert 'poll_sk_kz_discovery' in names"  → OK
grep -c "poll_sk_kz_discovery" backend/app/workers/worker_settings.py  → 4 (import + cron entry + 2 comments)
```

## Self-Check

### Created Files

- `backend/tests/test_sk_kz_service.py` — FOUND
- `backend/tests/test_poll_sk_kz_discovery.py` — FOUND

### Modified Files

- `backend/app/workers/worker_settings.py` — FOUND (import + cron entry verified)

### Commits

- `bda540c` — chore(08-03): register poll_sk_kz_discovery in WorkerSettings
- `46acd14` — test(08-03): add unit tests for sk_kz_service REST client
- `1418777` — test(08-03): add integration tests for poll_sk_kz_discovery cron task

## Self-Check: PASSED
