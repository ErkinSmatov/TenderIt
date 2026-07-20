---
phase: "07-discovery-matching"
plan: "04"
subsystem: "backend"
tags: ["telegram", "webhook", "application-service", "disc-callbacks", "idor", "tdd"]
dependency_graph:
  requires:
    - "07-01"  # TenderMatch ORM model (created in Wave 1)
  provides:
    - "create_discovery_draft — Application ORM bypass of Pydantic lots validator"
    - "send_discovery_notification — Telegram card with disc:participate/disc:skip buttons"
    - "disc:* webhook handlers with IDOR protection"
  affects:
    - "backend/app/services/application_service.py"
    - "backend/app/services/telegram_service.py"
    - "backend/app/routers/telegram_webhook.py"
tech_stack:
  added: []
  patterns:
    - "TDD RED→GREEN for create_discovery_draft"
    - "AsyncMock-based unit testing for service functions that commit internally"
    - "Telegram InlineKeyboardMarkup with disc: callback_data prefix (D-04)"
    - "IDOR protection via telegram_chat_id comparison (mirrors T-05-30 pattern)"
key_files:
  created:
    - "backend/tests/test_application_service.py — 5 unit tests (TDD)"
    - "backend/tests/test_telegram_disc_webhook.py — 6 integration tests"
  modified:
    - "backend/app/services/application_service.py — create_discovery_draft appended"
    - "backend/app/services/telegram_service.py — send_discovery_notification appended"
    - "backend/app/routers/telegram_webhook.py — guard updated + disc:* block added"
decisions:
  - "Used AsyncMock for DB session in unit tests (create_discovery_draft commits internally, breaking the rollback-based db_session fixture)"
  - "Wrapped entire confirm: block inside if parts[0] == 'confirm': to safely add elif parts[0] == 'disc': as a peer branch"
  - "answer_callback_query wrapped in try/except — non-fatal, prevents spinner from blocking user"
metrics:
  duration: "~25 min"
  completed_date: "2026-07-20"
  tasks_completed: 2
  files_changed: 5
---

# Phase 07 Plan 04: Discovery Telegram Integration Summary

**One-liner:** Telegram disc:participate/disc:skip interaction loop with IDOR-guarded handlers and ORM-bypass Application draft creation.

## What Was Built

### Task 1: create_discovery_draft (TDD RED → GREEN)

Added `create_discovery_draft(db, user_id, tender_id)` to `backend/app/services/application_service.py`.

**Critical design decision (Research pitfall 1 / D-05):** The existing `ApplicationCreate` Pydantic schema has a `@field_validator("lots_data")` that raises `ValueError` for empty lists. The Telegram "Участвуем" handler cannot call `create_application()` with `lots_data=[]`. This new function constructs the `Application` ORM object directly, bypassing schema validation. Lots are filled later via the wizard.

5 unit tests (all passing):
- `test_create_discovery_draft_status` — result.status == 'draft'
- `test_create_discovery_draft_lots_empty` — result.lots_data == []
- `test_create_discovery_draft_tender_id` — correct tender_id
- `test_create_discovery_draft_user_id` — correct user_id
- `test_application_create_validator_rejects_empty_lots` — **REGRESSION GUARD**: confirms the validator still exists on ApplicationCreate

### Task 2: send_discovery_notification + disc:* handlers

**telegram_service.py:** Added `send_discovery_notification()` with:
- Formatted tender card (name, customer, amount, deadline, region)
- `InlineKeyboardMarkup` with `disc:participate:{match_id}` and `disc:skip:{match_id}` buttons (D-04)
- Caller must guard: `if user.telegram_chat_id is None: return` (D-03)

**telegram_webhook.py changes:**
1. Added imports: `TenderMatch`, `create_discovery_draft`, `datetime`, `timezone`
2. Added `get_tender_match_by_id(db, match_id)` helper (same IDOR pattern as `get_application_by_id`)
3. **Guard fixed** (Research pitfall 2): `parts[0] != "confirm"` → `parts[0] not in ("confirm", "disc")`
4. Wrapped existing confirm block in `if parts[0] == "confirm":` to enable safe peer `elif parts[0] == "disc":` branch
5. `disc:participate` handler: IDOR check → `create_discovery_draft()` → `match.status = "participating"` → `db.commit()` → `answer_callback_query()`
6. `disc:skip` handler: IDOR check → `match.status = "skipped"` → `db.commit()` → `answer_callback_query()`

6 integration tests (all passing):
- `test_disc_prefix_accepted` — disc:* passes the updated guard
- `test_disc_participate_idor` — wrong chat_id → silently ignored, no Application created (T-07-01)
- `test_disc_skip_idor` — wrong chat_id → match status unchanged (T-07-02)
- `test_disc_participate_creates_draft` — correct owner → Application created, match=participating
- `test_disc_skip_sets_skipped` — correct owner → match=skipped
- `test_secret_token_required` — 403 without secret (T-05-31 still applies)

All 5 existing `test_telegram_webhook.py` confirm:* tests still pass (no regression).

## Commits

| Hash | Type | Description |
|------|------|-------------|
| `ad6624f` | test | TDD RED — failing tests for create_discovery_draft |
| `8e65380` | feat | create_discovery_draft implementation (GREEN) |
| `bb9ec73` | feat | send_discovery_notification + disc:* handlers + 6 tests |

## Deviations from Plan

None — plan executed exactly as written.

The only implementation note: wrapped existing `confirm:` dispatch in `if parts[0] == "confirm":` block (a necessary structural change to enable the peer `elif parts[0] == "disc":` block). The plan said "add elif block after confirm actions" — this is the correct implementation of that intent.

## Known Stubs

None. All functions are fully implemented with real logic.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced beyond what the plan's threat model documented. The `disc:*` handlers use the same Telegram webhook endpoint (`POST /api/telegram/webhook`) already covered by T-05-31. IDOR mitigations T-07-01 and T-07-02 are implemented as specified.

## Self-Check

### Files exist:
- `backend/app/services/application_service.py` — modified
- `backend/app/services/telegram_service.py` — modified
- `backend/app/routers/telegram_webhook.py` — modified
- `backend/tests/test_application_service.py` — created
- `backend/tests/test_telegram_disc_webhook.py` — created

### Commits exist:
- ad6624f — test(07-04): add failing tests for create_discovery_draft (TDD RED)
- 8e65380 — feat(07-04): implement create_discovery_draft — Task 1
- bb9ec73 — feat(07-04): send_discovery_notification + disc:* webhook handlers — Task 2

## Self-Check: PASSED
