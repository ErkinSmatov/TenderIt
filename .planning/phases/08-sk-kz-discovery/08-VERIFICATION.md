---
phase: 08-sk-kz-discovery
verified: 2026-08-06T00:00:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Открой https://zakup.sk.kz/eprocsearch/tender/1242993 (или любой реальный tender ID из sk.kz) в браузере"
    expected: "Страница тендера на портале zakup.sk.kz открывается корректно — это подтверждает, что шаблон URL /eprocsearch/tender/{number_anno} рабочий"
    why_human: "URL-шаблон portal_url вычисляется на сервере из number_anno, который приходит из API zakup.sk.kz. Программно нельзя проверить, что страница реально открывается — нужен браузер или curl с реальным ID. Сам план (08-03, acceptance criteria) явно требует ручной верификации до деплоя."
---

# Phase 8: zakup.sk.kz Discovery — Verification Report

**Phase Goal:** zakup.sk.kz discovery integration — sk.kz tenders appear in the same match feed as goszakup, notifications arrive via the same Telegram bot, and the frontend shows a SourceBadge distinguishing sk.kz from goszakup.
**Verified:** 2026-08-06
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| #   | Truth (SC)                                                                                           | Status     | Evidence                                                                                                                                                  |
| --- | ---------------------------------------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | SC-08-01: ARQ worker polls zakup.sk.kz every 15 min, upserts to `tenders` with `source='sk_kz'`     | ✓ VERIFIED | `worker_settings.py` cron_jobs list confirmed by import; `_map_sk_tender` hardcodes `source="sk_kz"`; 9/9 unit+integration tests pass                     |
| 2   | SC-08-02: Matching engine runs unchanged — sk.kz tenders match client_filters the same way          | ✓ VERIFIED | `matching_service.py` not modified in any phase-08 commit; `poll_sk_kz_discovery` enqueues `run_matching` identically to goszakup flow                    |
| 3   | SC-08-03: User sees sk.kz matches in same /discovery feed with source badge "SK.KZ"                 | ✓ VERIFIED | `TenderMatchResponse` schema has `source`/`portal_url`; `GET /matches` populates from JOIN; `SourceBadge` in TenderMatchCard.tsx renders blue "SK.KZ" badge |
| 4   | SC-08-04: Telegram card includes source name and direct link to zakup.sk.kz                         | ✓ VERIFIED | `send_discovery_notification` has `source`/`portal_url` params; message prefixes `[SK.KZ]`/`[ГОСЗАКУП]`; portal link appended when set                   |
| 5   | SC-08-05: "Участвуем" on sk.kz tender creates draft Application; manual note shown                  | ✓ VERIFIED | `POST /participate` calls `create_discovery_draft` (source-agnostic); amber note rendered when `source==='sk_kz' && status==='participating'`              |

**Score: 5/5 truths verified**

---

### Required Artifacts

| Artifact                                                           | Expected                                                  | Status      | Details                                                            |
| ------------------------------------------------------------------ | --------------------------------------------------------- | ----------- | ------------------------------------------------------------------ |
| `backend/app/services/sk_kz_service.py`                           | REST client: fetch, parse, map sk.kz tenders             | ✓ VERIFIED  | 5 functions; no auth header; ISO 8601 parse; source="sk_kz"        |
| `backend/app/workers/tasks/poll_sk_kz_discovery.py`               | ARQ cron: Redis-gated upsert → run_matching enqueue      | ✓ VERIFIED  | LAST_POLLED_KEY="sk_kz:last_polled_at"; 24h lookback; atomicity    |
| `backend/app/workers/worker_settings.py`                          | poll_sk_kz_discovery in cron_jobs, minute={0,15,30,45}   | ✓ VERIFIED  | Import confirmed; cron_jobs=['poll_watchlist_tenders', 'poll_goszakup_discovery', 'poll_sk_kz_discovery'] |
| `backend/app/services/telegram_service.py`                        | send_discovery_notification extended with source/portal_url | ✓ VERIFIED | source default="goszakup"; portal_url default=None; backward-compatible |
| `backend/app/workers/tasks/run_matching.py`                       | _portal_url helper + updated notification call           | ✓ VERIFIED  | _portal_url returns sk.kz URL for sk_kz, None for goszakup; call updated |
| `backend/app/schemas/tender_match.py`                             | TenderMatchResponse with source and portal_url fields    | ✓ VERIFIED  | Both Optional[str]=None confirmed via import check                 |
| `backend/app/routers/discovery.py`                                | GET /matches populates source and portal_url from JOIN   | ✓ VERIFIED  | _portal_url helper at module level; source=tender.source in response |
| `frontend/src/types/discovery.ts`                                 | TenderMatchResponse with source/portal_url TypeScript fields | ✓ VERIFIED | source: string\|null; portal_url: string\|null — added after region |
| `frontend/src/components/discovery/TenderMatchCard.tsx`           | SourceBadge + portal link + sk.kz participation note     | ✓ VERIFIED  | SourceBadge defined + used (2 occurrences); anchor with rel="noopener noreferrer"; amber note |
| `backend/tests/test_sk_kz_service.py`                             | 5 unit tests for REST client (respx mock)                | ✓ VERIFIED  | 5 passed in 3.09s (incl. retry delay for 500-test)                 |
| `backend/tests/test_poll_sk_kz_discovery.py`                      | 4 integration tests for ARQ cron task (fakeredis+patch)  | ✓ VERIFIED  | 4 passed in 0.13s                                                  |

