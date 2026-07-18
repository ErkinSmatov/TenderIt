---
phase: 05-eds-signing-submission
plan: "03"
subsystem: signing-wizard
tags: [goszakup-proxy, ncalayer, cryptosocket, wizard-ui, tdd, portal-steps]
dependency_graph:
  requires: [05-01, 05-02]
  provides: [portal-proxy-steps-1-11, cryptosocket-hook, signing-wizard]
  affects: [05-04, 05-05]
tech_stack:
  added:
    - useCryptoSocket hook (TumarCSP WebSocket, ws://127.0.0.1:6126/tumarcsp)
    - runSigningFlow orchestration lib (browser ↔ /api/goszakup proxy ↔ NCALayer ↔ CryptoSocket)
    - 4-step ApplicationWizard UI
  patterns:
    - TDD RED→GREEN for portal client + proxy router (Task 1)
    - EFCAPI.EncryptOfferPrice + SetAPIKey CryptoSocket protocol (GAMMA-ENCRYPTION-FINDINGS.md)
    - PHP bracket notation: selectLots[], xmlData[lpId], offer[app_lot_id][lp_id][price]
    - CSRF refresh: extract from Set-Cookie + JSON body per response
    - Per-user Redis session: goszakup_session:{user_id}, 72000s TTL
key_files:
  created:
    - backend/app/services/goszakup_portal_client.py (extended with steps 1-11)
    - backend/app/routers/goszakup_proxy.py (12 auth-gated endpoints)
    - backend/tests/test_goszakup_proxy.py (25 tests, all passing)
    - frontend/src/types/cryptosocket.ts
    - frontend/src/hooks/useCryptoSocket.ts
    - frontend/src/hooks/__tests__/useCryptoSocket.test.ts (10 vitest tests)
    - frontend/src/types/application.ts
    - frontend/src/lib/goszakup.ts
    - frontend/src/components/applications/ApplicationWizard.tsx
    - frontend/src/components/applications/LotPriceForm.tsx
    - frontend/src/components/applications/DocumentSelect.tsx
    - frontend/src/components/applications/SigningStep.tsx
    - frontend/src/app/(dashboard)/applications/new/page.tsx
  modified:
    - backend/app/services/application_service.py (Rule 1: datetime timezone bug)
    - backend/.env.example (removed stray artifact, added Phase 5 comment)
    - frontend/.env.example (NEXT_PUBLIC_CRYPTOSOCKET_API_KEY placeholder)
    - frontend/.env.local.example (NEXT_PUBLIC_CRYPTOSOCKET_API_KEY placeholder)
decisions:
  - "CSRF refresh: portal does NOT change CSRF token per AJAX step (constant per session). Refresh check added for safety."
  - "CryptoSocket hook separate from useNCALayer (architecture constraint GAMMA-ENCRYPTION-FINDINGS.md)"
  - "iik + subject_address collected as form inputs in SigningStep — not in company_profiles schema (Phase 2 scope boundary)"
  - "tenderBuyId parsed from number_anno format {trd_buy_id}-{version} (tender.py model comment)"
metrics:
  completed: "2026-07-18"
  tasks_completed: 3
  tasks_total: 3
  files_created: 13
  files_modified: 5
---

# Phase 5 Plan 03: Portal Proxy + CryptoSocket Hook + Application Wizard Summary

**One-liner:** GoszakupPortalClient extended with portal steps 1-11, auth-gated /api/goszakup proxy, useCryptoSocket hook (TumarCSP EFCAPI.EncryptOfferPrice), and 4-step ApplicationWizard for price→documents→signing flow.

## What Was Built

### Task 1 (TDD): Backend portal proxy + client steps 1-11

`GoszakupPortalClient` extended with methods for all 12 portal steps:
- `create_application` → `/ru/application/ajax_create_application/`
- `add_lots` → PHP bracket notation `selectLots[]` repeated
- `lots_next`, `docs_next`, `priceoffers_next` → `next=1` confirmations
- `save_beneficiary` → `/ru/beneficiary/ajax_save_info` with citizenship=398, option_1..4 defaults
- `get_encr_info` → returns JSON encryption params for CryptoSocket
- `add_encrypt` → saves encrypted price blob
- `save_gamma_signs` ��� `xmlData[lpId]` + `signData[lpId]` PHP bracket notation

`goszakup_proxy.py` replaced from empty stub to 12 auth-gated endpoints:
- `POST /auth/login` → calls login_with_signed_xml, stores Redis session
- `/proxy/create-draft` through `/proxy/priceoffers-next` → loads session, calls client, re-stores session
- `/proxy/mark-ready/{app_id}` → verifies ownership, calls mark_ready, persists application_id + tender_buy_id

All tests: **25/25 passing**.

### Task 2: useCryptoSocket + orchestration lib

- `useCryptoSocket` hook: `ws://127.0.0.1:6126/tumarcsp`, SetAPIKey auth, EFCAPI.EncryptOfferPrice
- `runSigningFlow` in `goszakup.ts`: orchestrates all 12 steps, progress callback, typed GoszakupFlowError
- `frontend/src/types/application.ts` + `cryptosocket.ts`

All vitest tests: **10/10 passing**.

### Task 3: ApplicationWizard UI

4-step wizard at `/applications/new`:
1. Select watched tender from GET /api/watchlist
2. LotPriceForm — unit price per lot, totalPrice = unitPrice × quantity
3. DocumentSelect — multi-select from GET /api/documents/attachable
4. SigningStep — NCALayerStatus + CertificateInfo + CryptoSocket status, button gated on both connected

Build output: **/applications/new — 9.96 kB** (static pre-render).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] datetime.now(timezone.utc) incompatible with PostgreSQL TIMESTAMP WITHOUT TIME ZONE**
- **Found during:** Task 1 verification
- **Issue:** `mark_ready()` in `application_service.py` passed timezone-aware datetimes to asyncpg, causing `DataError`
- **Fix:** Added `_utcnow()` helper returning `datetime.now(timezone.utc).replace(tzinfo=None)`; replaced all occurrences
- **Files modified:** `backend/app/services/application_service.py`

