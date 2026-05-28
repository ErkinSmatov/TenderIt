---
phase: 01-spikes-foundation
plan: "02"
subsystem: spikes
tags: [goszakup, graphql, api, spike, auth, rate-limit]
dependency_graph:
  requires:
    - 01-01 (monorepo scaffold — backend Python package structure)
  provides:
    - spike-01-goszakup-introspection-script
    - spike-01-letter-template
    - spike-01-partial-findings
  affects:
    - Phase 3 goszakup sync worker (TrdBuy field names from schema)
    - Phase 5 submission architecture (mutation existence verdict — PENDING)
tech_stack:
  added:
    - httpx 0.28.1 (already in pyproject.toml — used for async GraphQL calls)
    - tenacity (already in pyproject.toml — used for TrdBuy retry logic)
  patterns:
    - asyncio.run() as entry point for spike scripts
    - httpx.AsyncClient with timeout=30.0 and http2=True
    - os.environ for token injection (never hardcoded — T-02-01 mitigation)
    - tenacity retry only on TrdBuy query (not rate limit probe — intentional)
    - pytest.mark.skipif pattern for token-gated integration tests
key_files:
  created:
    - backend/spikes/spike_goszakup.py
    - backend/spikes/findings/.gitkeep
    - backend/spikes/findings/SPIKE-01-FINDINGS.md
    - backend/tests/spikes/__init__.py
    - backend/tests/spikes/test_spike01_goszakup.py
    - docs/letter-templates/goszakup-api-token-request.md
  modified: []
decisions:
  - "Endpoint reachability probe (401 not ECONNREFUSED) confirms goszakup v3 GraphQL is live and auth-gated — no sandbox exists, all testing against production"
  - "Framework fingerprint from 401 body: yii\\web\\UnauthorizedHttpException — backend is Yii2/PHP, not a native GraphQL server; error formats may differ from spec"
  - "Token intentionally not printed in spike script output (T-02-01 Information Disclosure mitigation)"
  - "Rate limit probe uses 1 req/sec inter-request sleep with stop-on-429 (T-02-03 WAF mitigation)"
  - "Mutation verdict (D-S01-01) and rate limit data (D-S01-02) are PENDING — blocked on API token from АО ЦЭФ"
metrics:
  duration: "~20 minutes"
  completed_date: "2026-05-28"
  tasks_completed: 2
  tasks_total: 3
  files_created: 6
---

# Phase 1 Plan 02: SPIKE-01 goszakup GraphQL API Summary

**One-liner:** goszakup v3 GraphQL endpoint confirmed reachable (401 in 78ms, Yii2/PHP backend); introspection script + formal letter template created; schema/mutation verdict pending API token from АО ЦЭФ.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write goszakup introspection script and letter template | bd69798 | backend/spikes/spike_goszakup.py, backend/tests/spikes/test_spike01_goszakup.py, docs/letter-templates/goszakup-api-token-request.md |
| 3 | Write SPIKE-01-FINDINGS.md from captured evidence | bcf716b | backend/spikes/findings/SPIKE-01-FINDINGS.md (partial — pre-token sections complete) |

## Task Skipped (Checkpoint — Human Action Required)

| Task | Name | Status | Blocker |
|------|------|--------|---------|
| 2 | Execute goszakup introspection against live API | BLOCKED | Requires Bearer token from АО «Центр Электронных Финансов» |

## Verification Results

| Check | Command | Result |
|-------|---------|--------|
| Script import | `python3 -c "from spikes.spike_goszakup import spike_goszakup"` | OK |
| Missing token exit | `python -m spikes.spike_goszakup` (no token) | Exits code 1, clear message |
| Pytest discovery | `pytest tests/spikes/test_spike01_goszakup.py --collect-only` | 2 tests collected |
| Tests skip without token | `pytest tests/spikes/test_spike01_goszakup.py -v` | 2 skipped (GOSZAKUP_API_TOKEN not set) |
| FINDINGS.md exists | `test -f backend/spikes/findings/SPIKE-01-FINDINGS.md` | FOUND (170 lines) |
| Letter template exists | `test -f docs/letter-templates/goszakup-api-token-request.md` | FOUND |
| Endpoint reachable | `curl -X POST https://ows.goszakup.gov.kz/v3/graphql` (no auth) | 401 in ~78ms |

