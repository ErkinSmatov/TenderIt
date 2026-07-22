---
phase: 06-notifications
verified: 2026-07-22T06:00:00Z
status: passed
score: 12/12 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 12/14
  gaps_closed:
    - "WhatsApp/NOTIF-05 gap (previous truth 13): FALSE POSITIVE — ROADMAP Phase 6 has no WhatsApp success criterion. SC-1=Telegram connect, SC-2=Watchlist remove. NOTIF-05 is explicitly noted as deferred to v2 in ROADMAP Phase 6 header note. No WhatsApp must-have ever existed for this phase."
    - "Enable/disable watchlist gap (previous truth 14): FALSE POSITIVE — ROADMAP Phase 6 SC-2 says 'remove entries' (not 'enable/disable/remove'). D-02 in 06-CONTEXT.md (LOCKED) restricts Phase 6 scope to delete-only. The implementation matches the ROADMAP contract exactly."
  gaps_remaining: []
  regressions: []
---

# Phase 6: Notifications — Verification Report (Re-verification)

**Phase Goal:** Users can connect Telegram to receive tender-status notifications and manage their watchlist from a dedicated settings page.
**Verified:** 2026-07-22
**Status:** PASSED
**Re-verification:** Yes — previous gaps_found status was based on two false-positive gaps

---

## Re-verification Summary

Previous verification (2026-07-22) reported `gaps_found` (12/14). Both gaps were false positives caused by reading success criteria that do not exist in the current ROADMAP:

- **Previous gap 1** ("WhatsApp ROADMAP SC-2"): ROADMAP Phase 6 has only 2 success criteria; neither mentions WhatsApp. The ROADMAP header note for Phase 6 explicitly says `NOTIF-05 (WhatsApp/Twilio) deferred to v2`. The previous verifier invented a "SC-2 WhatsApp" that was never in the ROADMAP text.
- **Previous gap 2** ("enable/disable ROADMAP SC-3"): ROADMAP Phase 6 has no SC-3. SC-2 says "remove entries" — exactly what WatchlistSettingsTable implements. D-02 (LOCKED) excluded toggle from Phase 6 scope before planning.

Both gaps close as FALSE POSITIVE. No implementation changes required or made.

