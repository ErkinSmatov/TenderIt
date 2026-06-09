# Phase 3 — Tender Lookup: Discussion Context

**Created:** 2026-06-10  
**Updated:** 2026-06-10 (added full API contract from official docs)  
**Status:** Ready for planning  
**Requirements covered:** SRCH-01, SRCH-02, SRCH-03, SRCH-04

---

## Summary

Phase 3 lets users find a specific tender by portal announcement number, view its details, and add it to their watchlist. The API is documented at `https://goszakup.gov.kz/ru/developer/ows_v3` — we now know the endpoints, field names, and schema. **One unknown remains: the exact `refBuyStatusId` integer values**, which must be resolved in Wave 0 by querying the справочник endpoint. Everything else is implementable.

---

## API Contract (Confirmed from Official Docs)

**Base URL:** `https://ows.goszakup.gov.kz`  
**Auth:** `Authorization: Bearer <token>` — tokens are valid 1 year  
**GraphQL endpoint:** `POST /v3/graphql`  
**REST fallback:** `GET /v3/trd-buy/number-anno/{numberAnno}` + `GET /v3/lots/number-anno/{numberAnno}`

### Decision: Use GraphQL (not REST)

`TrdBuy` has a nested `Lots` field in the GraphQL schema — one query returns announcement + all lots. REST would require two parallel calls. GraphQL is strictly better here.

### GraphQL query for tender lookup

```graphql
query TenderByNumber($numberAnno: String!) {
  TrdBuy(filter: { numberAnno: $numberAnno }, limit: 1) {
    id
    numberAnno
    nameRu
    nameKz
    totalSum
    countLots
    customerBin
    customerNameRu
    customerNameKz
    refBuyStatusId
    RefBuyStatus {
      id
      nameRu
      nameKz
      code
    }
    startDate
    endDate
    publishDate
    lastUpdateDate
    Lots {
      id
      lotNumber
      nameRu
      nameKz
      descriptionRu
      amount
      refLotStatusId
    }
  }
}
```

### Key TrdBuy fields (confirmed from schema)

| GraphQL field | DB column | Description |
|---|---|---|
| `numberAnno` | `number_anno` | Nomination number — **String, not Int** — this is what users paste |
| `nameRu` | `name_ru` | Tender title in Russian |
| `nameKz` | `name_kz` | Tender title in Kazakh |
| `totalSum` | `total_sum` | Total planned amount (Float) |
| `customerNameRu` | `customer_name_ru` | Customer name in Russian |
| `customerNameKz` | `customer_name_kz` | Customer name in Kazakh |
| `refBuyStatusId` | `status_id` | Status code (Int) — Phase 5 polls this field |
| `RefBuyStatus.nameRu` | `status_name_ru` | Human-readable status name |
| `startDate` | `start_date` | Application acceptance start (String → TIMESTAMPTZ) |
| `endDate` | `end_date` | Application acceptance end / deadline (String → TIMESTAMPTZ) |
| `publishDate` | `publish_date` | Publication date |

### `Lots` fields (confirmed from schema)

| GraphQL field | Description |
|---|---|
| `nameRu` | Lot name in Russian |
| `descriptionRu` | Lot detailed description |
| `amount` | Lot amount (Float) |
| `lotNumber` | Lot number within announcement |

### 404 format (confirmed)

```json
{
  "name": "Not Found",
  "message": "...",
  "code": 0,
  "status": 404,
  "type": "yii\\web\\NotFoundHttpException"
}
```

GraphQL returns `TrdBuy: []` (empty array) for an unknown `numberAnno` — not HTTP 404. Backend must treat empty array as not-found and return 404.

---

## Wave 0 — Targeted Spike (Still Required)

Wave 0 is now **narrow**: the API contract is known. The only blocker is:

1. **Confirm token works** — run `{ __typename }` query against `/v3/graphql`  
2. **Get status reference values** — call `GET /v3/справочники` or GraphQL introspection to find what `refBuyStatusId` code means "open for applications (принимаются заявки)". This value is the trigger for Phase 5 notifications.
3. **Confirm `numberAnno` format** — run the TrdBuy query with a real tender ID; record the actual string value returned (is it `"123456"`, `"RU-2025-123456"`, or something else?)
4. **Record a real sample response** — redact sensitive fields, save to `backend/spikes/findings/SPIKE-01-GRAPHQL-FINDINGS.md`

Wave 0 output gates Wave 1. **Do not start Wave 1 without the status code for "open"**.

**Update existing spike test:** `backend/tests/spikes/test_spike01_goszakup.py` already uses `/v3/graphql` and Bearer auth — update it to also test the TrdBuy query.

---

## Decisions

