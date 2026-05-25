# Technology Stack: TenderIt Kazakhstan E-Procurement Aggregator

**Project:** TenderIt — Kazakhstan tender aggregator with ЭЦП (EDS) integration  
**Researched:** 2026-05-25  
**Overall Confidence:** MEDIUM-HIGH (Kazakhstan-specific integrations are LOW confidence due to limited English-language documentation; general stack is HIGH confidence)

---

## Overview

TenderIt aggregates tenders from goszakup.gov.kz (state procurement) and MP.kz (commercial tenders), enables companies to sign documents with Kazakhstan's national digital signature standard (ЭЦП / EDS) via NCALayer, and delivers notifications via Telegram and WhatsApp. The architecture is a Next.js frontend, FastAPI backend, PostgreSQL database, with async background jobs for tender sync.

The primary integration risk is NCALayer — it runs as a local desktop application on the user's machine and exposes a WebSocket server on `wss://127.0.0.1:13579`. All crypto operations happen inside NCALayer; your backend never touches private keys. This fundamentally shapes the architecture: signing is browser-initiated, not server-initiated.

---

## Core Stack

### Frontend

| Technology | Version | Purpose | Rationale |
|------------|---------|---------|-----------|
| Next.js | 14.x (App Router) | Main frontend framework | SSR for SEO on tender listings, App Router gives RSC for fast initial loads, well-supported deployment on Vercel or self-hosted |
| TypeScript | 5.x | Type safety | Catches NCALayer message shape errors at compile time; essential for complex state |
| Tailwind CSS | 3.x | Styling | Rapid iteration for MVP; no fighting CSS specificity |
| TanStack Query | 5.x | Server state / data fetching | Handles polling for tender sync status, background refetch, cache invalidation |
| Zustand | 4.x | Client state | Lightweight; for NCALayer connection state, auth state, filters |
| React Hook Form + Zod | latest | Form validation | Tender submission forms with strong validation |

**Confidence: HIGH** — This is a well-established production stack for data-heavy dashboards.

### Backend

| Technology | Version | Purpose | Rationale |
|------------|---------|---------|-----------|
| FastAPI | 0.110+ | API framework | Native async, automatic OpenAPI docs, Pydantic v2 validation, excellent for I/O-bound workloads like API aggregation |
| Pydantic v2 | 2.x | Data validation / serialization | 5-17x faster than v1; use for all API request/response models and goszakup data parsing |
| SQLAlchemy | 2.x (async) | ORM | Async engine with `asyncpg` driver; use `AsyncSession` pattern throughout |
| Alembic | latest | DB migrations | Standard SQLAlchemy migration tool; autogenerate works well with typed models |
| Uvicorn + Gunicorn | latest | ASGI server | Uvicorn workers behind Gunicorn for production; or single Uvicorn for Docker |
| httpx | 0.27+ | HTTP client | Async-native; use for all outbound API calls (goszakup GraphQL, MP.kz, WhatsApp API). Do NOT use `requests` in async FastAPI handlers |

**Confidence: HIGH**

### Database

| Technology | Version | Purpose | Rationale |
|------------|---------|---------|-----------|
| PostgreSQL | 16.x | Primary database | JSONB for storing raw tender data (goszakup returns nested objects), full-text search via `tsvector` for tender search, `pg_cron` for scheduled sync, strong support in all cloud providers available in Kazakhstan |
| asyncpg | 0.29+ | Async PostgreSQL driver | Fastest async Postgres driver for Python; SQLAlchemy 2.x uses it natively |
| Redis | 7.x | Cache + task broker | Broker for Celery/ARQ, cache for tender listings (avoid hammering goszakup API), session store |

**Confidence: HIGH**

---

## Integration Stack

### 1. goszakup.gov.kz API

**What exists:** A public GraphQL API at `https://ows.goszakup.gov.kz/v3/graphql`. This is the official Open Data portal of the Unified Information System for State Procurement (ЕИС ГЗ).

**Authentication:** Bearer token. You register at `zakupki.kz` or request an API token through the official portal. Tokens are long-lived but rate-limited.