All 12 actual must-haves from both PLANs and both ROADMAP SCs are VERIFIED against actual code.

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | POST /api/notifications/telegram/link-token returns {deep_link: 'https://t.me/{BOT}?start={43-char-token}'} | VERIFIED | `notifications.py` line 43: `secrets.token_urlsafe(32)`; line 50: f-string with settings.telegram_bot_username; `test_create_link_token`: `len(token) == 43` passes |
| 2 | GET /api/notifications/status returns {telegram_connected: bool, telegram_chat_id: int\|null} | VERIFIED | `notifications.py` lines 54–66: returns dict with exact keys; `test_get_status_not_connected` passes |
| 3 | DELETE /api/notifications/telegram → 204, clears telegram_chat_id and telegram_link_token | VERIFIED | `notifications.py` lines 79–83: sets all 3 fields to None + commit; `test_disconnect` passes |
| 4 | Telegram webhook /start VALID_TOKEN sets user.telegram_chat_id = message.from_user.id, clears link token | VERIFIED | `telegram_webhook.py` lines 161–165: `user.telegram_chat_id = chat_id`, clears both token fields, commits; `test_webhook_start_links_telegram` asserts handler called once |
| 5 | Telegram webhook /start EXPIRED_TOKEN replies "Ссылка устарела", does NOT set telegram_chat_id | VERIFIED | `telegram_webhook.py` lines 149–159: timezone-aware expiry check; `test_expired_token_does_not_set_chat_id` asserts `telegram_chat_id is None` and bot message contains "устарела" |
| 6 | All tests in test_notifications.py pass; full backend suite green | VERIFIED | `python3 -m pytest tests/test_notifications.py`: 10 passed (exceeds plan minimum of 6); `python3 -m pytest`: 163 passed, 3 skipped, 0 failed |
| 7 | User can navigate to /settings/notifications via Bell "Настройки" in Sidebar | VERIFIED | `Sidebar.tsx` line 5: Bell in import; line 18: `{ href: '/settings/notifications', label: 'Настройки', icon: Bell }` in navItems |
| 8 | TelegramConnectCard shows "Подключить Telegram" button when telegram_connected is false | VERIFIED | `TelegramConnectCard.tsx` line 113: renders button in `!status?.telegram_connected && !deepLink` branch |
| 9 | After clicking connect: deep-link button + "Ожидание подключения..." + 3s polling auto-detects connection | VERIFIED | `TelegramConnectCard.tsx` lines 27–34: refetchInterval returns 3000 when `pollingActive && !telegram_connected`; lines 122–140: "Открыть Telegram" anchor + "Ожидание подключения..." with animate-pulse indicator |
| 10 | TelegramConnectCard shows "Telegram подключён ✓" + "Отключить" when telegram_connected is true | VERIFIED | `TelegramConnectCard.tsx` lines 97–111: connected branch shows "Telegram подключён ✓" (text-green-600) + disconnect button |
| 11 | WatchlistSettingsTable renders rows with number_anno, tender name, status, and "Удалить" button | VERIFIED | `WatchlistSettingsTable.tsx` lines 74–114: renders `entry.tender.name_ru ?? entry.tender.number_anno`, `number_anno` in font-mono, `status_name_ru`, Trash2 + "Удалить" button per row |
| 12 | Clicking "Удалить" calls DELETE /api/watchlist/{number_anno} and removes row via cache invalidation | VERIFIED | `WatchlistSettingsTable.tsx` line 34: `api.delete('/api/watchlist/${numberAnno}')` in mutationFn; line 40: `invalidateQueries({ queryKey: ['watchlist'] })` on success |