## Pre-Token Evidence (Confirmed Without API Access)

The unauthenticated curl probe returned:
```json
{
  "name": "Unauthorized",
  "message": "Your request was made with invalid credentials.",
  "code": 0,
  "status": 401,
  "type": "yii\\web\\UnauthorizedHttpException"
}
```

**Confirmed facts:**
- DNS resolves, TLS handshake succeeds, application processes the request
- Backend is Yii2/PHP (not a native GraphQL server — error format uses Yii2 exception class)
- Bearer auth is required; header format is `Authorization: Bearer {token}`
- Response time: ~78ms unauthenticated

## Deviations from Plan

### Auto-fixed Issues

None.

### Scope Adjustment

**Task 3 executed partially (pre-token).** The plan specifies Task 3 (SPIKE-01-FINDINGS.md) should run
after Task 2 (human-executed spike). Since Task 2 is blocked, Task 3 was executed with the evidence
available — reachability probe results (401 body, timing, framework fingerprint) — and all pending
sections are clearly marked `[PENDING — token required]`. This is consistent with the plan's own note:
"If the spike was only partially executable... document what was verified and what remains pending."

The findings document has all required section headings and exceeds the 80-line minimum (170 lines).

## Authentication Gate

**BLOCKED:** API token for https://ows.goszakup.gov.kz/v3/graphql requires a formal written request
to АО «Центр Электронных Финансов». Processing time is 3–10 business days.

**What to do:**
1. Review and fill in `docs/letter-templates/goszakup-api-token-request.md`
2. Submit per instructions at https://goszakup.gov.kz/ru/developer/ows_v3
3. While waiting, try the public schema browser at https://ows.goszakup.gov.kz/help/v3/schema/
   to check for mutation type existence (this may answer the Phase 5 architecture question immediately)
4. When token arrives, run:
   ```bash
   cd backend && GOSZAKUP_API_TOKEN=your_token python -m spikes.spike_goszakup
   ```
5. Populate the pending sections in `backend/spikes/findings/SPIKE-01-FINDINGS.md`

## Known Stubs

| Stub | File | Reason |
|------|------|--------|
| Schema summary section | SPIKE-01-FINDINGS.md | Token required for introspection |
| Rate limit findings | SPIKE-01-FINDINGS.md | Token required for probe execution |
| TrdBuy sample response | SPIKE-01-FINDINGS.md | Token required for live query |
| D-S01-01 mutation verdict | SPIKE-01-FINDINGS.md | Token required — critical Phase 5 gate |
| D-S01-02 ARQ sync interval | SPIKE-01-FINDINGS.md | Token required — rate limit measurement |

These stubs do NOT block Phase 1 completion of other spikes (SPIKE-02 through SPIKE-05 are independent).
They DO block Phase 3 goszakup sync worker design and Phase 5 submission architecture.

## Threat Model Review

| Threat ID | Status |
|-----------|--------|
| T-02-01: GOSZAKUP_API_TOKEN in .env | Mitigated — token read from env, never printed, .env in .gitignore |
| T-02-02: spike-01-schema.json committed to git | Accepted (pending) — no schema committed yet; when populated, schema is public knowledge |
| T-02-03: Rate limit probe triggering WAF block | Mitigated — 1 req/sec with asyncio.sleep(1.0), stop on first 429 |

## Self-Check: PASSED

- [x] `backend/spikes/spike_goszakup.py` exists and `from spikes.spike_goszakup import spike_goszakup` succeeds
- [x] Running without token prints clear error and exits code 1
- [x] `backend/tests/spikes/test_spike01_goszakup.py` exists — pytest discovers 2 test functions
- [x] `docs/letter-templates/goszakup-api-token-request.md` exists with all required sections (production Russian)
- [x] `backend/spikes/findings/SPIKE-01-FINDINGS.md` exists with all required section headings (170 lines)
- [x] Task 1 commit bd69798 present in git log
- [x] Task 3 commit bcf716b present in git log
- [x] No modifications to STATE.md or ROADMAP.md
