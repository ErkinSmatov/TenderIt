---
phase: 7
phase_slug: discovery-matching
created: 2026-07-19
---

# Phase 7 — Discovery & Matching: Validation Strategy

## Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| Config file | `backend/pytest.ini` |
| Quick run | `cd backend && pytest tests/test_matching_service.py -x` |
| Full suite | `cd backend && pytest tests/ -x` |
| Mock library | respx 0.23.1 (goszakup HTTP), fakeredis (Redis) |
| Frontend | `cd frontend && npx tsc --noEmit && npx next build` |

## Requirements → Test Map

| Req ID | Behavior | Test Type | File |
|--------|----------|-----------|------|
| DISC-01 | PUT /api/discovery/filters upserts; second PUT replaces | integration | `tests/test_discovery_filters.py` |
| DISC-01 | GET /api/discovery/filters returns current filter set | integration | `tests/test_discovery_filters.py` |
| DISC-02 | `fetch_tenders_batch` calls goszakup with lastUpdateDate + paginates | unit (respx) | `tests/test_goszakup_batch.py` |
| DISC-02 | `poll_goszakup_discovery` writes `last_polled_at` to Redis | unit (fakeredis) | `tests/test_poll_discovery.py` |
| DISC-03 | `match_tenders_for_user` returns tender when keyword ILIKE matches `name_ru` | unit | `tests/test_matching_service.py` |
| DISC-03 | `match_tenders_for_user` respects region exact-match | unit | `tests/test_matching_service.py` |
| DISC-03 | `match_tenders_for_user` respects amount range | unit | `tests/test_matching_service.py` |
| DISC-03 | ON CONFLICT (user_id, tender_id) DO NOTHING prevents duplicates | integration | `tests/test_matching_service.py` |
| DISC-04 | GET /api/discovery/matches returns only current user's matches (IDOR) | integration | `tests/test_discovery_matches.py` |
| DISC-05 | `disc:participate:{match_id}` from wrong chat_id is silently ignored | integration | `tests/test_telegram_disc_webhook.py` |
| DISC-05 | `disc:participate:{match_id}` creates Application with status=draft | integration | `tests/test_telegram_disc_webhook.py` |
| DISC-05 | `disc:skip:{match_id}` sets match status=skipped | integration | `tests/test_telegram_disc_webhook.py` |
| DISC-05 | `create_discovery_draft` creates Application with empty lots_data | unit | `tests/test_application_service.py` |

## Wave 0 Test Files (create before implementation)

- [ ] `tests/test_matching_service.py` — unit, no DB, mock Tender objects
- [ ] `tests/test_goszakup_batch.py` — respx mocks for batch endpoint
- [ ] `tests/test_poll_discovery.py` — integration with fakeredis
- [ ] `tests/test_discovery_filters.py` — CRUD integration tests
- [ ] `tests/test_discovery_matches.py` — IDOR integration tests
- [ ] `tests/test_telegram_disc_webhook.py` — webhook handler tests (extend existing test_telegram_webhook.py pattern)

## Security Validation

| Threat | Test | Plan |
|--------|------|------|
| T-07-01 IDOR /participate | User A cannot participate in User B's match → 404 | 07-03/07-04 |
| T-07-02 IDOR /skip | User A cannot skip User B's match → 404 | 07-03 |
| T-07-03 Info disclosure | GET /matches never leaks other user's data | 07-03 |
| T-07-04 Rate limit poll | asyncio.sleep(0.5) between pages + tenacity retry | 07-02 |
| T-07-05 Telegram spoofing | HMAC check inherited from existing webhook router | 07-04 |

## Acceptance (Phase Complete when ALL TRUE)

1. `cd backend && pytest tests/ -x` — 0 failures, ≥ 13 new tests covering DISC-01..05
2. `cd frontend && npx tsc --noEmit` — exits 0
3. `cd frontend && npx next build` — exits 0
4. Human checkpoint (07-06): /discovery feed visible, filter settings save/load, "Участвуем" creates application
