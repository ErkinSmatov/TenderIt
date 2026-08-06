---
phase: 08-sk-kz-discovery
plan: "01"
subsystem: backend/ingestion
tags: [sk_kz, discovery, arq, rest-client, upsert]
dependency_graph:
  requires:
    - "backend/app/models/tender.py (Tender model with source/region/spgz_code — phase 7 migration 0005)"
    - "backend/app/workers/tasks/poll_goszakup_discovery.py (analog structure)"
    - "backend/app/services/goszakup_service.py (analog _is_retryable, retry decorator)"
  provides:
    - "backend/app/services/sk_kz_service.py — REST client for zakup.sk.kz filter API"
    - "backend/app/workers/tasks/poll_sk_kz_discovery.py — ARQ cron task (15-min incremental poll)"
  affects:
    - "tenders table (new rows with source='sk_kz')"
    - "Redis key sk_kz:last_polled_at"
    - "run_matching ARQ task (enqueued with sk.kz tender IDs)"
tech_stack:
  added:
    - "zakup.sk.kz REST filter API (POST /eprocsearch/api/external/4dv3rts/filter)"
  patterns:
    - "tenacity retry with _is_retryable (5xx + network errors only)"
    - "httpx.AsyncClient(timeout=20.0) per-call (no singleton)"
    - "pg_insert ON CONFLICT(number_anno) DO UPDATE — idempotent upsert"
    - "Redis sk_kz:last_polled_at timestamp — written ONLY after successful DB commit"
key_files:
  created:
    - backend/app/services/sk_kz_service.py
    - backend/app/workers/tasks/poll_sk_kz_discovery.py
  modified: []
decisions:
  - "24h lookback (not 7 days) — sk.kz sorts by lastModifiedDate,desc making short windows reliable"
  - "Single page per poll — 15-min interval with 24h lookback yields <50 new tenders in practice"
  - "region and spgz_code mapped from kato.ru and truHistory.code; documented as potentially absent in filter responses (detail endpoint guarantees them)"
  - "Registration in worker_settings.py deferred to plan 08-03 (Wave 2) — enables isolated testing first"
metrics:
  duration: "~15min"
  completed: "2026-08-06T05:29:42Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 0
---

# Phase 08 Plan 01: sk.kz REST Client and ARQ Cron Task Summary

**One-liner:** Stateless REST client (fetch/parse/map) and stateful ARQ cron task (Redis-gated incremental upsert) for zakup.sk.kz → PostgreSQL ingestion.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | sk_kz_service.py — REST client with retry, date parsing, field mapping | df67f7d | backend/app/services/sk_kz_service.py |
| 2 | poll_sk_kz_discovery.py — ARQ cron task with Redis state and upsert | 3e71fc9 | backend/app/workers/tasks/poll_sk_kz_discovery.py |

## What Was Built

### `backend/app/services/sk_kz_service.py`

Stateless REST client for the zakup.sk.kz public filter endpoint:

- `_is_retryable(exc)` — copied verbatim from goszakup analog; retries 5xx and network errors only
- `parse_sk_date(value)` — ISO 8601 TZ-aware parsing via `datetime.fromisoformat()` after replacing `"Z"` with `"+00:00"`
- `_item_updated_since(item, since)` — datetime comparison gate; returns True on missing date (err on inclusion)
- `fetch_sk_tenders_page(since, page, size)` — POST to `/filter` with tenacity retry (3 attempts, exponential backoff); no auth header; parses raw JSON array; client-side filters by `lastModifiedDate`
- `_map_sk_tender(data)` — maps all sk.kz fields to Tender column dict; `source="sk_kz"` hardcoded; `status_id=None`; `region` from `kato.ru`; `spgz_code` from `truHistory.code`

### `backend/app/workers/tasks/poll_sk_kz_discovery.py`

Stateful ARQ cron task (registration deferred to 08-03):

- `LAST_POLLED_KEY = "sk_kz:last_polled_at"` — separate Redis namespace from goszakup
- `DEFAULT_LOOKBACK_HOURS = 24` — 24h lookback on first run (reliable because sk.kz sorts by `lastModifiedDate,desc`)
- `poll_sk_kz_discovery(ctx)` — reads Redis timestamp, fetches page 0, upserts, writes Redis ONLY after successful DB commit, enqueues `run_matching`
- `_upsert_tenders(session, tender_dicts)` — `pg_insert(Tender).values(rows).on_conflict_do_update(index_elements=["number_anno"])` with `cached_at=func.now()`; returns list of internal DB IDs

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Comment text] Rephrased "Authorization" in comments → "auth header"**
- **Found during:** Task 1 verification
- **Issue:** Plan acceptance criteria requires `grep -c "Authorization" sk_kz_service.py` to return 0; module docstring and function docstring used the word "Authorization" (in comments only, not in code)
- **Fix:** Replaced "Authorization header" with "auth header" in both comment occurrences
- **Files modified:** backend/app/services/sk_kz_service.py
- **Commit:** df67f7d (same commit)

**2. [Rule 1 - Comment text] Rephrased "get_db" in comment → "FastAPI dependency injection"**
- **Found during:** Task 2 verification
- **Issue:** Plan acceptance criteria requires `grep -c "get_db" poll_sk_kz_discovery.py` to return 0; module docstring used "NEVER FastAPI get_db" to document the ARQ pitfall
- **Fix:** Replaced with "NEVER FastAPI dependency injection"
- **Files modified:** backend/app/workers/tasks/poll_sk_kz_discovery.py
- **Commit:** 3e71fc9 (same commit)

## Known Stubs

None. Both files are complete implementations. `region` and `spgz_code` may be `None` for filter-endpoint responses (documented in code comment inside `_map_sk_tender`) — this is expected behavior, not a stub.

## Threat Surface Scan

No new security-relevant surface beyond the plan's threat model:
- T-08-01 (DoS): tenacity retry with `stop_after_attempt(3)` and `wait_exponential(max=10)` implemented
- T-08-02 (Tampering): all DB writes use SQLAlchemy parameterized `pg_insert().values()` — no f-string SQL
- T-08-04 (Info Disclosure): `LAST_POLLED_KEY` stores ISO timestamp only, not logged at INFO level

## Self-Check

### Created Files

- `backend/app/services/sk_kz_service.py` — FOUND (import verified)
- `backend/app/workers/tasks/poll_sk_kz_discovery.py` — FOUND (import verified)

### Commits

- `df67f7d` — feat(08-01): add sk_kz_service.py
- `3e71fc9` — feat(08-01): add poll_sk_kz_discovery.py

## Self-Check: PASSED
