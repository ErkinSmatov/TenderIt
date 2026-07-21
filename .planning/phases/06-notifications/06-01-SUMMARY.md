---
phase: 06-notifications
plan: "01"
subsystem: backend
tags: [telegram, notifications, deep-link, webhook, auth, migration]
dependency_graph:
  requires:
    - "05-07 (telegram_webhook.py + User.telegram_chat_id)"
    - "alembic 0007 (down_revision)"
  provides:
    - "User.telegram_link_token + telegram_link_token_expires_at ORM fields"
    - "Migration 0008 (add telegram link-token columns to users)"
    - "POST /api/notifications/telegram/link-token endpoint"
    - "GET /api/notifications/status endpoint"
    - "DELETE /api/notifications/telegram endpoint"
    - "_handle_start_command webhook handler"
  affects:
    - "Phase 7 ARQ workers (user.telegram_chat_id is now populated by linking flow)"
    - "Plan 06-02 frontend (polls /api/notifications/status)"
tech_stack:
  added:
    - "secrets.token_urlsafe(32) — 256-bit entropy link tokens"
  patterns:
    - "TDD RED/GREEN cycle (test first, implement to pass)"
    - "JWT-gated endpoints via Depends(get_current_user)"
    - "Alembic op.add_column + op.create_index (unique=True) pattern"
    - "Timezone-aware datetime comparison: datetime.now(timezone.utc)"
key_files:
  created:
    - "backend/alembic/versions/0008_add_telegram_link_token.py"
    - "backend/app/routers/notifications.py"
    - "backend/tests/test_notifications.py"
  modified:
    - "backend/app/models/user.py"
    - "backend/app/config.py"
    - "backend/app/main.py"
    - "backend/app/routers/telegram_webhook.py"
decisions:
  - "D-09: telegram_bot_username added to Settings with empty default — deep_link is broken in dev but non-fatal; production sets TELEGRAM_BOT_USERNAME env var"
  - "GET /notifications/status does NOT take db dependency — get_current_user already loads User; avoids redundant DB call"
  - "_handle_start_command checks text.startswith('/start ') with trailing space — prevents plain /start from triggering DB lookup (Pitfall 1)"
  - "Task 3 webhook tests patch _handle_start_command directly to avoid live DB setup complexity"
metrics:
  duration: "5 min 5 sec (07:43:33Z to 07:48:38Z)"
  completed_date: "2026-07-21"
  tasks_completed: 3
  files_created: 3
  files_modified: 4
---

# Phase 06 Plan 01: Telegram Account Linking Backend Summary

**One-liner:** Telegram deep-link linking flow (NOTIF-04) — migration 0008, 3 JWT-gated endpoints, `/start TOKEN` webhook handler — sets `telegram_chat_id` that Phase 7 ARQ workers guard on.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Migration 0008 + User model + config | `1921661` | 0008_add_telegram_link_token.py, models/user.py, config.py |
| 2 (RED) | Failing tests for notifications endpoints | `44ddf85` | tests/test_notifications.py |
| 2 (GREEN) | Notifications router + main.py registration | `640307d` | routers/notifications.py, main.py |
| 3 (GREEN) | telegram_webhook.py _handle_start_command + dispatch | `a2ca793` | routers/telegram_webhook.py |

## Verification Results

```
163 passed, 3 skipped, 0 failed
```

- `test_notifications.py`: 10/10 passed
- `test_telegram_webhook.py`: 5/5 passed (existing tests unaffected)
- `alembic upgrade 0008 → downgrade → upgrade`: all exits 0

### NOTIF-04 Coverage

| Requirement | Test | Status |
|-------------|------|--------|
| POST link-token → deep_link | `test_create_link_token` | PASS |
| GET status (not connected) | `test_get_status_not_connected` | PASS |
| DELETE disconnect | `test_disconnect` | PASS |
| Webhook /start dispatch | `test_webhook_start_links_telegram` | PASS |
| Webhook secret guard preserved | `test_webhook_rejects_wrong_secret` | PASS |
| Expired token rejects | `test_expired_token_does_not_set_chat_id` | PASS |

## Acceptance Criteria Verified

- `_handle_start_command` uses `text.startswith("/start ")` with trailing space (mandatory)
- No `text.split()[1]` usage (would IndexError on plain `/start`)
- No `datetime.utcnow()` usage (always `datetime.now(timezone.utc)`)
- `secrets.token_urlsafe(32)` produces 43-char URL-safe tokens (T-06-01)
- Token cleared on use (T-06-02 replay prevention)
- `DELETE /notifications/telegram` clears `telegram_chat_id` AND `telegram_link_token`
- No WhatsApp/Twilio code (D-01 honored)
- `main.py`: `include_router(notifications.router, prefix="/api", tags=["notifications"])`

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all endpoints wire to real DB via SQLAlchemy ORM.

## Threat Flags

No new threat surface beyond the plan's `<threat_model>`. All T-06-01 through T-06-06 mitigations implemented:
- T-06-01: `secrets.token_urlsafe(32)` + unique DB index
- T-06-02: token cleared on first use
- T-06-03: `get_current_user` dep, no user_id in request body
- T-06-04: `_handle_start_command` runs after T-05-31 secret guard (inherited)
- T-06-05: timezone-aware expiry comparison

## TDD Gate Compliance

- RED gate: `test(06-01)` commit `44ddf85` — 10 tests failing (notifications router missing)
- GREEN gate: `feat(06-01)` commit `640307d` (notifications router) + `a2ca793` (webhook handler)
- All tests pass in GREEN state

## Self-Check: PASSED

All 8 expected files found. All 4 task commits verified in git log.