---

### Key Link Verification

| From                                      | To                                         | Via                                              | Status     | Details                                                         |
| ----------------------------------------- | ------------------------------------------ | ------------------------------------------------ | ---------- | --------------------------------------------------------------- |
| `poll_sk_kz_discovery.py`                | `sk_kz_service.py`                         | `from app.services.sk_kz_service import fetch_sk_tenders_page, parse_sk_date, _map_sk_tender` | ✓ WIRED | Import confirmed; functions called at lines 70, 106             |
| `poll_sk_kz_discovery.py`                | Redis key `sk_kz:last_polled_at`           | `ctx["redis"].get / ctx["redis"].set`            | ✓ WIRED    | get at line 61, set at lines 78 and 88 (after async with)       |
| `poll_sk_kz_discovery.py`                | tenders table                              | `pg_insert(Tender).on_conflict_do_update(index_elements=["number_anno"])` | ✓ WIRED | Lines 108-129 of poll_sk_kz_discovery.py                       |
| `poll_sk_kz_discovery.py`                | `run_matching` ARQ task                    | `await redis.enqueue_job("run_matching", upserted_ids)` | ✓ WIRED | Line 93; guarded by `if upserted_ids:` (atomicity)             |
| `worker_settings.py`                     | `poll_sk_kz_discovery.py`                  | `from app.workers.tasks.poll_sk_kz_discovery import poll_sk_kz_discovery` | ✓ WIRED | Confirmed by runtime import check; appears in cron_jobs         |
| `run_matching.py`                         | `telegram_service.py`                      | lazy import `send_discovery_notification`; `source=tender.source`, `portal_url=_portal_url(...)` | ✓ WIRED | Lines 146-165; both new kwargs confirmed                        |
| `discovery.py`                            | `tender_match.py` schema                   | `TenderMatchResponse(source=tender.source if tender else None, portal_url=_portal_url(...))` | ✓ WIRED | Lines 181-185 of discovery router                              |
| `TenderMatchCard.tsx`                     | `discovery.ts`                             | `import type { TenderMatchResponse } from '@/types/discovery'`; `match.source`, `match.portal_url` | ✓ WIRED | Line 14; used at lines 153 (SourceBadge) and 189 (note)        |

---

### Data-Flow Trace (Level 4)

| Artifact             | Data Variable     | Source                             | Produces Real Data | Status     |
| -------------------- | ----------------- | ---------------------------------- | ------------------ | ---------- |
| `TenderMatchCard`    | `match.source`    | `GET /discovery/matches` → `tender.source` (DB column) | Yes — populated from `Tender.source` which `_upsert_tenders` sets to `"sk_kz"` | ✓ FLOWING |
| `TenderMatchCard`    | `match.portal_url`| `_portal_url(tender.source, tender.number_anno)` in router | Yes — computed server-side from Tender DB fields | ✓ FLOWING |
| Telegram bot message | `source_label`    | `send_discovery_notification(source=tender.source)` from `run_matching.py` | Yes — `tender.source` loaded from DB at line 141 | ✓ FLOWING |

---

### Behavioral Spot-Checks

| Behavior                                                       | Command / Check                                                                                   | Result                                            | Status  |
| -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------- | ------- |
| `parse_sk_date('2026-08-17T05:00:00Z')` returns TZ-aware datetime | `python3 -c "..."` import + assertion                                                           | `imports OK, parse_sk_date OK, _map_sk_tender OK` | ✓ PASS  |
| `_map_sk_tender` sets `number_anno=str(id)` and `source="sk_kz"` | Same import check                                                                               | number_anno=='1242993', source=='sk_kz'          | ✓ PASS  |
| `LAST_POLLED_KEY == "sk_kz:last_polled_at"`, `DEFAULT_LOOKBACK_HOURS == 24` | Python3 import assertion                                                              | KEY=sk_kz:last_polled_at, LOOKBACK=24h           | ✓ PASS  |
| `TenderMatchResponse.model_fields` contains source and portal_url | Python3 schema check                                                                          | Both fields confirmed in schema                  | ✓ PASS  |
| `_portal_url` returns correct URL for sk_kz, None for goszakup | Python3 assertion on all 3 cases                                                              | All 3 assertions pass                            | ✓ PASS  |
| `send_discovery_notification` signature: source='goszakup', portal_url=None | `inspect.signature` check                                                          | Both defaults confirmed                          | ✓ PASS  |
| `WorkerSettings.cron_jobs` contains poll_sk_kz_discovery      | Python3 import + list comprehension check                                                         | cron_jobs confirmed with all 3 entries           | ✓ PASS  |
| TypeScript compilation — no new errors                        | `npx tsc --noEmit` in frontend/                                                                   | Exit 0                                            | ✓ PASS  |

