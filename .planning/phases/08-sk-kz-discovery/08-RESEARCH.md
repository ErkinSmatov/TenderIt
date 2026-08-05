# Phase 8 Research — zakup.sk.kz Discovery Integration

**Date:** 2026-08-06
**Method:** HAR capture from browser DevTools (zakup.sk.kz.har)
**Conclusion:** zakup.sk.kz has a proper REST API — no HTML scraping required.

---

## API Architecture

zakup.sk.kz is a microservices platform. All external-facing endpoints share the prefix:
`https://zakup.sk.kz/{service}/api/external/`

| Microservice | Purpose |
|---|---|
| `eprocsearch` | Search/filter tenders and lots |
| `eprocuaa` | User auth (OAuth) |
| `eprocnotification` | Notifications / breaking news |
| `eprocglobal` | Reference dictionaries (tender types, regions) |
| `eproctender` | Tender requirements (salary docs, etc.) |

API version header from `/eprocuaa/api/ui-preferences`: `"api_version": "v2.4.1"`

---

## Public Endpoints (no auth required)

### 1. Filter/Search Tenders

```
POST /eprocsearch/api/external/4dv3rts/filter?size=10&page=0&sort=lastModifiedDate,desc
Content-Type: application/json
```

**Request body:**
```json
{
  "tenderSubjectTypes": [],
  "advertStatus": "PUBLISHED",
  "lotStatus": "PUBLISHED",
  "query": "надзор"
}
```

- `query` — optional full-text search
- `tenderSubjectTypes` — `["SERVICES"]`, `["GOODS"]`, `["WORKS"]` or empty for all
- `sort=lastModifiedDate,desc` — returns newest-modified first ✅ (unlike goszakup which sorts by id DESC)
- Pagination: `page=0&size=50` works

**Response item:**
```json
{
  "id": 1242993,
  "number": "1242993",
  "nameRu": "Услуги консультационные технические",
  "nameKk": "...",
  "tenderType": "OTP",
  "sumTruNoNds": 17500000.00,
  "acceptanceBeginDateTime": "2026-08-06T05:00:00Z",
  "acceptanceEndDateTime": "2026-08-17T05:00:00Z",
  "advertStatus": "PUBLISHED",
  "flagApplicationFiled": false
}
```

### 2. Tender Detail

```
GET /eprocsearch/api/external/4dv3rts/{id}
```

Returns full tender: customer BIN/name, organizer, phone, email, documents (PDF UIDs),
`tenderType`, `simpleStatus`, `advertStatus`, KATO, `sumTruNoNds`.

Document download: `fileUid` format is `{uuid}-{year}-minio` — download URL TBD (not in HAR).

### 3. Lots by Tender

```
GET /eprocsearch/api/external/4dv3rts/lots/{tender_id}?size=10&page=0
```

**Lot response fields (confirmed):**
```json
{
  "id": 4500680,
  "number": "4500680",
  "nameRu": "Услуги консультационные технические",
  "truHistory": {
    "code": "711211.000.000001",
    "ru": "Услуги консультационные технические",
    "category": "SERVICES"
  },
  "kato": { "code": "710000000", "ru": "г.Астана" },
  "deliveryKato": { "code": "710000000", "ru": "г.Астана" },
  "tenderSubjectType": "SERVICES",
  "count": 1.0,
  "price": 17500000.0,
  "sumTruNoNds": 17500000.0,
  "durationMonth": "07.2026",
  "lotStatus": "PUBLISHED",
  "lotDocuments": [{ "documentCategory": "LOT_TECHNICAL_SPECIFICATION", "fileUid": "..." }]
}
```

**Key field mappings vs goszakup:**
| goszakup | sk.kz | Notes |
|---|---|---|
| `numberAnno` | `number` | Tender identifier |
| `nameRu` | `nameRu` | Same |
| `totalSum` | `sumTruNoNds` | Sum without VAT |
| `endDate` | `acceptanceEndDateTime` | ISO 8601 with TZ |
| `Lots[].count` | `count` | Quantity |
| `Lots[].amount` | `price` / `sumTruNoNds` | Budget |
| `Lots[].nameRu` | `nameRu` | Lot name |
| N/A | `truHistory.code` | TRU/СПГЗ code (richer than goszakup!) |
| N/A | `kato.code` | Region code |
| `customerNameRu` | `customer.nameRu` | Nested object |
| `customerBin` | `customer.bin` | Nested |

### 4. Reference Dictionaries

```
GET /eprocglobal/open-api/entries?code=tender_type
```

Returns all tender type codes: `CP`, `CPOU`, `OT`, `OTP`, etc.

---

## Auth-Required Endpoints (submission)

```
GET /eprocuaa/api/account  →  401 Unauthorized
```

The HAR was captured without login. Auto-submission flow is unknown — requires a
separate HAR captured during a logged-in submission session.

**Assumption:** zakup.sk.kz likely uses an OAuth/OIDC flow with ЭЦП for authentication,
similar to NCALayer-based auth on other Kazakhstan government portals. This needs a
separate spike (capture HAR while clicking "Подать заявку" while logged in).

---

## Polling Strategy

Unlike goszakup (which returns by `id DESC` making time-window polling unreliable),
zakup.sk.kz supports `sort=lastModifiedDate,desc` — incremental polling is reliable:

1. Fetch `POST /filter?size=50&page=0&sort=lastModifiedDate,desc`
2. Stop when `lastModifiedDate < since` (items are sorted, so first item older than
   the window means we can stop)
3. Store `sk_kz:last_polled_at` in Redis to track the window

This is significantly more efficient than the goszakup polling fix (7-day lookback).

---

## Rate Limiting / ToS

- No `X-RateLimit-*` headers observed in HAR responses
- `/api/external/` path prefix strongly implies this is intentionally public
- No CAPTCHA or bot detection observed on search endpoints
- Conservative polling: 15-minute interval (same as goszakup) is safe

---

## Implementation Scope for Phase 8

### In scope (discovery only):
- `sk_kz_service.py` — REST client for the filter + detail + lots endpoints
- `poll_sk_kz_discovery` ARQ cron task (15-min interval)
- DB: `source` field on `tenders` already supports `'sk_kz'` (column exists from Phase 7 migration)
- `_map_sk_kz_tender()` mapping to existing `Tender` model
- Matching against existing `client_filters` (same rule engine, source-agnostic)
- Telegram notifications include source badge ("SK.KZ" vs "ГОСЗАКУП")
- Discovery feed UI shows source badge per card

### Out of scope (Phase 8):
- Auto-submission to zakup.sk.kz (auth flow unknown — separate spike required)
- When user clicks "Участвуем" on sk.kz tender: create Application with `status='draft'`
  and show manual submission note (same as current draft flow, but user submits manually
  on the portal)
