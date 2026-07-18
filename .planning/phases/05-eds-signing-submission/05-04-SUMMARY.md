---
phase: 05-eds-signing-submission
plan: 04
subsystem: backend
tags: [arq, worker, telegram, auto-submit, redis, confirm-flow]
dependency_graph:
  requires: [05-01]
  provides: [auto-submission-engine, telegram-notification, confirm-flow]
  affects: [backend/app/workers, backend/app/routers/telegram_webhook.py, backend/app/main.py]
tech_stack:
  added: [python-telegram-bot==22.8]
  patterns: [ARQ cron job, ARQ delayed job, ARQ Retry backoff, Telegram webhook + set_webhook, IDOR mitigation via chat_id match]
key_files:
  created:
    - backend/app/workers/worker_settings.py
    - backend/app/workers/tasks/__init__.py
    - backend/app/workers/tasks/poll_watchlist.py
    - backend/app/workers/tasks/auto_submit.py
    - backend/app/services/telegram_service.py
    - backend/app/routers/telegram_webhook.py
    - backend/tests/test_poll_watchlist.py
    - backend/tests/test_auto_submit.py
    - backend/tests/test_confirm_flow.py
    - backend/tests/test_telegram_webhook.py
  modified:
    - backend/pyproject.toml
    - backend/app/config.py
    - backend/.env.example
    - backend/app/main.py
decisions:
  - "ARQ Redis in main.py lifespan: ArqRedis pool initialized on startup and stored in app.state.arq_redis for webhook handler enqueue"
  - "Telegram set_webhook guarded: only executed when settings.telegram_bot_token is non-empty — safe for local dev without a bot"
  - "enqueue_submit extracted as a function in telegram_webhook.py to allow clean mocking in tests"
  - "BACKOFF_SECONDS = [0, 30, 90, 180, 300, 600, 900]: 7 retries totalling ~35 min (T-05-34 cap)"
  - "auto_submit uses DB-only Application lookup (no user_id filter) because context is background job, not JWT auth; IDOR is enforced upstream in the webhook by chat_id check (T-05-30)"
metrics:
  duration: "18 minutes"
  completed_date: "2026-07-18"
  tasks_completed: 3
  tests_added: 18
  files_created: 10
  files_modified: 4
---

# Phase 05 Plan 04: Async Auto-Submission Engine Summary

**One-liner:** ARQ cron+job engine with Telegram Да/Нет confirmation, 15-min fallback submit, and durable retry backoff using python-telegram-bot 22.8.

## What Was Built

The durable auto-submission background layer for TenderIt's core value: "auto-submit the moment the tender opens."

### Components

