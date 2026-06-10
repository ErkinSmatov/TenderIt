---
phase: 03-tender-lookup
plan: 00
status: complete
completed: "2026-06-10"
---

# Plan 03-00 Summary — Wave 0: Spike + Scaffolding

## What Was Done

- **SPIKE-01** ran against live goszakup GraphQL endpoint. All unknowns resolved.
- `respx==0.23.1` added as dev dep in pyproject.toml.
- `goszakup_service.py` stub created with correct signature + TENDER_QUERY + OPEN_FOR_APPLICATIONS_STATUS_ID constant.
- 11 red test scaffolds created (5 service + 6 route) — all collect cleanly, none error.
- `QueryClientProvider` wrapper added to dashboard route group via `Providers.tsx`. Layout stays server component.

---

## Spike Findings (Wave 1 inputs)

### numberAnno Format
**`"17163708-1"`** — NOT purely numeric. Format: `{trd_buy_id}-{version_suffix}`.
→ Current validation (non-empty string ≤ 100 chars) is sufficient. No regex needed.
→ Frontend placeholder must show `"17163708-1"` not `"123456"`.

### Date String Format
**`"2026-06-10 17:57:53"`** — `YYYY-MM-DD HH:MM:SS`, no timezone suffix (NOT ISO-8601).
→ Wave 1 Pydantic validator must use `datetime.strptime(v, "%Y-%m-%d %H:%M:%S")` and attach `tzinfo=UTC+5`.

### refBuyStatusId for "open" (WAVE 1 GATE)
**`220`** = `"Опубликовано (прием заявок)"` / code `PublishedOrderTaking`
→ `OPEN_FOR_APPLICATIONS_STATUS_ID = 220` in `goszakup_service.py`.
→ Phase 5 ARQ polling checks `refBuyStatusId == 220` to trigger submission.

### Nullable Fields
`customerNameRu` and `customerNameKz` may be `null` despite `customerBin` being present.
→ DDL has `VARCHAR(500) NULL` — already correct, no schema change needed.

### totalSum Type
Returned as integer (`24180000`), not float. DDL stores as `NUMERIC(18,2)` — safe for both.

---

## Surprises

1. **TrdBuy query with nested Lots takes ~70s** — timeout raised to 90s in spike test. Wave 1 production client should use 60s (service-to-service, faster path without spike overhead).
2. **`customerNameRu` is null** even when `customerBin` is present — org name may not be populated for all customers. Handle gracefully in frontend.
3. **`totalSum` is integer** in practice despite GraphQL schema declaring it as `Float` — `NUMERIC(18,2)` column handles both.

---

## Scaffolds Created

| File | Purpose |
|------|---------|
| `backend/app/services/goszakup_service.py` | Stub with GRAPHQL_URL, TENDER_QUERY, OPEN_FOR_APPLICATIONS_STATUS_ID, `fetch_tender_by_number_anno` (raises NotImplementedError) |
| `backend/tests/test_tender_service.py` | 5 respx-based unit test stubs (Wave 1 target) |
| `backend/tests/test_tenders.py` | 6 route integration test stubs (Wave 2 target) |
| `frontend/src/app/(dashboard)/Providers.tsx` | QueryClientProvider client boundary for dashboard group |
| `backend/spikes/findings/SPIKE-01-GRAPHQL-FINDINGS.md` | Full findings with grep-gated security (no "Bearer") |

---

## Gate Status

| Gate | Value | Status |
|------|-------|--------|
| `refBuyStatusId` for "open" | **220** | ✅ CLEARED |
| Wave 1 unblocked | yes | ✅ |
| Phase 5 ARQ polling constant | `OPEN_FOR_APPLICATIONS_STATUS_ID = 220` | ✅ RECORDED |