### 1. Database Model

**Decision:** Two tables.

```sql
-- Cached tender data from goszakup portal
tenders
  id                SERIAL PRIMARY KEY
  number_anno       VARCHAR(100) UNIQUE NOT NULL  -- TrdBuy.numberAnno — String
  name_ru           TEXT
  name_kz           TEXT
  total_sum         NUMERIC(18, 2)
  customer_name_ru  VARCHAR(500)
  customer_name_kz  VARCHAR(500)
  status_id         INT                          -- TrdBuy.refBuyStatusId — Phase 5 polls this
  status_name_ru    VARCHAR(200)                 -- TrdBuy.RefBuyStatus.nameRu
  start_date        TIMESTAMPTZ
  end_date          TIMESTAMPTZ                  -- submission deadline
  publish_date      TIMESTAMPTZ
  lots_data         JSONB                        -- serialized Lots array (nameRu, descriptionRu, amount)
  raw_data          JSONB                        -- full GraphQL response snapshot
  cached_at         TIMESTAMPTZ NOT NULL DEFAULT now()
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()

-- Per-user watchlist
user_watchlist
  id                SERIAL PRIMARY KEY
  user_id           INT NOT NULL  REFERENCES users(id) ON DELETE CASCADE
  tender_id         INT NOT NULL  REFERENCES tenders(id) ON DELETE CASCADE
  added_at          TIMESTAMPTZ NOT NULL DEFAULT now()
  notification_on   BOOLEAN NOT NULL DEFAULT true
  UNIQUE(user_id, tender_id)
```

**Rationale for `lots_data JSONB`:**  
A tender can have multiple lots. Storing them in a separate `lots` table adds complexity with no Phase 3 benefit. JSONB is sufficient for display; if Phase 5 needs per-lot targeting, we add the table then.

**Rationale for `raw_data JSONB`:**  
Phase 5 (submission payload) may need additional TrdBuy fields (e.g. `systemId`, `refTradeMethodsId`). Storing the full response avoids a future re-fetch just to get a new field.

**Rationale for two tables:**  
Same tender can be watched by multiple users — cache once, serve to all. `user_watchlist` is a clean M:N join.

---

### 2. Cache Strategy

**Decision:** Always cache in `tenders` on lookup, even before adding to watchlist.

**Rules:**
- Lookup by `number_anno`: check `tenders` table first
  - Found AND `cached_at` within **30 minutes** → return cached row (no API call)
  - Found AND `cached_at` older than 30 minutes → re-fetch from API, `UPDATE`
  - Not found → fetch from API, `INSERT`
- Not-found from API → return `404`, do NOT insert into `tenders`
- **Phase 5 ARQ polling** updates `status_id` + `status_name_ru` + `cached_at` directly — bypasses the 30-min TTL entirely. That's Phase 5, not Phase 3.

**Frontend not-found message:** `"Тендер с номером {ID} не найден на портале"`

---

### 3. `number_anno` Validation

**Decision:** Accept any non-empty string up to 100 chars, strip whitespace. No regex until Wave 0 spike confirms the exact format.

---

### 4. Scope Boundaries

**In Phase 3:**
- `GET /api/tenders/{number_anno}` — lookup + cache
- `POST /api/watchlist` — add tender to watchlist  
- `DELETE /api/watchlist/{number_anno}` — remove  
- `GET /api/watchlist` — list watched tenders for dashboard  
- Frontend: search input page, tender card, watchlist section on dashboard

**Phase 5 (not here):** ARQ polling, status change detection, Telegram/WhatsApp notify, auto-submit

**v2 (deferred):** keyword search, filters, MP.kz

---

## Wave Plan

| Wave | Content | Gate |
|------|---------|------|
| Wave 0 | Spike: confirm token, get status reference codes, record real response | Must complete before Wave 1 |
| Wave 1 | DB models + Alembic migration + goszakup GraphQL service layer | After Wave 0 |
| Wave 2 | Backend routes + cache logic + unit tests | After Wave 1 |
| Wave 3 | Frontend: search page, tender card component, watchlist on dashboard | After Wave 2 |

---

## Existing Patterns to Follow

- SQLAlchemy 2.x async with `lazy="selectin"` on all relationships (Phase 2)
- Alembic: revision ID pattern, `models/__init__.py` must import all new models
- Pydantic schemas in `backend/app/schemas/` with `@field_validator`
- `get_current_user` dependency from `backend/app/deps.py` for protected routes
- HTTPx for outbound API calls
- React Hook Form + Zod on frontend (Phase 2 `CompanyProfileForm` as reference)
- **НИКОГДА не хранить токен goszakup в коде** — только `settings.goszakup_api_token` из `.env`