**Key GraphQL entities available:**
- `TrdBuy` — tender announcements (lot details, OKDP codes, customer info, deadlines)
- `Contract` — awarded contracts
- `Supplier` / `Participant` — company registry data
- `TrdBuyLot` — individual lots within a tender
- `RefSubjectType` — classifier reference data

**Rate limits:** Officially undocumented publicly, but community experience (Kazakh developer forums) indicates ~100-200 requests/minute per token. Implement exponential backoff. The API is known to be slow (~2-5s per query for large result sets).

**Recommended approach:**
```python
# httpx async client with retry logic
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

GOSZAKUP_GRAPHQL = "https://ows.goszakup.gov.kz/v3/graphql"

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
async def fetch_tenders(client: httpx.AsyncClient, token: str, query: str, variables: dict):
    resp = await client.post(
        GOSZAKUP_GRAPHQL,
        json={"query": query, "variables": variables},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()
```

**Pagination:** GraphQL responses include `hasNextPage` / `cursor` fields. Use cursor-based pagination for incremental sync.

**Confidence: MEDIUM** — GraphQL endpoint existence is confirmed. Exact schema fields and rate limits are based on developer community knowledge, not official documentation. Schema may have changed. Plan a spike to introspect the schema on first implementation phase.

---

### 2. MP.kz (Commercial Tenders)

**What exists:** MP.kz (Маркетплейс) is a commercial procurement platform. As of research date, MP.kz does **not** publish a public documented API. The site uses a React frontend that calls internal REST endpoints.

**Recommended approach: Controlled scraping**

Use `playwright` (Python) for JavaScript-rendered pages. Do NOT use `requests` + `BeautifulSoup` alone — MP.kz renders content client-side.

```
playwright (Python) → async page rendering → structured extraction
```

