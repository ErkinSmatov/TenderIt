---
phase: 07-discovery-matching
plan: "02"
subsystem: backend
tags: [goszakup, batch-fetch, arq, cron, discovery, redis, pagination]
dependency_graph:
  requires:
    - "07-01: DB schema (tenders.source, region, spgz_code columns from migration 0005)"
  provides:
    - "fetch_tenders_batch() in goszakup_service.py (used by poll_goszakup_discovery)"
    - "poll_goszakup_discovery ARQ cron task (discovery:last_polled_at Redis key)"
    - "run_matching ARQ job enqueued after each poll (implemented in 07-03)"
  affects:
    - "backend/app/services/goszakup_service.py — extended with batch fetch"
    - "backend/app/workers/tasks/ — new cron task file"
tech_stack:
  added: []
  patterns:
    - "respx HTTP mock for goszakup GraphQL unit tests"
    - "fakeredis.aioredis for Redis state tests without live Redis"
    - "pg_insert().on_conflict_do_update(index_elements=['number_anno']) — bulk upsert"
    - "tenacity @retry on fetch_tenders_batch — same decorator as fetch_tender_by_number_anno"
key_files:
  created:
    - backend/app/workers/tasks/poll_goszakup_discovery.py
    - backend/tests/test_goszakup_batch.py
    - backend/tests/test_poll_discovery.py
  modified:
    - backend/app/services/goszakup_service.py
decisions:
  - "Fallback pagination strategy used (no server-side lastUpdateDate filter) because goszakup API was unreachable from worktree environment for introspection; client-side stop condition implemented instead"
  - "refEnstruCode assumed as СПГЗ lot field name (LOW confidence; ACTION required: verify via live API introspection)"
  - "asyncio.sleep(0.5) in poll worker loop, NOT inside fetch_tenders_batch (T-07-04)"
  - "last_polled_at written to Redis ONLY after successful DB upsert (atomicity)"
metrics:
  duration: "~25 minutes"
  completed: "2026-07-19T10:43:46Z"
  tasks_completed: 2
  files_modified: 4
---

# Phase 7 Plan 02: Goszakup Batch Fetch + Discovery Poll Worker Summary

**One-liner:** ARQ cron `poll_goszakup_discovery` fetches tenders via `fetch_tenders_batch` with client-side date filtering, paginates with 0.5s inter-page delay, upserts via `pg_insert ON CONFLICT(number_anno) DO UPDATE`, and enqueues `run_matching`.

---

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | GraphQL introspection + fetch_tenders_batch | `621abd5` | `goszakup_service.py` |
| 2 | poll_goszakup_discovery ARQ cron + unit tests | `b67f561` | `poll_goszakup_discovery.py`, `test_goszakup_batch.py`, `test_poll_discovery.py` |

---

## What Was Built

### Task 1: fetch_tenders_batch in goszakup_service.py

Added to `backend/app/services/goszakup_service.py`:

- **`BATCH_QUERY`** constant — GraphQL query fetching TrdBuy fields including `Lots.refEnstruCode` (ASSUMED СПГЗ field)
- **`fetch_tenders_batch(since, limit=50, offset=0)`** — fetches one page of tenders from goszakup GraphQL; applies client-side date filter (`lastUpdateDate >= since`); has the same tenacity retry policy as `fetch_tender_by_number_anno` (3 attempts, exponential backoff 1-10s, 5xx-only retry)
- **`_item_updated_since(item, since_str)`** — helper for ISO string comparison (lexicographic, correct for consistently-formatted UTC dates)
- **SPIKE-BATCH comments** documenting the introspection attempt and its outcome

`fetch_tender_by_number_anno` is unmodified.

### Task 2: poll_goszakup_discovery + tests

**`backend/app/workers/tasks/poll_goszakup_discovery.py`:**
- `LAST_POLLED_KEY = "discovery:last_polled_at"` and `DEFAULT_LOOKBACK_DAYS = 7`
- `poll_goszakup_discovery(ctx)` — ARQ cron function; reads `since` from Redis, paginates `fetch_tenders_batch` with `asyncio.sleep(0.5)` between pages (T-07-04), upserts all tenders, writes `last_polled_at` only on success, enqueues `run_matching`
- `_upsert_tenders(session, tender_dicts)` — builds `pg_insert(Tender).values(rows).on_conflict_do_update(index_elements=["number_anno"])` with all relevant columns; returns list of upserted IDs
- `_map_tender_dict(data)` — maps goszakup JSON keys to Tender column names; includes `source="goszakup"`, `region=None`, `spgz_code` from `Lots[0].refEnstruCode`

