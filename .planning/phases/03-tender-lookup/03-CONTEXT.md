# Phase 3 — Tender Lookup: Discussion Context

**Created:** 2026-06-10  
**Status:** Ready for planning  
**Requirements covered:** SRCH-01, SRCH-02, SRCH-03, SRCH-04

---

## Summary

Phase 3 lets users find a specific tender by its portal ID, view its details, and add it to their watchlist. The key constraint is that **the Unified Services REST API is undocumented** — we only have a token. Wave 0 must be an API discovery spike before any integration code is written.

---

## Decisions

### 1. API Discovery Is Wave 0 (Blocker)

**Decision:** Phase 3 begins with an API discovery spike (Wave 0) that runs live HTTP calls against the goszakup Unified Services REST API to determine:
- Base URL of the Unified Services REST API (distinct from the old GraphQL endpoint `ows.goszakup.gov.kz/v3/graphql`)
- Endpoint for fetching a single tender by its portal ID
- Exact format of `tenderID` (numeric? string? prefix? length?)
- Authentication header format (`Bearer <token>` or custom header)
- Response schema: fields returned, field names, status codes
- Rate limits (if discoverable)
- What happens on a not-found ID (404 vs 200 with empty body vs error body)

**Why:** No API documentation was provided with the token. tenderID format is unknown. Attempting to write integration code without this information would produce untestable stubs.

**Spike output:** `backend/spikes/findings/SPIKE-01-UNIFIED-REST-FINDINGS.md` with curl examples, actual response samples (redacted of any sensitive data), and the confirmed endpoint + field mapping.

**Note:** The existing `backend/tests/spikes/test_spike01_goszakup.py` targets the old GraphQL endpoint and should be updated or replaced after the spike with a new REST-targeted test.

**Starting point for discovery (try these in order):**
1. `https://ows.goszakup.gov.kz/` — root, may list available APIs
2. `https://ows.goszakup.gov.kz/v3/` — v3 REST root
3. `https://api.goszakup.gov.kz/` — alternative domain
4. Auth: `Authorization: Bearer <token>` header (standard; confirm it works)
5. Public goszakup developer portal if accessible (developer.goszakup.gov.kz or similar)

---

### 2. Database Model

**Decision:** Two tables.

```sql
-- Cached tender data from goszakup portal
tenders
  id                SERIAL PRIMARY KEY
  tender_id_portal  VARCHAR(50)  UNIQUE NOT NULL  -- номер объявления из goszakup
  title             TEXT
  customer_name     VARCHAR(500)
  lot_description   TEXT
  contract_amount   NUMERIC(18, 2)
  deadline          TIMESTAMPTZ
  status            VARCHAR(100)                  -- Phase 5 ARQ polling updates this field
  raw_data          JSONB                         -- full API response snapshot (no schema lock-in)
  cached_at         TIMESTAMPTZ NOT NULL DEFAULT now()
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()

-- Per-user watchlist
user_watchlist
  id                SERIAL PRIMARY KEY
  user_id           INT NOT NULL  REFERENCES users(id) ON DELETE CASCADE
  tender_id         INT NOT NULL  REFERENCES tenders(id) ON DELETE CASCADE
  added_at          TIMESTAMPTZ NOT NULL DEFAULT now()
  notification_on   BOOLEAN NOT NULL DEFAULT true
  UNIQUE(user_id, tender_id)  -- user can only add a tender once
```

**Rationale for `raw_data JSONB`:**
- The API schema is unknown until the spike runs
- Storing the full response in JSONB lets us add new displayed fields later (Phase 5 may need additional fields for submission) without a migration
- Named scalar columns (`title`, `customer_name`, etc.) are extracted for indexed queries and UI display

**Rationale for two tables:**
- Same tender can theoretically be watched by multiple users — cache it once, serve to all
- `tenders` acts as an API response cache
- `user_watchlist` is the per-user relationship, independent of cache state

---

### 3. Cache Strategy

**Decision:** Always cache in `tenders` on lookup, even before adding to watchlist.

**Rules:**
- On lookup by `tender_id_portal`: check `tenders` table first
  - If found AND `cached_at` is within **30 minutes** → return cached data (no API call)
  - If found AND `cached_at` is older than 30 minutes → re-fetch from API, `UPDATE tenders SET ... cached_at = now()`
  - If not found → fetch from API, `INSERT INTO tenders`
- Cache entry exists regardless of watchlist status (user may look up same tender multiple times)
- 30-minute TTL for tender card display is acceptable; tender status does not change minute-to-minute during the pre-submission period
- **Phase 5 ARQ polling** will update the `status` field directly (bypassing the TTL) — that's a separate concern, not part of Phase 3

**Not-found handling:**
- If API returns not-found for a portal ID → return 404 from backend, never insert into `tenders`
- Frontend shows: "Тендер с номером {ID} не найден на портале"
- No crash, no 500, no empty card

---

### 4. tenderID Validation

**Decision:** Defer precise validation rules to spike findings.

**Interim approach:** accept any non-empty string up to 50 chars, strip whitespace. Once spike establishes the format (e.g., "6 digits", "prefix+8 digits"), add a regex validator in the Pydantic schema.

---

### 5. Scope Boundaries for Phase 3

**In scope:**
- Lookup by single tenderID
- Tender card display (title, lot, customer, amount, deadline, status)
- Add to / remove from watchlist
- Not-found error handling
- `tenders` + `user_watchlist` models and migration
- Backend `GET /api/tenders/{tender_id}` + `POST /api/watchlist` + `DELETE /api/watchlist/{tender_id}` + `GET /api/watchlist`
- Frontend: search bar page, tender card component, watchlist on dashboard

**Out of scope (Phase 5):**
- ARQ polling job for status updates
- Tender status change notifications
- Auto-submit flow

**Out of scope (v2):**
- Keyword search / browse
- Filters (amount, deadline, region)
- MP.kz integration

---

## Wave Plan (Recommended)

| Wave | Content |
|------|---------|
| Wave 0 | API discovery spike — determine endpoints, tenderID format, response schema |
| Wave 1 | DB models + migration (`tenders` + `user_watchlist`) + service layer |
| Wave 2 | Backend API routes + cache logic + tests |
| Wave 3 | Frontend: search page + tender card + watchlist management |

Wave 0 output must be complete before Wave 1 begins. Waves 1–3 can proceed once endpoint + schema are known.

---

## Existing Patterns to Follow

- SQLAlchemy 2.x async with `lazy="selectin"` on all relationships (established in Phase 2)
- Alembic migration with `revision` id (follow `0001_create_users_company_profiles.py` naming)
- `models/__init__.py` must import all new models for Alembic to detect them
- Pydantic schemas in `backend/app/schemas/` with field validators
- `get_current_user` dependency from `backend/app/deps.py` for auth-protected routes
- HTTPx for outbound API calls (already in deps)
- React Hook Form + Zod on frontend for forms