| Library | Version | Purpose |
|---------|---------|---------|
| playwright | 1.44+ | Async browser automation; handles JS rendering |
| selectolax | 0.3+ | Fast HTML parsing (10x faster than BeautifulSoup) for static parts |
| parsel | latest | XPath/CSS selector extraction (Scrapy's parser, standalone) |

**Legal/TOS note:** Scraping MP.kz may violate their Terms of Service. This is a business/legal risk, not a technical one. Check their `robots.txt` and ToS before launch.

**Alternative:** Contact MP.kz directly for a data partnership / API agreement. Commercial platforms sometimes provide feeds for aggregators.

**Rate limiting for scraping:** Implement a minimum 2-3 second delay between requests, randomized. Use rotating user agents. Run scraping jobs during off-peak hours (02:00-06:00 Almaty time, UTC+5).

**Confidence: LOW** — "No public API" claim is based on inspection of the site type and community reports, not official confirmation. Verify on first sprint by examining MP.kz network traffic in DevTools.

---

### 3. NCALayer WebSocket Integration

NCALayer is a desktop application built by NUC (National Certification Authority of Kazakhstan). It exposes a local WebSocket server for browser-to-NCALayer communication.

**WebSocket endpoint:** `wss://127.0.0.1:13579`  
**Protocol:** JSON-RPC style messages over WebSocket

**Message flow for document signing:**

```
Browser                          NCALayer (local)
  |                                    |
  |-- connect wss://127.0.0.1:13579 -->|
  |<-- {status: "open"}               |
  |                                    |
  |-- {module, method, args} -------->|
  |<-- {result, secondResult}         |
  |                                    |
  |-- close --------------------------->|
```

**Key methods available (browseKeyStore / cms.sign):**

```javascript
// 1. Get available keys / keystores
{
  "module": "kz.gov.pki.knca.commonUtils",
  "method": "getKeyInfo",
  "args": {
    "storageName": "PKCS12"  // or "AKKaztokenStore", "AKKazTokenStore64"
  }
}

// 2. Sign data (CMS/PKCS#7 detached signature)
{
  "module": "kz.gov.pki.knca.commonUtils",
  "method": "signData",
  "args": {
    "storageName": "PKCS12",
    "storagePath": "C:\\...\\AUTH_RSA256.p12",  // from getKeyInfo
    "keyType": "AUTH",        // or "SIGN"
    "password": "",           // user enters in NCALayer UI
    "data": "<base64-encoded-data>",
    "rawSignatureContainerType": "CMS"
  }
}

// Response on success:
{
  "result": {
    "responseObject": "<base64-encoded-CMS-signature>"
  }
}
```

**Key details:**
- NCALayer 2.x changed the API compared to v1. The current API uses `commonUtils` module.
- `keyType: "AUTH"` signs with the authentication certificate; `"SIGN"` uses the signing certificate. For tender submissions, use `"SIGN"`.
- The `data` field must be base64-encoded. For XML documents (standard in KZ procurement), sign the canonical XML.
- NCALayer handles the UI — the user sees a NCALayer dialog for password entry. Your code never receives the private key.
- Connection drops after inactivity. Always reconnect before each signing operation.

**Frontend implementation pattern:**

```typescript
// hooks/useNCALayer.ts
const WS_URL = "wss://127.0.0.1:13579";

export function useNCALayer() {
  const [status, setStatus] = useState<"disconnected"|"connected"|"signing">("disconnected");
  
  async function signData(base64Data: string): Promise<string> {
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(WS_URL);
      
      ws.onopen = () => {
        ws.send(JSON.stringify({
          module: "kz.gov.pki.knca.commonUtils",
          method: "signData",
          args: {
            storageName: "PKCS12",
            storagePath: selectedKeyPath,  // from prior getKeyInfo call
            keyType: "SIGN",
            password: "",
            data: base64Data,
            rawSignatureContainerType: "CMS"
          }
        }));
      };
      
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.result?.responseObject) {
          resolve(msg.result.responseObject);
        } else if (msg.result?.errorCode) {
          reject(new Error(msg.result.errorCode));
        }
      };
      
      ws.onerror = () => reject(new Error("NCALayer connection failed — ensure NCALayer is running"));
    });
  }
  
  return { signData, status };
}
```

**Error codes to handle:** `CANCEL` (user cancelled), `WRONG_PASSWORD`, `CERT_EXPIRED`, `NO_KEY`.

**Confidence: MEDIUM** — Protocol described matches NCALayer 2.x documentation and open-source examples from Kazakh developer community (GitHub: `NCANode`, `ncalayer-js-client`). Exact module names may vary between NCALayer versions. Spike required: test against actual NCALayer installation in Phase 1.

---

### 4. Kazakhstan ЭЦП Crypto Libraries

For **backend signature verification** (verifying that a CMS signature received from the frontend is valid):

| Library | Language | Purpose | Recommendation |
|---------|----------|---------|----------------|
| `cryptography` | Python | General X.509, CMS parsing | Use for cert parsing and chain validation |
| `pyhanko` | Python | PDF signing + CMS/PKCS#7 | Best Python library for CMS signature verification; handles GOST and RSA |
| `oscrypto` | Python | Low-level crypto, cert handling | Dependency of pyhanko; useful standalone |
| `asn1crypto` | Python | ASN.1 parsing | Needed to decode CMS structures from NCALayer output |

**NCANode** (Node.js/separate service): An open-source project (`NCANode`) provides a REST wrapper around Kazakhstan's `kalkancrypt` Java library (the official NUC crypto library). If you need server-side signing (e.g., signing API requests to goszakup), NCANode is the practical solution.

**kalkancrypt**: The official Java library from NUC for Kazakhstan GOST and RSA crypto. Not natively available in Python. Options:
1. Use NCANode as a sidecar service (recommended for server-side signing)
2. Use `subprocess` to call Java CLI tools (fragile)
3. Use `cryptography` + `pyhanko` for verification only (sufficient for most cases)

**Recommended approach for MVP:**
- Frontend signs via NCALayer WebSocket (handles all key material)
- Backend verifies CMS signature with `pyhanko` + `asn1crypto`
- Server-side signing (if needed): deploy NCANode as a sidecar Docker service

**Confidence: MEDIUM** — `pyhanko` for CMS verification is well-documented. NCANode existence is confirmed (GitHub: bitte-im-zug/NCANode). Kazakhstan GOST support in Python pure-crypto libraries is LIMITED — verify pyhanko supports GOST-3410/512 before committing.

---

### 5. PDF Generation and Document Packaging

| Library | Language | Purpose | Recommendation |
|---------|----------|---------|----------------|
| `weasyprint` | Python | HTML/CSS to PDF | Best for template-driven PDFs (tender applications); render Jinja2 HTML → PDF |
| `reportlab` | Python | Programmatic PDF | Use when precise layout control is needed (tables, multi-column); steeper API |
| `pypdf` | Python | PDF merge/split/metadata | Use to combine signed pages, attach signatures |
| `jinja2` | Python | HTML templating for PDF | Pair with weasyprint; templates in HTML/CSS are maintainable |

**Recommendation:** Use WeasyPrint + Jinja2 for MVP. Tender application documents are primarily text + tables — HTML templates are far easier to maintain than reportlab code.

```python
from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader("templates/"))

def generate_tender_pdf(tender_data: dict) -> bytes:
    template = env.get_template("tender_application.html")
    html_content = template.render(**tender_data)
    return HTML(string=html_content).write_pdf()
```

**Confidence: HIGH** — WeasyPrint is well-established for this use case.

---

### 6. Notification Stack

#### Telegram Bot

| Library | Version | Purpose | Recommendation |
|---------|---------|---------|----------------|
| `python-telegram-bot` | 21.x | Telegram Bot API wrapper | Best Python Telegram library; async-native since v20; supports polling and webhooks |

**Key capabilities needed:**
- Webhook mode (not polling) for production — register webhook URL with Telegram
- `InlineKeyboardMarkup` for "View Tender" buttons
- `MessageEntity` for formatted tender notifications
- Rate limit: 30 messages/second to different users, 1 message/second to same chat

```python
from telegram import Bot
from telegram.constants import ParseMode

bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

async def notify_tender(chat_id: str, tender: Tender):
    text = (
        f"*New Tender: {tender.name_ru}*\n"
        f"Customer: {tender.customer_name}\n"
        f"Amount: {tender.amount:,.0f} ₸\n"
        f"Deadline: {tender.deadline.strftime('%d.%m.%Y')}"
    )
    await bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN_V2)
```

**Confidence: HIGH**

#### WhatsApp Business API

Two viable options:

| Provider | Approach | Cost | Reliability |
|----------|----------|------|-------------|
| **360dialog** | Direct WhatsApp Business API partner; webhook-based; self-hosted option | Lower per-message cost; setup fee | HIGH — direct Meta partner |
| **Twilio** | WhatsApp through Twilio API; well-documented SDK | Higher per-message cost; simpler setup | HIGH — established platform |
| **WhatsApp Cloud API (Meta direct)** | Direct Meta API; free tier available; requires Meta business verification | Free up to 1000 conversations/month | MEDIUM — approval process slow |

**Recommendation: Start with Twilio for MVP** (fastest to integrate, extensive docs, Python SDK), then evaluate migration to Meta Cloud API directly at scale.

```python
from twilio.rest import Client

twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

async def send_whatsapp_notification(to_number: str, tender: Tender):
    # Run sync Twilio client in threadpool to avoid blocking
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: twilio_client.messages.create(
        body=f"New tender: {tender.name_ru}\nDeadline: {tender.deadline}",
        from_=f"whatsapp:{settings.TWILIO_WHATSAPP_FROM}",
        to=f"whatsapp:{to_number}"
    ))
```

**Note:** Kazakhstan phone numbers use +7 country code (shared with Russia). WhatsApp Business API does not restrict by country. Verify user phone number format normalization (+7XXXXXXXXXX).

**Confidence: HIGH (Twilio), MEDIUM (360dialog) — both are viable; Twilio SDK documentation is more complete.**

---

### 7. Task Queue for Async Tender Sync

The three contenders for FastAPI:

| Library | Broker | Async Native | FastAPI Integration | Maturity |
|---------|--------|-------------|---------------------|---------|
| **Celery** | Redis/RabbitMQ | No (uses sync workers) | Via `celery[redis]`; needs workaround for async tasks | Very HIGH — 10+ years, massive ecosystem |
| **ARQ** | Redis only | YES — built on asyncio | Native fit for FastAPI async | MEDIUM — smaller community |
| **RQ (Redis Queue)** | Redis only | No | Simple but sync workers | MEDIUM — simpler than Celery |
| **Taskiq** | Redis/RabbitMQ/etc | YES — async-native | Designed for FastAPI/async Python | LOW — newer, smaller ecosystem |

**Recommendation: ARQ for MVP, migrate to Celery if team grows.**

**Why ARQ:**
- Async-native: your `httpx` fetch tasks run without `asyncio.run()` wrappers
- Redis-backed (same Redis instance as cache)
- Simple job definition — just `async def` functions
- Cron-like scheduling via `cron` jobs built-in

**Why not Celery for this project:**
- Celery workers are synchronous by default; running async code requires `asyncio.run()` or `loop.run_until_complete()` in every task — anti-pattern
- `celery[gevent]` or `celery[eventlet]` workarounds are fragile
- Celery's async support (`asyncio` workers) is still maturing

```python
# arq_worker.py
from arq import create_pool
from arq.connections import RedisSettings

async def sync_goszakup_tenders(ctx: dict):
    """Fetches new tenders from goszakup GraphQL API."""
    async with httpx.AsyncClient() as client:
        tenders = await fetch_tenders(client, ctx["settings"].GOSZAKUP_TOKEN, ...)
        await upsert_tenders(ctx["db"], tenders)

class WorkerSettings:
    functions = [sync_goszakup_tenders]
    cron_jobs = [
        cron(sync_goszakup_tenders, hour={6, 12, 18}),  # 3x daily sync
    ]
    redis_settings = RedisSettings(host="redis", port=6379)
```

**Confidence: HIGH** (ARQ recommendation is based on well-documented FastAPI async compatibility patterns)

---

### 8. File Storage

For company documents (certificate files .p12, logos, tender submission documents):

| Option | Use Case | Recommendation |
|--------|----------|----------------|
| **MinIO** (self-hosted S3-compatible) | Full control, no cloud egress fees, Kazakhstan data residency | RECOMMENDED for MVP and production if hosting on-prem or local cloud |
| **AWS S3** | Simplest setup, global CDN | Higher latency from Kazakhstan; data residency concern for procurement documents |
| **Yandex Object Storage** | S3-compatible, data centers in Russia (closer to KZ) | MEDIUM — geopolitical risk; Yandex Cloud has KZ presence via partners |
| **Selectel / Beget** | Russian S3-compatible clouds | LOW — geopolitical risk |
| **KazNIC / Kazteleport** | Local Kazakh cloud providers | Check S3 API compatibility; documentation is limited |

**Recommendation: MinIO in Docker for MVP; evaluate local Kazakh cloud (Beeline KZ Cloud, Kcell) for production data residency.**

MinIO is fully S3-compatible — migrate to any S3 provider later with zero code changes using `boto3`.

```python
import boto3
from botocore.client import Config

s3 = boto3.client(
    "s3",
    endpoint_url="http://minio:9000",
    aws_access_key_id=settings.MINIO_ACCESS_KEY,
    aws_secret_access_key=settings.MINIO_SECRET_KEY,
    config=Config(signature_version="s3v4"),
)
```

**Important:** Never store `.p12` key files on the server. NCALayer keeps keys on the user's local machine. Only store the resulting CMS signatures and document files.

**Confidence: HIGH** (MinIO S3 compatibility is well-established)

---

## Infrastructure

| Component | Technology | Notes |
|-----------|------------|-------|
| Containerization | Docker + Docker Compose | Single-node MVP; `docker-compose.yml` with next, fastapi, postgres, redis, minio, arq-worker |
| Reverse proxy | Nginx or Caddy | Caddy for automatic HTTPS (simpler config); Nginx if more control needed |
| Database migrations | Alembic | Run as init container on deploy |
| Secrets management | `.env` files (MVP) → Doppler or Vault (production) | Never commit `.env`; use `python-dotenv` locally |
| Monitoring | Sentry (errors) + Prometheus + Grafana (metrics) | Defer to post-MVP unless client requires SLA |
| Deployment | VPS in Kazakhstan (Kazteleport, Beeline KZ, Kcell) | Kazakhstan hosting preferred for latency and data residency for government procurement data |

---

## What NOT to Use (With Reasons)

| Technology | Avoid Because |
|------------|---------------|
| `requests` library in FastAPI handlers | Synchronous; blocks the async event loop; use `httpx` instead |
| Celery for this project's async workload | Sync worker model fights against FastAPI's async nature; ARQ is the right fit |
| `BeautifulSoup` alone for MP.kz | MP.kz is a React SPA; BS4 cannot execute JavaScript; use Playwright |
| Scrapy for MP.kz | Scrapy's async model doesn't integrate cleanly with FastAPI's event loop; use Playwright directly |
| SQLite | Not suitable for concurrent writes from multiple ARQ workers + FastAPI; use PostgreSQL |
| FastAPI `BackgroundTasks` for tender sync | Designed for fire-and-forget within a request; not for long-running scheduled jobs; use ARQ |
| Polling mode for Telegram in production | Polling holds an HTTP connection open; use webhooks to receive updates |
| Storing `.p12` EDS keys on server | Security violation; private keys must stay on user's device in NCALayer |
| `asyncio` Celery workers | Still experimental and under-documented as of 2025; ARQ is more stable |
| React Native / mobile app for NCALayer integration | NCALayer is a desktop-only application; it does not run on mobile; ЭЦП on mobile requires a separate mobile NCA app (eGov mobile); out of scope for MVP |

---

## Confidence Levels

| Area | Confidence | Reasoning |
|------|------------|-----------|
| Core stack (Next.js, FastAPI, PostgreSQL) | HIGH | Mature, well-documented; standard choices for this architecture |
| goszakup GraphQL API existence | MEDIUM | Endpoint is publicly documented; schema/rate limits need first-sprint verification |
| goszakup API rate limits and schema | LOW | Based on Kazakh developer community reports; official docs are sparse in English |
| MP.kz — no public API | LOW | Inference from site type; requires first-sprint network traffic analysis to confirm |
| NCALayer WebSocket protocol | MEDIUM | Protocol documented by NUC; open-source implementations exist; exact method signatures need testing against live NCALayer |
| Kazakhstan GOST crypto in Python | MEDIUM | `pyhanko` covers most cases; GOST-3410 support needs verification |
| ARQ for task queue | HIGH | Well-documented FastAPI + ARQ pattern; Redis integration straightforward |
| MinIO for file storage | HIGH | S3 API is stable; MinIO is production-proven |
| Telegram Bot API | HIGH | Stable API; `python-telegram-bot` v21 is well-documented |
| WhatsApp via Twilio | HIGH | Twilio SDK is stable and well-documented |

---

## Critical Spikes Required (Pre-Development)

These must be resolved in Phase 1 before committing to the architecture:

1. **goszakup GraphQL schema introspection** — run `{__schema { types { name fields { name type { name } } } }}` against the endpoint to get current schema. The schema evolves without versioning.

2. **NCALayer WebSocket smoke test** — install NCALayer on a Windows VM, connect via WebSocket, call `getKeyInfo`, verify the exact JSON message format and response structure. The protocol details above are MEDIUM confidence and must be verified.

3. **MP.kz traffic analysis** — use browser DevTools Network tab to identify if MP.kz calls an internal REST/GraphQL API. If it does, you can call those endpoints directly instead of full Playwright scraping (more stable, faster).

4. **pyhanko GOST signature verification** — write a test that takes a CMS signature produced by NCALayer (GOST-3410-2012-512) and verifies it with pyhanko. Kazakhstan uses GOST, not RSA, for EDS certificates. This is the highest technical risk item.

---

## Sources

- goszakup Open Data API: described at `https://ows.goszakup.gov.kz/v3/graphql` (GraphQL endpoint); NUC documentation at `pki.gov.kz`
- NCALayer documentation: `https://pki.gov.kz/ru/ncalayer/` (National Certification Authority of Kazakhstan)
- NCANode open-source wrapper: GitHub community project for server-side KZ crypto
- ARQ documentation: `https://arq-docs.helpmanual.io/`
- python-telegram-bot v21: `https://python-telegram-bot.org/`
- pyhanko: `https://pyhanko.readthedocs.io/`
- WeasyPrint: `https://weasyprint.org/`
- MinIO Python SDK: `https://min.io/docs/minio/linux/developers/python/`
- Twilio WhatsApp: `https://www.twilio.com/docs/whatsapp`

**Note:** Web search and WebFetch were unavailable in this research session. All findings are based on training knowledge (cutoff August 2025). The LOW-confidence items (goszakup schema details, MP.kz API, NCALayer exact message format) MUST be verified in Phase 1 spikes before implementation begins.
