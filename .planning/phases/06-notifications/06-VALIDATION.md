---
phase: 6
slug: notifications
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-20
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (backend) + vitest/jest (frontend) |
| **Config file** | `backend/pyproject.toml` (pytest) / `frontend/package.json` (vitest) |
| **Quick run command** | `cd backend && python -m pytest tests/ -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ && cd ../frontend && npm run test` |
| **Estimated runtime** | ~30 seconds (backend), ~15 seconds (frontend) |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/ -x -q`
- **After every plan wave:** Run full suite (backend + frontend)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | NOTIF-04 | T-06-01 | Migration adds telegram_link_token, expires_at nullable | unit | `pytest tests/test_notifications.py::test_migration_fields` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | NOTIF-04 | T-06-02 | POST /notifications/telegram/link-token returns deep_link with token | unit | `pytest tests/test_notifications.py::test_link_token_generation` | ❌ W0 | ⬜ pending |
| 06-01-03 | 01 | 1 | NOTIF-04 | T-06-03 | /start TOKEN webhook sets telegram_chat_id, clears token | unit | `pytest tests/test_notifications.py::test_start_handler` | ❌ W0 | ⬜ pending |
| 06-01-04 | 01 | 1 | NOTIF-04 | T-06-04 | Expired token returns error message, does NOT set chat_id | unit | `pytest tests/test_notifications.py::test_expired_token` | ❌ W0 | ⬜ pending |
| 06-01-05 | 01 | 1 | NOTIF-04 | T-06-05 | GET /notifications/status returns correct telegram_connected state | unit | `pytest tests/test_notifications.py::test_status_endpoint` | ❌ W0 | ⬜ pending |
| 06-01-06 | 01 | 1 | NOTIF-04 | T-06-06 | DELETE /notifications/telegram clears chat_id (own user only) | unit | `pytest tests/test_notifications.py::test_disconnect` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 2 | NOTIF-06 | — | /settings/notifications renders TelegramConnectCard + WatchlistSettingsTable | manual | UI: visit /settings/notifications when logged in | — | ⬜ pending |
| 06-02-02 | 02 | 2 | NOTIF-06 | — | Watchlist delete removes entry from table | manual | UI: click Удалить on watchlist row | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_notifications.py` — stubs for NOTIF-04 test cases (link-token, start handler, status, disconnect)
- [ ] `backend/tests/conftest.py` — check if `async_session` fixture covers notifications tests (it should — existing pattern)

*Frontend tests: existing vitest setup covers component tests; no new Wave 0 needed for frontend.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Telegram deep-link flow end-to-end | NOTIF-04 | Requires real Telegram bot + real user account | 1. Visit /settings/notifications; 2. Click "Подключить Telegram"; 3. Follow deep link; 4. Send /start in bot; 5. Verify page shows "Подключён" |
| Watchlist settings page UI | NOTIF-06 | Visual verification of layout + responsive behavior | Visit /settings/notifications, verify both blocks render, test delete |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