**Score:** 12/12 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/alembic/versions/0008_add_telegram_link_token.py` | Migration: telegram_link_token (String 64, unique) + telegram_link_token_expires_at (TIMESTAMP tz) | VERIFIED | revision="0008", down_revision="0007"; op.add_column x2 + op.create_index(unique=True); sa.TIMESTAMP(timezone=True) |
| `backend/app/models/user.py` | User ORM extended with telegram_link_token + telegram_link_token_expires_at | VERIFIED | Lines 25–30: Mapped[Optional[str]] String(64) unique+index; Mapped[Optional[datetime]] sa.TIMESTAMP(timezone=True) |
| `backend/app/config.py` | Settings.telegram_bot_username added | VERIFIED | telegram_bot_username: str = "" present; Phase 6 D-09 comment above it |
| `backend/app/routers/notifications.py` | 3 JWT-gated endpoints (link-token, status, delete) | VERIFIED | Full implementation; secrets.token_urlsafe(32); datetime.now(timezone.utc) + timedelta; no db dep on GET status |
| `backend/app/main.py` | notifications router registered with prefix="/api" | VERIFIED | Line 17: `from app.routers import notifications`; line 86: `include_router(notifications.router, prefix="/api", tags=["notifications"])` |
| `backend/app/routers/telegram_webhook.py` | _handle_start_command added before @router.post; dispatch branch before early return | VERIFIED | Lines 108–170: _handle_start_command with trailing-space guard (`/start ` with space), timezone-aware expiry, token-replay prevention; line 202: dispatch pre-filter + handler call |
| `backend/tests/test_notifications.py` | Tests covering NOTIF-04 behaviors | VERIFIED | 10 tests total: 6 endpoint tests (T-06-01..06) + 4 webhook tests (T-06-07..10); all 10 pass |
| `frontend/src/components/notifications/TelegramConnectCard.tsx` | Connect/disconnect/polling with v5 refetchInterval | VERIFIED | 'use client'; refetchInterval uses `(query) =>` form (v5); pollingActive referenced 4 times; no `(data, error)` v4 syntax; no "whatsapp" string |
| `frontend/src/components/notifications/WatchlistSettingsTable.tsx` | Watchlist table with delete mutation; shared ['watchlist'] cache key | VERIFIED | 'use client'; queryKey ['watchlist']; `api.delete('/api/watchlist/${numberAnno}')` in mutationFn; Trash2 + "Удалить"; onError handler (WR-04 applied); deletingId per-row tracking |
| `frontend/src/app/(dashboard)/settings/notifications/page.tsx` | Page rendering TelegramConnectCard then WatchlistSettingsTable | VERIFIED | Line 15: `<TelegramConnectCard />`; line 16: `<WatchlistSettingsTable />`; space-y-6 max-w-2xl shell; no QueryClientProvider |
| `frontend/src/components/layout/Sidebar.tsx` | Bell icon + settings/notifications nav item | VERIFIED | Line 5: Bell in import; line 18: `{ href: '/settings/notifications', label: 'Настройки', icon: Bell }` |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `notifications.py` | `models/user.py` | current_user.telegram_link_token written via SQLAlchemy ORM + await db.commit() | VERIFIED | Lines 44–48: token + expires_at assigned to current_user; db.commit() at line 48 |
| `telegram_webhook.py` | `models/user.py` | _handle_start_command: user.telegram_chat_id = chat_id after token validation | VERIFIED | Line 162: `user.telegram_chat_id = chat_id` inside success branch; token fields cleared; db.commit() at line 165 |
| `main.py` | `notifications.py` | include_router(notifications.router, prefix="/api", tags=["notifications"]) | VERIFIED | Line 86: exact match |
| `page.tsx` | `TelegramConnectCard.tsx` | renders `<TelegramConnectCard />` as first section | VERIFIED | Line 15: `<TelegramConnectCard />` before `<WatchlistSettingsTable />` |
| `TelegramConnectCard.tsx` | `GET /api/notifications/status` | useQuery with refetchInterval polling every 3s when pollingActive | VERIFIED | Lines 26–34: queryFn fetches /api/notifications/status; refetchInterval returns 3000 when `pollingActive && !query.state.data?.telegram_connected` |
| `WatchlistSettingsTable.tsx` | `DELETE /api/watchlist/{number_anno}` | useMutation mutationFn + onSuccess invalidateQueries(['watchlist']) | VERIFIED | Lines 33–48: mutationFn calls api.delete; onSuccess invalidates ['watchlist'] cache |
| `Sidebar.tsx` | `/settings/notifications` | Bell nav item in navItems array | VERIFIED | Line 18: href navigates to /settings/notifications; Bell icon renders in nav loop |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `TelegramConnectCard.tsx` | `status` (NotificationStatus) | GET /api/notifications/status → notifications.py → current_user.telegram_chat_id from ORM (get_current_user dep loads full User row) | Yes — real DB row via SQLAlchemy | FLOWING |
| `WatchlistSettingsTable.tsx` | `entries` (WatchlistEntry[]) | GET /api/watchlist → tenders.py existing endpoint → SQLAlchemy query (established in Phase 3/5) | Yes — real DB query | FLOWING |
| `notifications.py` POST link-token | `token` + `deep_link` | secrets.token_urlsafe(32) → stored to DB → f-string URL with settings.telegram_bot_username | Yes — writes to DB; returns computed URL | FLOWING |
| `telegram_webhook.py` _handle_start_command | `user` (User ORM) | `db.execute(select(User).where(User.telegram_link_token == token))` | Yes — real DB query; no hardcoded returns | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| POST link-token returns 200 with 43-char token | `python3 -m pytest tests/test_notifications.py::test_create_link_token -v` | 1 passed | PASS |
| POST without JWT → 401 | `python3 -m pytest tests/test_notifications.py::test_link_token_unauthenticated -v` | 1 passed | PASS |
| GET status not connected → telegram_connected false | `python3 -m pytest tests/test_notifications.py::test_get_status_not_connected -v` | 1 passed | PASS |
| Expired token does not set chat_id | `python3 -m pytest tests/test_notifications.py::test_expired_token_does_not_set_chat_id -v` | 1 passed | PASS |
| All test_notifications.py tests | `python3 -m pytest tests/test_notifications.py -x -q` | 10 passed | PASS |
| Full backend suite | `python3 -m pytest -x -q` | 163 passed, 3 skipped, 0 failed | PASS |
| TypeScript compilation | `npx tsc --noEmit` | exit 0, no output | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| NOTIF-04 | 06-01-PLAN.md | Пользователь может подключить Telegram через /start с привязкой к аккаунту | SATISFIED | 3 JWT endpoints + _handle_start_command + 10 passing tests. ROADMAP SC-1 fully met. |
| NOTIF-05 | — | WhatsApp/Twilio — deferred to v2 per D-01 (LOCKED) | DEFERRED — NOT a Phase 6 gap | ROADMAP Phase 6 header note: "NOTIF-05 (WhatsApp/Twilio) deferred to v2". No Phase 6 SC covers WhatsApp. |
| NOTIF-06 | 06-02-PLAN.md | Пользователь может просмотреть и управлять watchlist | SATISFIED (Phase 6 scope) | View ✓; Delete ✓. D-02 LOCKED: delete-only. ROADMAP SC-2 says "remove entries" — matched exactly. |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | No TBD/FIXME/XXX markers found in any phase-modified file | — | — |

No stub implementations. No hardcoded empty data in rendering components. No `datetime.utcnow()` usage. No `(data, error)` v4 refetchInterval syntax.

Post-review fixes applied and committed (WR-01 timeout cleanup, WR-02 dispatch alignment, WR-04 onError handler, CR-01/02/03 security fixes) — all confirmed in git log.

---

## Human Verification

Human-verify checkpoint was Plan 06-02 Task 3 (blocking gate). Completed during original execution:

- **Result:** PASSED — user responded "approved" (commit `d2b1dfb`: "test(06-02): human verification passed — UI approved (NOTIF-06)")
- Sidebar Bell "Настройки" entry verified
- TelegramConnectCard connect/disconnect/polling flow verified
- WatchlistSettingsTable per-row delete verified

No additional human verification required.

---

## Gaps Summary

No gaps. Phase goal fully achieved.

The previous verification's two gaps were false positives:
1. WhatsApp was never a Phase 6 ROADMAP success criterion — it is explicitly deferred to v2.
2. "Enable/disable" watchlist was never in ROADMAP SC-2 ("remove entries") — D-02 LOCKED decision narrowed scope before planning and ROADMAP reflects that narrowing.

All 12 must-haves from ROADMAP SCs and both PLANs are VERIFIED against actual code.

**What is working:**
- Telegram deep-link flow: generate token → user opens bot → /start TOKEN → chat_id stored
- All 3 JWT-gated endpoints (POST link-token, GET status, DELETE disconnect)
- _handle_start_command: trailing-space guard, timezone-aware expiry, replay prevention, Telegram bot responses
- /settings/notifications page with TelegramConnectCard + WatchlistSettingsTable
- Sidebar Bell "Настройки" nav entry
- 3s polling that auto-detects telegram_connected → stops + clears state; 60s hard timeout
- Per-row watchlist delete with loading state, error feedback (WR-04)
- 10 backend tests all passing; TypeScript 0 errors; 163 total backend tests green
- Human verification approved (commit d2b1dfb)

---

_Verified: 2026-07-22_
_Verifier: Claude (gsd-verifier)_
_Re-verification: Yes — previous gaps_found (2 false positives) → passed_