**`backend/tests/test_goszakup_batch.py`** (5 tests, all pass):
- `test_fetch_batch_single_page_returns_30` — 30 items returned correctly
- `test_fetch_batch_sends_correct_offset` — offset=50 forwarded to API variables
- `test_fetch_batch_sends_bearer_token` — Authorization header starts with "Bearer "
- `test_fetch_batch_filters_old_items` — items with lastUpdateDate < since excluded
- `test_fetch_batch_empty_response` — empty API response returns []

**`backend/tests/test_poll_discovery.py`** (5 tests, all pass):
- `test_poll_writes_last_polled_at_after_success` — Redis key set after successful poll
- `test_poll_does_not_write_last_polled_at_on_fetch_error` — atomicity: no key update on error
- `test_poll_defaults_to_7_days_ago_on_first_run` — first-run defaults to 7 days ago (±10s)
- `test_poll_enqueues_run_matching_with_upserted_ids` — run_matching enqueued with correct IDs
- `test_poll_advances_timestamp_even_when_no_new_tenders` — timestamp still advanced on empty result

---

## Deviations from Plan

### Auto-fixed Issues

None — plan executed as written with one documented deviation.

### Deviation: GraphQL Introspection Not Possible

**Rule: Auto-documented (environment constraint)**

- **Found during:** Task 1, STEP 1 (mandatory introspection)
- **Issue:** `https://ows.goszakup.gov.kz/v3/graphql` unreachable from worktree execution environment (network isolation). `curl` returned exit code 000 — no network path.
- **Impact:** Two fields remained ASSUMED instead of CONFIRMED:
  1. `lastUpdateDate` filter operator (gte vs equality vs none)
  2. `refEnstruCode` as the СПГЗ code field name in Lots
- **Mitigation applied:**
  - Used client-side stop condition (`lastUpdateDate >= since_str`) as the documented fallback approach
  - Documented both assumptions as `# SPIKE-BATCH` comments in `goszakup_service.py`
  - `spgz_code` column is nullable → app works correctly even if field returns null
  - BATCH_QUERY uses `refEnstruCode` — easily changed once field name is confirmed
- **Required action:** Developer should run `query { __type(name: "Lot") { fields { name } } }` and `query { __type(name: "TrdBuyFilter") { inputFields { name } } }` against the live API with a valid token and update `goszakup_service.py` accordingly

---

## Known Stubs

- `refEnstruCode` field in `BATCH_QUERY` — ASSUMED field name for СПГЗ code in goszakup Lots. If wrong, `spgz_code` will be NULL for all tenders. The matching service's СПГЗ filter will silently never match. Resolution: run introspection query and update `_SPGZ_LOT_FIELD` + `BATCH_QUERY`.

---

## Threat Surface Scan

No new threat surface introduced beyond what is already in the threat model:
- T-07-04 (DoS): `asyncio.sleep(0.5)` between pages implemented ✓
- T-07-ext-01 (Tampering): `pg_insert().values(rows)` — parameterized via SQLAlchemy ORM ✓
- T-07-ext-02 (Info Disclosure): goszakup token never logged; only used in `Authorization: Bearer` header ✓

## Self-Check: PASSED

Files exist:
- `backend/app/services/goszakup_service.py` — FOUND (modified)
- `backend/app/workers/tasks/poll_goszakup_discovery.py` — FOUND (created)
- `backend/tests/test_goszakup_batch.py` — FOUND (created)
- `backend/tests/test_poll_discovery.py` — FOUND (created)

Commits exist:
- `621abd5` feat(07-02): add fetch_tenders_batch to goszakup_service — FOUND
- `b67f561` feat(07-02): poll_goszakup_discovery ARQ cron task + unit tests — FOUND

Tests: 10/10 passed
