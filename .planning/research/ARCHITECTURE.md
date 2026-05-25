# Architecture Patterns

**Domain:** Kazakhstan e-procurement tender aggregator (TenderIt)
**Researched:** 2026-05-25
**Confidence note:** NCALayer protocol — MEDIUM (based on pki.gov.kz official docs and widely-referenced community integrations, no live fetch possible in this session). Goszakup GraphQL schema — MEDIUM (public API, schema well-documented). Overall structural patterns — HIGH.

---

## Recommended Architecture

### Overview

The system has five distinct runtime concerns that must stay cleanly separated:

1. **Web tier** — Next.js, serves UI and proxies signing calls
2. **API tier** — FastAPI, all business logic, portal integration, document management
3. **Worker tier** — Python async workers for tender sync and notification dispatch (same FastAPI codebase, separate process entry point)
4. **Storage tier** — PostgreSQL (relational data + JSONB for portal-specific fields), local/S3 filesystem for company documents
5. **External integrations** — goszakup GraphQL, MP.kz REST, NCALayer (localhost WS on user machine), Telegram Bot API, WhatsApp Business API

NCALayer is **not** a server-side concern. It runs on the user's machine and is called exclusively from the browser. The backend never touches NCALayer directly.

---

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  USER'S BROWSER                                             │
│                                                             │
│  ┌──────────────────┐      ┌──────────────────────────────┐ │
│  │  Next.js UI       │      │  NCALayer (local desktop app)│ │
│  │  (React SPA pages)│◄────►│  ws://localhost:14579        │ │
│  │                  │      │  PKCS#7 / CMS signer         │ │
│  └────────┬─────────┘      └──────────────────────────────┘ │
│           │ HTTPS/REST                                       │
└───────────┼─────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│  FASTAPI BACKEND                                            │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐ │
│  │ Auth Router  │  │Tender Router │  │ Application Router│ │
│  │ JWT + refresh│  │search/filter │  │ draft/sign/submit │ │
│  └──────────────┘  └──────┬───────┘  └────────┬──────────┘ │
│                           │                   │             │
│  ┌──────────────┐  ┌──────▼───────┐  ┌────────▼──────────┐ │
│  │  Doc Router  │  │Tender Service│  │Submission Service │ │
│  │ upload/fetch │  │(unified model│  │(portal adapters)  │ │
│  └──────┬───────┘  └──────┬───────┘  └────────┬──────────┘ │
│         │                 │                   │             │
│  ┌──────▼─────────────────▼───────────────────▼──────────┐ │
│  │              PostgreSQL (via SQLAlchemy async)         │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Worker Process (APScheduler or Celery Beat)         │  │
│  │  ┌─────────────────┐  ┌────────────────────────────┐ │  │
│  │  │ Tender Sync Job  │  │  Notification Dispatcher   │ │  │
│  │  │ goszakup GraphQL │  │  (Telegram Bot + WhatsApp) │ │  │
│  │  │ MP.kz REST       │  │                            │ │  │
│  │  └─────────────────┘  └────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
            │                        │
            ▼                        ▼
┌──────────────────┐     ┌─────────────────────────────────┐
│  File Storage     │     │  External APIs                  │
│  (S3 / local FS) │     │  goszakup.gov.kz GraphQL        │
│  company docs    │     │  MP.kz REST                     │
│                  │     │  Telegram Bot API               │
└──────────────────┘     │  WhatsApp Business API          │
                         └─────────────────────────────────┘
```

---

## Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| Next.js UI | Render pages, manage NCALayer WS connection, display tender feed, application status | FastAPI (HTTPS), NCALayer localhost WS |
| FastAPI Auth | JWT issue/refresh, user registration, password hashing | PostgreSQL |
| FastAPI Tender | Unified tender search, filter, pagination, detail view | PostgreSQL (tenders table) |
| FastAPI Application | Draft creation, document assembly, status transitions, receive signed blob from browser | PostgreSQL, File Storage, Submission Service |
| Submission Service | Portal-specific adapters: package tenders application per portal spec, call portal API | goszakup GraphQL, MP.kz REST |
| Tender Sync Worker | Scheduled pull from both portals, upsert into tenders table, enqueue notification checks | PostgreSQL, goszakup GraphQL, MP.kz REST |
| Notification Dispatcher | Query subscriptions vs new tenders, send messages via Telegram/WhatsApp | PostgreSQL, Telegram Bot API, WhatsApp Business API |
| Document Service | Store/retrieve company documents, generate signed URLs, version blobs | File Storage (S3 or local) |

---

## 1. NCALayer WebSocket Flow

### Protocol (MEDIUM confidence — pki.gov.kz v2 protocol)

NCALayer v2 listens on `ws://localhost:14579`. All messages are JSON. The browser is the sole client — the backend never opens a connection to it.

**Request envelope:**
```json
{
  "module": "kz.gov.pki.knca.commonUtils",
  "method": "signXml",
  "args": {
    "storageName": "PKCS12",
    "keyType": "SIGNATURE",
    "xmlToSign": "<base64-encoded-xml-string>",
    "tbsElementXPath": "",
    "signNodeId": "",
    "signaturePolicyId": ""
  }
}
```

Available `method` values relevant to TenderIt:
- `signXml` — signs an XML string, returns XMLDSig-wrapped result
- `signData` — signs arbitrary base64 data, returns CMS/PKCS#7 detached signature
- `getKeyInfo` — returns certificate info (IIN/BIN embedded in subject) without signing

`storageName` is typically `"PKCS12"` (file-based key) or `"AKKAZEToken"` (hardware token). For MVP, PKCS12 is sufficient.

**Response envelope (success):**
```json
{
  "module": "kz.gov.pki.knca.commonUtils",
  "method": "signXml",
  "result": {
    "xml": "<SignedInfo>...</SignedInfo>"
  }
}
```

**Response envelope (error / user cancel):**
```json
{
  "module": "kz.gov.pki.knca.commonUtils",
  "method": "signXml",
  "errorCode": "USER_CANCEL",
  "message": "Действие отменено пользователем"
}
```

Known `errorCode` values: `USER_CANCEL`, `PASSWORD_CHANGED`, `NONE` (generic), `NOT_FOUND` (no key store found).

### Integration Flow

The browser opens the WS connection lazily — only when the user initiates signing. Keep the connection alive for the duration of one signing session, then close it.

```
Browser                     FastAPI                    NCALayer (localhost)
  │                             │                            │
  │  POST /applications/{id}/prepare                        │
  │ ─────────────────────────► │                            │
  │                             │  Assembles payload XML     │
  │                             │  (application data)        │
  │ ◄─────────────────────────  │                            │
  │  { payloadXml: "..." }      │                            │
  │                             │                            │
  │  ws://localhost:14579 CONNECT                           │
  │ ────────────────────────────────────────────────────── ►│
  │  { module, method: "signXml", args: { xmlToSign } }     │
  │ ────────────────────────────────────────────────────── ►│
  │  (User enters PIN in NCALayer dialog)                   │
  │ ◄──────────────────────────────────────────────────────  │
  │  { result: { xml: "<signed>...</signed>" } }            │
  │                             │                            │
  │  POST /applications/{id}/submit                         │
  │  body: { signedXml: "..." }                             │
  │ ─────────────────────────► │                            │
  │                             │  SubmissionService calls   │
  │                             │  portal API with signed XML│
  │ ◄─────────────────────────  │                            │
  │  { status: "submitted" }    │                            │
```

**Critical design decision:** The backend assembles the payload before signing, and receives the signed blob after. The backend never stores the user's private key or PIN. The browser is the signing oracle.

**Frontend implementation:** A custom React hook `useNCALayer()` manages the WS lifecycle. It exposes `{ sign(xml: string): Promise<string>, status, error }`. The hook opens the WS on first call and handles reconnection with exponential backoff. If NCALayer is not running, `status` becomes `"unavailable"` and the UI shows a "Start NCALayer" prompt with a download link.

---

## 2. Tender Sync Architecture

### Scheduler

Use **APScheduler** (AsyncIOScheduler) running as a separate process entry point (`worker/main.py`). This is preferable to Celery for MVP because it adds zero infrastructure — no Redis, no RabbitMQ. The workers share the same SQLAlchemy async engine as the API.

For v2 (if sync load grows), migrate to Celery Beat + Redis.

**Job schedule:**
```
goszakup_sync   — every 15 minutes
mpkz_sync       — every 30 minutes
notification_dispatch — every 5 minutes (runs after sync windows)
```

### Goszakup GraphQL Sync

Goszakup exposes a public GraphQL API at `https://ows.goszakup.gov.kz/v3/graphql`. Authentication is via an API token passed in the `Authorization: Bearer <token>` header — tokens are issued per company (user must supply their goszakup API token in their profile, or TenderIt obtains one per company during onboarding).

Incremental sync query (conceptual — exact field names depend on current schema):
```graphql
query SyncTenders($after: String, $publishedFrom: String) {
  TrdBuy(
    filter: { publishDateStart: $publishedFrom }
    first: 100
    after: $after
  ) {
    id
    numberAnno
    nameRu
    totalSum
    publishDate
    endDate
    status { nameRu }
    customer { bin nameRu }
    lots { id nameRu count amount }
    trdBuyType { nameRu }
  }
}
```

Use cursor-based pagination (`after`) and track `last_synced_at` per portal in a `sync_state` table. On each run: query from `last_synced_at` → upsert → update `sync_state`.

### MP.kz Sync

MP.kz uses a REST API. Treat it as a portal adapter behind the same sync interface:

```python
class PortalAdapter(Protocol):
    async def fetch_new_tenders(self, since: datetime) -> list[RawTender]: ...
    async def submit_application(self, package: ApplicationPackage) -> SubmissionResult: ...
```

Both goszakup and MP.kz implement this protocol. The sync worker calls `adapter.fetch_new_tenders()` and feeds results into the unified mapper.

### Notification Matching

After each sync run, the notification dispatcher:
1. Loads all `user_subscriptions` (keyword lists + filters per user)
2. Queries `tenders` inserted since last dispatch run
3. Performs keyword matching in Python (for MVP: simple `ILIKE '%keyword%'` in PostgreSQL against `name_ru`, `name_kz`, `description`)
4. For each match: creates a `notification` row with status `pending`, dispatches to Telegram/WhatsApp, marks `sent`

For v2: use PostgreSQL full-text search (`tsvector` on name + description columns) for proper stemming.

---

## 3. Document Storage

### Storage Backend

For MVP: local filesystem under a configured base path (e.g., `/data/documents/{company_id}/{doc_type}/`). Use an abstraction layer (`DocumentStorage` protocol) so it can swap to S3/MinIO without changing business logic.

For production: S3-compatible storage (AWS S3 or MinIO self-hosted). Pre-signed URLs for browser downloads (time-limited, no public bucket).

### Versioning

Company documents change (new license, updated charter). Store versions explicitly:

```
documents
  id, company_id, doc_type, version, filename,
  storage_key, mime_type, size_bytes, uploaded_at,
  is_current (boolean)
```

On new upload: mark old `is_current = false`, insert new row with `is_current = true`. Retain old versions for audit trail. Do not delete.

### Auto-Attach to Applications

When user initiates an application, the Application Service queries `documents WHERE company_id = ? AND is_current = true` and builds an `application_documents` join table. The user reviews the document list before signing. Documents are fetched by storage key at submission time to assemble the final package.

---

## 4. Application Submission Pipeline

### Application Package for Goszakup

Goszakup submission uses their GraphQL mutation API (v3). The signed data is an XML document conforming to their XMLDSig schema. The process:

1. **Prepare stage** (server-side): FastAPI builds the application XML from:
   - Tender lot ID
   - Company BIN and details
   - Price offer
   - Document references (or inline base64-encoded document content for required attachments)

2. **Sign stage** (browser-side): The prepared XML is sent to NCALayer `signXml`. The returned signed XML contains the original data plus `<ds:Signature>` block.

3. **Submit stage** (server-side): FastAPI calls goszakup's submission mutation:
   ```graphql
   mutation SubmitApplication($input: ApplicationInput!) {
     createApplication(input: $input) {
       id
       status
       errorMessage
     }
   }
   ```
   The `input` contains the signed XML as a string field plus metadata.

For MP.kz: the package format is their own REST spec (likely multipart/form-data with XML + file attachments). Same three-stage flow; different adapter.

### Application State Machine

```
DRAFT ──► DOCUMENTS_READY ──► SIGNING ──► SIGNED ──► SUBMITTING ──► SUBMITTED
                                              │                          │
                                              └──► SIGN_FAILED           └──► SUBMIT_FAILED
```

State is stored on the `applications` table. Transitions are validated server-side. The `SUBMITTING` → `SUBMITTED` / `SUBMIT_FAILED` transition happens in the `SubmissionService` after receiving the portal API response.

---

## 5. Multi-Platform Abstraction (Unified Tender Schema)

The unified model captures the intersection of what both portals provide, plus a JSONB `portal_data` field for portal-specific extras that don't fit the common schema.

```sql
CREATE TABLE tenders (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  portal          TEXT NOT NULL,          -- 'goszakup' | 'mpkz'
  portal_id       TEXT NOT NULL,          -- native ID on that portal
  name_ru         TEXT NOT NULL,
  name_kz         TEXT,
  description     TEXT,
  status          TEXT NOT NULL,          -- 'active' | 'closed' | 'cancelled'
  published_at    TIMESTAMPTZ NOT NULL,
  deadline_at     TIMESTAMPTZ,
  customer_bin    TEXT,
  customer_name   TEXT,
  region_code     TEXT,
  category_code   TEXT,                   -- KTRU/OKDP code
  total_amount    NUMERIC(18,2),
  currency        TEXT DEFAULT 'KZT',
  lots            JSONB,                  -- array of lot objects
  portal_data     JSONB,                  -- raw portal-specific fields
  synced_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (portal, portal_id)
);
```

Mappers live in `adapters/goszakup/mapper.py` and `adapters/mpkz/mapper.py`. Each takes a raw portal response dict and returns a `TenderCreate` Pydantic schema. The sync worker calls the mapper before upserting.

**Rule:** Business logic (search, filter, notification matching) only touches the unified columns. Portal-specific rendering in the UI reads from `portal_data` JSONB.

---

## 6. Frontend Architecture

### NCALayer Constraint

Because NCALayer is a localhost service, it can only be called from browser JavaScript. No server can proxy the call (a server cannot open a WS connection to the user's `localhost`). This constraint is architectural — embrace it:

- All signing logic lives in the browser
- The browser receives the pre-built payload from the API, signs it, and returns the signed blob to the API
- The Next.js server-side (RSC, API routes) plays no role in signing

### Next.js Page Structure

```
app/
  (auth)/
    login/page.tsx
    register/page.tsx
  (dashboard)/
    layout.tsx          ← checks JWT, redirects to login if missing
    tenders/
      page.tsx          ← tender feed (server component, initial load)
      [id]/page.tsx     ← tender detail
    applications/
      page.tsx          ← my applications list
      [id]/
        page.tsx        ← application detail + signing UI
    documents/
      page.tsx          ← company document vault
    profile/
      page.tsx          ← company profile + subscription filters
```

### State Management

Use React Server Components for initial data fetch (tender list, application list). Use TanStack Query (React Query) for client-side cache management, polling application status, and mutations. Do not use Redux or Zustand for MVP — the data graph is not complex enough.

### NCALayer Hook

```typescript
// hooks/useNCALayer.ts
type NCALayerStatus = 'idle' | 'connecting' | 'ready' | 'signing' | 'unavailable' | 'error'

interface UseNCALayer {
  status: NCALayerStatus
  sign(xmlPayload: string): Promise<string>    // returns signedXml
  certInfo: CertInfo | null
  connect(): void
}
```

On mount of the signing page, call `connect()` which opens `new WebSocket('ws://localhost:14579')`. On connection failure after 2 retries, set status `unavailable`. The signing page renders a "NCALayer not detected" banner with a download link to pki.gov.kz when `unavailable`.

---

## Data Flow: "User Submits Tender Application"

This is the most complex flow in the system. Numbered steps map to components.

```
1.  User clicks "Apply" on tender detail page
    → Browser: POST /api/applications  { tenderId, lotId }
    → FastAPI ApplicationRouter

2.  ApplicationRouter creates Application row (status=DRAFT)
    → Queries company profile and current documents
    → Returns { applicationId, documents: [...], companyInfo }

3.  User reviews document list on /applications/{id} page
    → Clicks "Confirm and Sign"
    → Browser: POST /api/applications/{id}/prepare
    → ApplicationService builds application XML payload

4.  FastAPI returns { payloadXml: "<Application>...</Application>" }

5.  Browser: useNCALayer.sign(payloadXml)
    → Opens WS to localhost:14579 (if not already open)
    → Sends { module, method: "signXml", args: { xmlToSign: payloadXml } }
    → User sees NCALayer PIN dialog
    → User enters PIN
    → NCALayer returns { result: { xml: "<SignedApplication>...</SignedApplication>" } }

6.  Browser: POST /api/applications/{id}/submit  { signedXml }
    → ApplicationRouter validates signedXml is non-empty, updates status=SIGNING

7.  SubmissionService.submit(application, signedXml):
    a. Selects correct portal adapter (goszakup or mpkz)
    b. Calls adapter.submit_application(package)
    c. Portal adapter calls goszakup GraphQL mutation (or MP.kz REST)
    d. On success: updates application status=SUBMITTED, stores portal_ref_id
    e. On failure: updates status=SUBMIT_FAILED, stores error_message

8.  Browser polls GET /api/applications/{id}/status (or SSE stream)
    → Receives final status: SUBMITTED or SUBMIT_FAILED
    → Shows success confirmation or error with retry option
```

---

## Database Schema Sketch

Core entities. Omits indexes and constraints for clarity.

```sql
-- Users and companies (1:1 for MVP)
CREATE TABLE users (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email           TEXT UNIQUE NOT NULL,
  password_hash   TEXT NOT NULL,
  created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE companies (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
  bin             TEXT UNIQUE NOT NULL,          -- Business ID number
  name_ru         TEXT NOT NULL,
  director_name   TEXT,
  address         TEXT,
  goszakup_token  TEXT,                          -- encrypted, per-company API token
  mpkz_token      TEXT,
  telegram_chat_id TEXT,
  whatsapp_number  TEXT,
  created_at      TIMESTAMPTZ DEFAULT now()
);

-- Tender aggregation
CREATE TABLE tenders (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  portal          TEXT NOT NULL,
  portal_id       TEXT NOT NULL,
  name_ru         TEXT NOT NULL,
  name_kz         TEXT,
  description     TEXT,
  status          TEXT NOT NULL,
  published_at    TIMESTAMPTZ NOT NULL,
  deadline_at     TIMESTAMPTZ,
  customer_bin    TEXT,
  customer_name   TEXT,
  region_code     TEXT,
  category_code   TEXT,
  total_amount    NUMERIC(18,2),
  currency        TEXT DEFAULT 'KZT',
  lots            JSONB,
  portal_data     JSONB,
  synced_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (portal, portal_id)
);

-- Full-text search vector (populated by trigger)
ALTER TABLE tenders ADD COLUMN search_vector TSVECTOR
  GENERATED ALWAYS AS (
    to_tsvector('russian', coalesce(name_ru,'') || ' ' || coalesce(description,''))
  ) STORED;
CREATE INDEX tenders_search_idx ON tenders USING GIN(search_vector);

-- Company documents
CREATE TABLE documents (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id      UUID REFERENCES companies(id) ON DELETE CASCADE,
  doc_type        TEXT NOT NULL,   -- 'charter' | 'license' | 'certificate' | 'other'
  display_name    TEXT NOT NULL,
  storage_key     TEXT NOT NULL,   -- path in S3/local FS
  mime_type       TEXT NOT NULL,
  size_bytes      INTEGER,
  version         INTEGER NOT NULL DEFAULT 1,
  is_current      BOOLEAN NOT NULL DEFAULT true,
  uploaded_at     TIMESTAMPTZ DEFAULT now()
);

-- Tender applications
CREATE TABLE applications (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id      UUID REFERENCES companies(id) ON DELETE CASCADE,
  tender_id       UUID REFERENCES tenders(id),
  portal          TEXT NOT NULL,
  lot_id          TEXT,
  status          TEXT NOT NULL DEFAULT 'DRAFT',
  price_offer     NUMERIC(18,2),
  payload_xml     TEXT,            -- assembled before signing
  signed_xml      TEXT,            -- returned from NCALayer, stored for audit
  portal_ref_id   TEXT,            -- ID assigned by portal after submission
  error_message   TEXT,
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Documents attached to an application (snapshot at time of submission)
CREATE TABLE application_documents (
  application_id  UUID REFERENCES applications(id) ON DELETE CASCADE,
  document_id     UUID REFERENCES documents(id),
  PRIMARY KEY (application_id, document_id)
);

-- User notification subscriptions
CREATE TABLE subscriptions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id      UUID REFERENCES companies(id) ON DELETE CASCADE,
  keywords        TEXT[] NOT NULL DEFAULT '{}',
  min_amount      NUMERIC(18,2),
  max_amount      NUMERIC(18,2),
  region_codes    TEXT[] DEFAULT '{}',
  category_codes  TEXT[] DEFAULT '{}',
  portals         TEXT[] DEFAULT '{"goszakup","mpkz"}',
  active          BOOLEAN DEFAULT true,
  created_at      TIMESTAMPTZ DEFAULT now()
);

-- Sent notifications (dedup)
CREATE TABLE notifications (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id      UUID REFERENCES companies(id),
  tender_id       UUID REFERENCES tenders(id),
  channel         TEXT NOT NULL,   -- 'telegram' | 'whatsapp'
  status          TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'sent' | 'failed'
  sent_at         TIMESTAMPTZ,
  UNIQUE (company_id, tender_id, channel)  -- prevent duplicate sends
);

-- Sync state tracking per portal
CREATE TABLE sync_state (
  portal          TEXT PRIMARY KEY,
  last_synced_at  TIMESTAMPTZ,
  last_tender_id  TEXT,
  error_count     INTEGER DEFAULT 0
);
```

---

## Suggested Build Order

Build order respects hard dependencies. A component is a prerequisite if later components cannot be tested without it.

```
Phase 1 — Foundation (nothing works without this)
  1a. PostgreSQL schema + Alembic migrations
  1b. FastAPI project structure, SQLAlchemy async setup, config management
  1c. Auth: register, login, JWT issue/refresh
  1d. Company profile CRUD

Phase 2 — Tender Data (everything downstream needs tenders in the DB)
  2a. Goszakup adapter: GraphQL client, mapper to unified schema
  2b. MP.kz adapter: REST client, mapper to unified schema
  2c. APScheduler worker: sync jobs, sync_state table
  2d. Tender search/filter API endpoints
  2e. Next.js tender feed page (RSC + TanStack Query)

Phase 3 — Document Vault (required before applications)
  3a. Document upload endpoint (FastAPI + storage abstraction)
  3b. Document listing and download (pre-signed URLs)
  3c. Next.js document vault UI

Phase 4 — Application + Signing (core product value)
  4a. Application CRUD (draft creation, document attachment)
  4b. Payload XML assembly (prepare endpoint)
  4c. useNCALayer hook (browser WS client for localhost:14579)
  4d. Signing UI page (sign button, NCALayer status, error states)
  4e. Goszakup submission adapter (GraphQL mutation)
  4f. MP.kz submission adapter (REST)
  4g. Application status polling / SSE

Phase 5 — Notifications
  5a. Subscription CRUD API + UI (keyword filters)
  5b. Telegram bot setup (bot token, sendMessage)
  5c. WhatsApp Business API integration
  5d. Notification dispatcher worker job

Phase 6 — Hardening
  6a. Error handling, retry logic in sync/submission workers
  6b. Signed XML storage for audit (GDPR/legal note: consider encryption at rest)
  6c. Rate limiting on API endpoints
  6d. Monitoring: Sentry or similar for exception tracking
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Backend Proxy for NCALayer
**What:** Routing NCALayer WS through a server-side proxy or trying to call it from FastAPI
**Why bad:** NCALayer binds to localhost. A server process cannot connect to the user's localhost. This approach is architecturally impossible.
**Instead:** Browser holds the WS connection. Backend assembles payload, browser signs, backend receives signed result.

### Anti-Pattern 2: Storing the Signed XML Only in Memory
**What:** Discarding `signedXml` after forwarding it to the portal
**Why bad:** No audit trail. Disputes with portals require proof of what was submitted.
**Instead:** Persist `signed_xml` on the `applications` row. Consider encryption at rest since it contains the user's digital signature.

### Anti-Pattern 3: Polling Portals Per User Request
**What:** Each time a user opens the tender list, making live calls to goszakup/MP.kz
**Why bad:** Portal APIs have rate limits, latency is high (200-800ms per page), and the data is the same for all users.
**Instead:** Background sync worker populates the local database. The API serves from PostgreSQL exclusively.

### Anti-Pattern 4: One Monolithic Sync Job
**What:** A single job that syncs both portals sequentially and then dispatches notifications
**Why bad:** If goszakup is slow, notification delivery is delayed. If one portal is down, the other doesn't sync.
**Instead:** Separate jobs per portal. Notification dispatcher is independent, runs on its own schedule.

### Anti-Pattern 5: Storing Portal API Tokens in Plain Text
**What:** Saving `goszakup_token` as plaintext in the companies table
**Why bad:** Database leak exposes all user portal credentials.
**Instead:** Encrypt with a server-side key (e.g., Fernet from Python `cryptography` library) before persisting. Decrypt only in memory when making portal calls.

---

## Scalability Considerations

| Concern | MVP (1-100 users) | Growth (100-5K users) |
|---------|-------------------|-----------------------|
| Tender sync | APScheduler in-process | Celery Beat + Redis, parallel workers per portal |
| Notification delivery | Synchronous in worker loop | Celery task per notification, bounded concurrency |
| Document storage | Local filesystem, per-instance | S3 or MinIO, decoupled from app instance |
| Search/filter | PostgreSQL GIN full-text | Same, add `pg_trgm` trigram index for fuzzy |
| DB connections | SQLAlchemy async, pool of 10 | PgBouncer connection pooler |
| Portal submission | Synchronous in request | Background task, webhook or polling for status |

---

## Sources

- NCALayer protocol: pki.gov.kz official documentation, NCALayer v2 API reference (MEDIUM confidence — official source, no live fetch in this session)
- Goszakup GraphQL API: ows.goszakup.gov.kz/v3/graphql, public developer documentation (MEDIUM confidence)
- APScheduler: apscheduler.readthedocs.io, AsyncIOScheduler patterns
- PostgreSQL full-text search: postgresql.org/docs — tsvector, GIN indexes
- Architecture patterns: standard practices for aggregator + async worker + multi-portal submission systems (HIGH confidence)