---

### Probe Execution

| Probe                                               | Command                                             | Result       | Status |
| --------------------------------------------------- | --------------------------------------------------- | ------------ | ------ |
| `tests/test_sk_kz_service.py` (5 tests)            | `pytest tests/test_sk_kz_service.py -x -v`         | 5 passed in 3.09s | PASS |
| `tests/test_poll_sk_kz_discovery.py` (4 tests)     | `pytest tests/test_poll_sk_kz_discovery.py -x -v`  | 4 passed in 0.13s | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| SC-08-01 | 08-01, 08-03 | ARQ poll + upsert with source='sk_kz' | ✓ SATISFIED | sk_kz_service.py + poll_sk_kz_discovery.py + worker_settings.py + 9 passing tests |
| SC-08-02 | 08-03 | Matching engine unchanged; sk.kz tenders flow through same pipeline | ✓ SATISFIED | matching_service.py not in any phase-08 commit; run_matching enqueues from both sources |
| SC-08-03 | 08-02, 08-04 | Source badge "SK.KZ" in discovery feed | ✓ SATISFIED | SourceBadge in TenderMatchCard.tsx + source/portal_url in schema + API router |
| SC-08-04 | 08-02 | Telegram card: source label + portal link | ✓ SATISFIED | send_discovery_notification extended; run_matching passes source+portal_url |
| SC-08-05 | 08-04 | "Участвуем" creates draft; manual note shown | ✓ SATISFIED | /participate endpoint calls create_discovery_draft; amber note in TenderMatchCard |

**REQUIREMENTS.md traceability gap (WARNING):**
SC-08-01 through SC-08-05 are defined in ROADMAP.md Phase 8 success criteria but are NOT registered in REQUIREMENTS.md. REQUIREMENTS.md (v1) explicitly lists zakup.sk.kz integration as a v2 deferred requirement and places it "Out of Scope" for v1. ROADMAP.md was updated to include Phase 8 but REQUIREMENTS.md traceability table was not updated to map SC-08-xx to Phase 8.

This is a documentation debt, not an implementation blocker. The phase goal matches ROADMAP.md, and all ROADMAP success criteria are satisfied by the codebase. Action: update REQUIREMENTS.md to add SC-08-01..SC-08-05 IDs and add Phase 8 rows to the traceability table.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `backend/app/workers/tasks/run_matching.py` | 6 | Docstring says "Called by poll_goszakup_discovery" — incomplete after Phase 8 | ℹ️ Info | No code impact; documentation only. Should say "Called by poll_goszakup_discovery and poll_sk_kz_discovery" |

No TBD/FIXME/XXX/HACK markers found in any of the 11 phase-8 modified files. No stub patterns detected.

---

### Human Verification Required

#### 1. Portal URL Template — zakup.sk.kz tender page

**Test:** Возьми реальный tender ID из ответа zakup.sk.kz filter API (например, из HAR или из первого же poll после деплоя) и открой `https://zakup.sk.kz/eprocsearch/tender/{id}` в браузере.

**Expected:** Страница тендера на zakup.sk.kz открывается (HTTP 200 или 302-редирект на страницу тендера). URL-шаблон корректен.

**Why human:** URL-шаблон `/eprocsearch/tender/{number_anno}` выведен из структуры URL-дерева (не из HAR-трафика). Сам план 08-03 явно указывает: _"Verify by navigating to a published sk.kz tender in a browser"_ (acceptance criteria Task 1). Если шаблон неверен — portal_url в Telegram-уведомлениях и в discovery feed будет вести на несуществующую страницу.

---

### Gaps Summary

Нет блокирующих gaps. Все 5 критериев успеха ROADMAP.md верифицированы в кодовой базе на всех уровнях (exists, substantive, wired, data-flowing). Тесты проходят (9/9). TypeScript компилируется без ошибок.

Единственная открытая задача — ручная проверка URL-шаблона для portal_url до включения Telegram-уведомлений в production.

---

_Verified: 2026-08-06_
_Verifier: Claude (gsd-verifier)_
