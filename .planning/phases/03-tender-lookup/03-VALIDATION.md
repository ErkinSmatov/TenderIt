---
phase: 3
slug: tender-lookup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-10
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| **Config file** | `backend/pytest.ini` (asyncio_mode = auto) |
| **Quick run command** | `cd backend && pytest tests/test_tenders.py tests/test_tender_service.py -x -q` |
| **Full suite command** | `cd backend && pytest -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && pytest tests/test_tenders.py tests/test_tender_service.py -x -q`
- **After every plan wave:** Run `cd backend && pytest -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 3-W0-01 | Wave 0 spike | 0 | SRCH-02 | — | Token from settings only, never logged | manual | `GOSZAKUP_API_TOKEN=x pytest tests/spikes/test_spike01_goszakup.py -v` | ✅ | ⬜ pending |
| 3-01-01 | 03-01 | 1 | SRCH-02 | T-token | `settings.goszakup_api_token` field exists in Settings | unit | `pytest tests/test_tender_service.py::test_fetch_tender_found -x` | ❌ W0 | ⬜ pending |
| 3-01-02 | 03-01 | 1 | SRCH-02 | — | Cache hit returns cached row without API call | unit | `pytest tests/test_tender_service.py::test_cache_hit_skips_api -x` | ❌ W0 | ⬜ pending |
| 3-01-03 | 03-01 | 1 | SRCH-02 | — | Stale cache triggers re-fetch and upsert | unit | `pytest tests/test_tender_service.py::test_cache_stale_refetches -x` | ❌ W0 | ⬜ pending |
| 3-01-04 | 03-01 | 1 | SRCH-02 | — | Empty TrdBuy array → returns None (not cached) | unit | `pytest tests/test_tender_service.py::test_fetch_tender_not_found -x` | ❌ W0 | ⬜ pending |
| 3-02-01 | 03-02 | 2 | SRCH-01 | T-idor | GET /api/tenders/{number_anno} returns 200 + TenderResponse for valid ID | integration | `pytest tests/test_tenders.py::test_get_tender_found -x` | ❌ W0 | ⬜ pending |
| 3-02-02 | 03-02 | 2 | SRCH-01 | — | GET /api/tenders/{number_anno} returns 404 for unknown ID | integration | `pytest tests/test_tenders.py::test_get_tender_not_found -x` | ❌ W0 | ⬜ pending |
| 3-02-03 | 03-02 | 2 | SRCH-04 | T-idor | POST /api/watchlist adds entry linked to authenticated user | integration | `pytest tests/test_tenders.py::test_add_to_watchlist -x` | ❌ W0 | ⬜ pending |
| 3-02-04 | 03-02 | 2 | SRCH-04 | — | POST /api/watchlist is idempotent (ON CONFLICT DO NOTHING) | integration | `pytest tests/test_tenders.py::test_add_watchlist_idempotent -x` | ❌ W0 | ⬜ pending |
| 3-02-05 | 03-02 | 2 | SRCH-04 | T-idor | DELETE /api/watchlist/{number_anno} only removes own entry | integration | `pytest tests/test_tenders.py::test_remove_from_watchlist -x` | ❌ W0 | ⬜ pending |
| 3-02-06 | 03-02 | 2 | SRCH-04 | T-idor | GET /api/watchlist returns only current user's entries | integration | `pytest tests/test_tenders.py::test_get_watchlist -x` | ❌ W0 | ⬜ pending |
| 3-03-01 | 03-03 | 3 | SRCH-03 | — | TenderCard renders nameRu, customerNameRu, totalSum, endDate, statusNameRu, lots | manual | `next build` exit 0 | ❌ W0 | ⬜ pending |
| 3-03-02 | 03-03 | 3 | SRCH-01 | — | "not found" message shown on 404 | manual | visual | ❌ W0 | ⬜ pending |
| 3-03-03 | 03-03 | 3 | SRCH-04 | — | Add/remove watchlist button updates UI state | manual | visual | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_tenders.py` — route integration tests (SRCH-01, SRCH-04)
- [ ] `backend/tests/test_tender_service.py` — cache/service unit tests with respx (SRCH-02, SRCH-03)
- [ ] `respx==0.23.1` added to `pyproject.toml` `[project.optional-dependencies] dev`
- [ ] `backend/app/services/goszakup_service.py` — stub (raises NotImplementedError) so test imports work
- [ ] `backend/app/models/tender.py` — Tender + UserWatchlist models
- [ ] `backend/alembic/versions/0002_create_tenders_watchlist.py` — migration
- [ ] `frontend/src/app/(dashboard)/layout.tsx` — QueryClientProvider wrapper

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| TenderCard renders correctly with real data | SRCH-03 | UI rendering requires browser; Next.js build only catches TypeScript errors | Start dev server, search for a real tender ID (from Wave 0 spike), verify all fields display |
| "Тендер не найден" message on unknown ID | SRCH-01 | Visual error state | Search for non-existent ID, verify error message appears |
| Watchlist persists after page reload | SRCH-04 | Browser state + DB | Add to watchlist, reload page, verify tender still in watchlist |
| Wave 0 spike: real goszakup API call | SRCH-02 | Requires live token | `GOSZAKUP_API_TOKEN=<token> pytest tests/spikes/test_spike01_goszakup.py -v` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING (❌) references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