**2. [Rule 1 - Artifact] Stray text in backend/.env.example**
- **Found during:** Task 2 env var additions
- **Issue:** File ended with `17163708-1` (accidental paste artifact, no trailing newline)
- **Fix:** Cleaned up file, added Phase 5 env var comments
- **Files modified:** `backend/.env.example`

### Research Finding: CSRF per-request refresh

RESEARCH open question #3 asked whether goszakup portal changes CSRF per AJAX step. Finding: portal does NOT refresh CSRF token per step — it is constant per session. `_extract_csrf_from_response()` helper checks Set-Cookie and JSON body for safety but finds nothing after initial login.

### iik + subject_address: Not in company_profiles

`iik` (IIK bank account) and `subject_address` (portal address ID) are portal-specific fields not stored in `company_profiles` (Phase 2 only stores BIN, company_name, legal_address). For MVP these are collected as form inputs in SigningStep. Adding to company_profiles is deferred to a future plan.

## Security Mitigations Applied

| Threat ID | Status | Implementation |
|-----------|--------|----------------|
| T-05-20 | Mitigated | `_require_session()` loads session by JWT user_id; each user drives their own session |
| T-05-21 | Mitigated | All portal calls via /api/goszakup; grep gate: zero direct portal XHR in frontend/src |
| T-05-22 | Mitigated | `_extract_csrf_from_response()` + re-store on every proxy step |
| T-05-23 | Mitigated | No logging of encrypted blobs, signed data, or session secrets |

## Known Stubs

| Stub | File | Reason |
|------|------|--------|
| `beneficiaries` placeholder (app_lot_id = lot index, names empty) | `ApplicationWizard.tsx` | Portal assigns app_lot_id after create_application; actual IDs not known at build time. Backend proxy uses real IDs from Redis session. |
| `tender_id: 0` in ApplicationCreate | `ApplicationWizard.tsx` | Tender DB id not exposed in WatchlistEntry. Workaround: pass `tender_number_anno` field; backend resolves. Requires 05-05 POST /api/applications endpoint to support this. |

## Self-Check

**Files:** 14/14 found (13 created + SUMMARY)
**Commits:** 4 task commits found

| Commit | Description |
|--------|-------------|
| `644d8cd` | test(05-03): RED — failing tests for portal steps 1-11 proxy + router endpoints |
| `f6dddb5` | feat(05-03): implement portal steps 1-11 + goszakup proxy router endpoints (GREEN) |
| `a5bb309` | feat(05-03): useCryptoSocket hook + browser orchestration lib (Task 2) |
| `45c4583` | feat(05-03): 4-step application wizard UI (Task 3) |

**Status: PASSED**
