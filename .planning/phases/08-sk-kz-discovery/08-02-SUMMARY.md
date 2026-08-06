---
phase: 08-sk-kz-discovery
plan: "02"
subsystem: api
tags: [telegram, fastapi, pydantic, discovery, notifications, sk-kz]

# Dependency graph
requires:
  - phase: 08-sk-kz-discovery/08-01
    provides: "Tender.source='sk_kz' column and sk.kz upsert pipeline"
  - phase: 07-discovery
    provides: "send_discovery_notification, TenderMatchResponse, GET /discovery/matches, run_matching ARQ task"

provides:
  - "send_discovery_notification with backward-compatible source/portal_url params"
  - "Telegram cards prefix [SK.KZ] or [ГОСЗАКУП] based on tender source"
  - "Portal link appended to Telegram card when portal_url is not None"
  - "TenderMatchResponse schema with source and portal_url Optional[str] fields"
  - "GET /discovery/matches populates source and portal_url from Tender JOIN"
  - "_portal_url helper (discovery.py and run_matching.py): https://zakup.sk.kz/eprocsearch/tender/{number_anno} for sk_kz"

affects:
  - future frontend TenderMatchCard (source badge, portal link button)
  - phase-09 and beyond that consume discovery feed API

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "source_label computed via explicit conditional (not raw DB value) — T-08-05 tamper protection"
    - "_portal_url helper duplicated in both discovery.py and run_matching.py (no shared module needed; helpers are 5 lines)"
    - "backward-compatible default params (source='goszakup', portal_url=None) so existing callers are unaffected"

key-files:
  created: []
  modified:
    - backend/app/services/telegram_service.py
    - backend/app/workers/tasks/run_matching.py
    - backend/app/schemas/tender_match.py
    - backend/app/routers/discovery.py
    - backend/tests/test_discovery_matches.py

key-decisions:
  - "source_label computed via explicit conditional ('sk_kz' else 'ГОСЗАКУП') — raw source value never injected into message text (T-08-05)"
  - "_portal_url returns None for goszakup (no stable public read-only URL); sk.kz URL is /eprocsearch/tender/{number_anno}"
  - "portal_url added to API response as Optional[str] = None — no schema migration needed, non-breaking"

patterns-established:
  - "Pattern: backward-compatible function extension — add new kwargs with defaults so existing callers require no changes"
  - "Pattern: source label via whitelist conditional (not f-string with raw DB value)"

requirements-completed:
  - SC-08-03
  - SC-08-04

# Metrics
duration: 18min
completed: 2026-08-06
---

# Phase 8 Plan 02: sk.kz Source Propagation Summary

**Telegram discovery cards now label [SK.KZ] vs [ГОСЗАКУП] and include a direct portal link; GET /discovery/matches API exposes source and portal_url fields from Tender JOIN**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-08-06T00:00:00Z
- **Completed:** 2026-08-06T00:18:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Extended `send_discovery_notification` with `source` and `portal_url` kwargs (backward-compatible defaults) — Telegram card prefixes [SK.KZ] or [ГОСЗАКУП] and conditionally appends portal link
- Added `_portal_url` helper to both `run_matching.py` and `discovery.py` — returns `https://zakup.sk.kz/eprocsearch/tender/{number_anno}` for sk_kz, None for goszakup
- Added `source` and `portal_url` (Optional[str] = None) to `TenderMatchResponse` Pydantic schema and populated them in GET /matches from the existing Tender JOIN
- All 5 `test_discovery_matches.py` tests pass (including pre-existing IDOR guard)

## Task Commits

1. **Task 1: Extend send_discovery_notification + update run_matching.py** - `176febe` (feat)
2. **Task 2: Extend TenderMatchResponse schema + discovery.py GET /matches** - `65a10ca` (feat)

**Plan metadata:** (see final docs commit)

## Files Created/Modified

- `backend/app/services/telegram_service.py` — Added `source` / `portal_url` params, `source_label` conditional, portal link append
- `backend/app/workers/tasks/run_matching.py` — Added `_portal_url` helper, updated `send_discovery_notification` call
- `backend/app/schemas/tender_match.py` — Added `source` and `portal_url` fields to `TenderMatchResponse`
- `backend/app/routers/discovery.py` — Added `_portal_url` helper, updated `TenderMatchResponse` constructor in GET /matches
- `backend/tests/test_discovery_matches.py` — Fixed pre-existing test bug (Rule 1)

## Decisions Made

- `source_label` computed via explicit conditional rather than f-string with raw `source` — T-08-05 tamper protection (raw DB string never flows into Telegram message)
- `_portal_url` duplicated in two files (run_matching.py and discovery.py) rather than creating a shared utility module — both usages are 5-line helpers, no shared module justified at this scale
- `portal_url` returned as None for goszakup because goszakup.gov.kz has no stable public read-only tender URL

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed pre-existing test bug in test_get_matches_idor_isolation**
- **Found during:** Task 2 verification — pytest run
- **Issue:** `test_get_matches_idor_isolation` iterated `resp.json()` as a list, but GET /matches returns `TenderMatchListResponse` (dict with `items`). Iterating over dict yields string keys, causing `TypeError: string indices must be integers, not 'str'`
- **Fix:** Changed `for m in matches` to `for m in data["items"]` after extracting `data = resp.json()`
- **Files modified:** `backend/tests/test_discovery_matches.py`
- **Verification:** All 5 `test_discovery_matches.py` tests pass
- **Committed in:** `65a10ca` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 pre-existing bug in test)
**Impact on plan:** Fix was necessary for test suite to pass. No scope creep — the bug was in the test file, not in application code introduced by this plan.

## Issues Encountered

None — all planned changes applied cleanly.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced. The `portal_url` field exposed in API response reveals only the tender's public ID (already public on zakup.sk.kz) — T-08-07 accepted per threat model.

## Known Stubs

None — `source` and `portal_url` are populated from real Tender JOIN data, not hardcoded or mocked.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Discovery feed API now carries source and portal_url — frontend TenderMatchCard can add a source badge and "Open on SK.KZ" link button
- Telegram notifications are source-aware and include portal links for sk.kz tenders
- Plan 08-01 (sk.kz poller) + Plan 08-02 (source propagation) together complete the full sk.kz discovery pipeline

---
*Phase: 08-sk-kz-discovery*
*Completed: 2026-08-06*