**WorkerSettings** (`backend/app/workers/worker_settings.py`)
- `on_startup` creates async DB engine + sessionmaker into `ctx` (ARQ Pitfall #6 mitigation)
- `on_shutdown` disposes DB engine
- `cron_jobs`: `poll_watchlist_tenders` every 5 min, `unique=True`
- `functions`: `[auto_submit_application]`
- Invoked with: `python -m arq app.workers.worker_settings.WorkerSettings`

**poll_watchlist_tenders** (`backend/app/workers/tasks/poll_watchlist.py`)
- Queries all `status='waiting'` applications via `list_waiting_applications(session)`
- For each: fetches live tender status from goszakup GraphQL API
- On `status_id == 220` (OPEN_FOR_APPLICATIONS_STATUS_ID):
  1. `set_confirm_pending(redis, app.id)` — 900s TTL window
  2. `send_tender_notification(...)` — if `user.telegram_chat_id` and `UserWatchlist.notification_on`
  3. `mark_submitting(session, app)` — waiting → submitting transition
  4. `redis.enqueue_job("auto_submit_application", app.id, _defer_by=timedelta(minutes=15), _job_id=f"submit:{app.id}")`
- No crash when `telegram_chat_id` is None — fallback submit always enqueued

**auto_submit_application** (`backend/app/workers/tasks/auto_submit.py`)
- Checks `confirm:{app_id}` in Redis:
  - `"no"` → `mark_error("Cancelled by user")`, return
  - `"yes"` / `"pending"` / `None` (expired) → proceed
- Loads `goszakup_session:{user_id}` from Redis — missing → `Retry(defer=60)`
- Calls `GoszakupPortalClient.public_application(...)`:
  - `{"status": "ok"}` → `mark_submitted`
  - error → `Retry(defer=BACKOFF_SECONDS[job_try])` up to 7 tries (~35 min)
  - exhausted → `mark_error(message)` (T-05-34)
- Session secrets never logged (T-05-03)

**send_tender_notification** (`backend/app/services/telegram_service.py`)
- Builds `InlineKeyboardMarkup` with Да (`confirm:yes:{id}`) / Нет (`confirm:no:{id}`) buttons
- Uses `async with telegram.Bot(token): await bot.send_message(...)` — no persistent singleton

**POST /api/telegram/webhook** (`backend/app/routers/telegram_webhook.py`)
- Verifies `X-Telegram-Bot-Api-Secret-Token == settings.telegram_webhook_secret` → 403 otherwise (T-05-31)
- Parses `Update.de_json(body, bot=None)` from Telegram
- On `confirm:yes:{app_id}`:
  - IDOR check: `query.from_user.id` must match `app.user.telegram_chat_id` (T-05-30)
  - `update_confirm(redis, app_id, "yes")`
  - `enqueue_submit(redis, app_id)` with `_job_id=f"submit:{app_id}"` (T-05-32 dedup)
- On `confirm:no:{app_id}`: `update_confirm(redis, app_id, "no")`

**main.py lifespan updates**
- `ArqRedis.create(...)` on startup → stored as `app.state.arq_redis`
- Guarded `bot.set_webhook(...)` — only when `settings.telegram_bot_token` is non-empty

## Tests (18 total, all green)

| File | Tests | Coverage |
|------|-------|----------|
| `test_poll_watchlist.py` | 4 | status=220 → enqueue; no chat_id → no crash; non-220 → skip; empty list → noop |
| `test_auto_submit.py` | 5 | ok→submitted; confirm=no→cancel; error→Retry; exhausted→mark_error; missing session→Retry(60) |
| `test_confirm_flow.py` | 4 | APPL-09 branches: yes/no/expired/pending |
| `test_telegram_webhook.py` | 5 | 403 on bad secret; yes→enqueue; no→no enqueue; IDOR ignored; plain message ok |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] arq.Retry stores defer as `defer_score` (ms), not `defer` attribute**
- **Found during:** Task 2 test fix
- **Issue:** `Retry(defer=60).defer` raises `AttributeError`; actual field is `defer_score=60000`
- **Fix:** Updated test assertion to `assert exc_info.value.defer_score == 60 * 1000`
- **Files modified:** `backend/tests/test_auto_submit.py`
- **Commit:** 8131785

**2. [Rule 1 - Bug] Telegram `Message.de_json(bot=None)` requires `date` field**
- **Found during:** Task 3 test for plain message update
- **Issue:** Test payload missing `date` field caused `KeyError: 'date'` in PTB internals
- **Fix:** Added `"date": int(time.time())` to `_message_update()` helper
- **Files modified:** `backend/tests/test_telegram_webhook.py`
- **Commit:** 0df514e

**3. [Rule 3 - Blocking] Worker branch lacked 05-01 backend commits**
- **Found during:** Task 1 setup
- **Issue:** Worktree branch was created before 05-01 was merged — `application_service.py`, `redis_service.py` (Phase 5 helpers), `Application` model all missing
- **Fix:** `git merge master` on the worktree — fast-forward, no conflicts
- **Commit:** (pre-task merge, no separate commit)

## Threat Surface Scan

All mitigations from the plan's threat register are implemented:

| Threat | Mitigation Applied |
|--------|-------------------|
| T-05-30 (IDOR) | `query.from_user.id == owner.telegram_chat_id` check in webhook handler |
| T-05-31 (Spoofing) | `X-Telegram-Bot-Api-Secret-Token` header verified → 403 on mismatch |
| T-05-32 (Duplicate submit) | `_job_id=f"submit:{app_id}"` in both poll (15-min) and webhook (immediate) |
| T-05-33 (Session disclosure) | `phpsessid`/`csrf` never logged; only event logged |
| T-05-34 (Infinite retries) | `BACKOFF_SECONDS` capped at 7 tries → `mark_error` final |

No new threat surface introduced beyond the plan's trust boundaries.

## Self-Check: PASSED

- All 10 created files exist on disk
- All 5 task commits verified in git log: a382508, b88743f, 8131785, 0df514e, 0753b5a
- `from app.workers.worker_settings import WorkerSettings; from app.main import app` imports clean
- 18/18 tests pass
