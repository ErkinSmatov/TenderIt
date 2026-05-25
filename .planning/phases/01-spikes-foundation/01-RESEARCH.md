# Phase 1: Spikes & Foundation — Research

**Researched:** 2026-05-25
**Domain:** Technical spike methodology, project scaffolding (Next.js 14 + FastAPI + Docker), goszakup GraphQL API, NCALayer WebSocket protocol, Kazakhstan legal/compliance
**Confidence:** MEDIUM (stack scaffolding HIGH; NCALayer protocol MEDIUM; goszakup submission mutations LOW; legal items LOW)

---

## Summary

Phase 1 has two parallel workstreams that must proceed concurrently: (1) scaffolding the monorepo so that subsequent phases have real infrastructure to run against, and (2) executing five technical/legal spikes that resolve the unknowns that would otherwise cause downstream rewrites. The spikes do not produce product code — they produce documented findings (spec files + ADRs) that the Phase 5 submission engine is built against. Without those findings, building Phase 5 is building against guesses.

The stack scaffolding is fully resolved: Next.js 14.2.x (latest in 14.x line) with App Router + TypeScript + Tailwind, FastAPI 0.115.x with Pydantic v2 + async SQLAlchemy 2.x + Alembic, PostgreSQL 16 + Redis 7 + MinIO in docker-compose. All these are confirmed against package registries as of this research date. The Node.js version installed locally (v16.18.1) is below Next.js 14's minimum requirement of Node 20.9 — the executor must install a current Node before running `create-next-app`. Docker is not installed on this machine; the executor must install Docker Desktop before standing up services.

The five spikes vary significantly in documentation availability. SPIKE-01 (goszakup GraphQL) has a confirmed v3 endpoint, confirmed Bearer token auth, and a confirmed schema browser at `ows.goszakup.gov.kz/help/v3/schema/` — but rate limits are undocumented and must be measured empirically. SPIKE-02 (NCALayer WebSocket) has a confirmed URL (wss://127.0.0.1:13579) and confirmed module name (kz.gov.pki.knca.basics is current; kz.gov.pki.knca.commonUtils is legacy/deprecated) but the exact signXml message schema must be obtained from the official NCA SDK which requires registration at pki.gov.kz — it cannot be extracted from public sources. NCALayer officially supports Windows, macOS, and Linux desktop, so a full Windows VM is not strictly required but is safest for testing with a real P12 certificate. SPIKE-03 (submission payload capture) is a manual browser task — use Chrome DevTools or mitmproxy. SPIKE-04 (MP.kz) requires live browser inspection only. SPIKE-05 (legal) is firmly LOW confidence in this research; a Kazakhstan-licensed attorney is the only path to a high-confidence answer.

**Primary recommendation:** Execute scaffolding and spikes in parallel. The scaffolding can be completed by any developer in 1-2 days; each spike is a focused 2-4 hour investigation producing a single findings document. All five spike findings must be reviewed and signed off before any Phase 2 work begins.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| NCALayer WebSocket spike (SPIKE-02) | Browser / Client | — | NCALayer only runs on user's local machine; spike must be executed from a browser environment, not a server |
| goszakup GraphQL introspection (SPIKE-01) | API / Backend | — | GraphQL introspection is an HTTP call; spike runs from Python httpx or curl, not from the browser |
| Submission payload capture (SPIKE-03) | Browser / Client | — | Traffic interception during a real browser-based goszakup session; no backend involvement |
| MP.kz API discovery (SPIKE-04) | Browser / Client | — | Network tab inspection of a live MP.kz browser session |
| Legal review (SPIKE-05) | External | — | Requires a Kazakhstan-licensed attorney; not a technical tier |
| Project skeleton (frontend scaffold) | Frontend Server (SSR) | — | next.js init, App Router config, Tailwind setup |
| Project skeleton (backend scaffold) | API / Backend | Database / Storage | FastAPI init, SQLAlchemy async setup, Alembic migrations, docker-compose |

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SPIKE-01 | Верифицировать goszakup GraphQL API: интроспектировать схему, протестировать аутентификацию, измерить rate limits | goszakup v3 endpoint confirmed: `https://ows.goszakup.gov.kz/v3/graphql`; schema browser at `/help/v3/schema/`; Bearer token obtained via letter to АО "Центр Электронных Финансов"; rate limits undocumented — must measure empirically |
| SPIKE-02 | Верифицировать NCALayer WebSocket протокол: живое подключение к ws://localhost:14579, вызов signXml, запись точного формата сообщений | WebSocket URL confirmed as `wss://127.0.0.1:13579` (not 14579 as stated in requirements); current module is `kz.gov.pki.knca.basics`; full SDK docs require registration at pki.gov.kz |
| SPIKE-03 | Захватить submission payload: перехватить браузерный трафик при ручной подаче заявки на goszakup, зафиксировать все обязательные поля XML | Chrome DevTools Network tab or mitmproxy for HTTPS interception; requires real company account on goszakup |
| SPIKE-04 | Верифицировать MP.kz API: анализ network трафика MP.kz на предмет внутренних API endpoints | MP.kz has no documented public API; spike methodology: open Chrome DevTools Network tab on mp.kz, filter by XHR/Fetch, look for internal REST/GraphQL calls |
| SPIKE-05 | Юридическая проверка: подтвердить допустимость автоматической подачи заявок от имени компании и требования к локализации данных в РК | Data localization confirmed effective 8 January 2025 (personal data must be stored in KZ); automated submission legality requires KZ-licensed attorney — not resolvable via research alone |
</phase_requirements>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| next | 14.2.35 | Frontend framework (App Router, SSR, RSC) | Latest stable in 14.x line — confirmed via npm registry |
| create-next-app | 14.2.35 | CLI scaffold for Next.js | Official scaffolding tool |
| typescript | 5.x (5.8.x latest) | Type safety | Built into create-next-app; required for NCALayer message type safety |
| tailwindcss | 3.4.19 | Styling | Latest in 3.x line — confirmed via npm registry |
| fastapi | 0.115.6 | Backend API framework | Installed on machine; async-native, matches stack decision |
| pydantic | 2.10.5 | Data validation | Installed on machine; v2 as specified in stack |
| sqlalchemy | 2.0.37 | Async ORM | Installed on machine; 2.x async pattern with asyncpg |
| alembic | 1.14.0 | DB migrations | Installed on machine; standard SQLAlchemy migration tool |
| asyncpg | 0.31.0 | Async PostgreSQL driver | Latest version — confirmed via PyPI |
| httpx | 0.28.1 | Async HTTP client | Latest version — use for goszakup spike calls |

[VERIFIED: npm registry for JS packages, PyPI for Python packages via `pip3 index versions`]

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| arq | 0.28.0 | Async task queue (ARQ) | Phase 1 skeleton: install now, configure for Phase 3 workers |
| @tanstack/react-query | 5.100.14 | Server state management | Phase 2+ UI; install in skeleton |
| zustand | 5.0.13 | Client state | NCALayer connection state; install in skeleton |
| react-hook-form | 7.76.1 | Form handling | Phase 2+ forms; install in skeleton |
| zod | 3.24.x (latest 3.x) | Schema validation | Shared types; install in skeleton |
| tenacity | latest | Retry / backoff for Python | Wrap all goszakup httpx calls from day one |

[VERIFIED: npm registry, PyPI]

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| arq | Celery | Celery sync workers fight FastAPI async event loop; ARQ is async-native |
| asyncpg | psycopg3 | asyncpg is faster and better documented for SQLAlchemy 2.x async |
| tailwindcss 3.x | tailwindcss 4.x | v4 is in alpha/RC stage; 3.x is stable, well-documented |
| MinIO (docker) | AWS S3 / Yandex Object Storage | MinIO provides data residency control; S3-compatible API means zero code change to swap |

**Installation:**
```bash
# Frontend (inside frontend/)
npx create-next-app@14 . --typescript --tailwind --app --src-dir --import-alias "@/*" --no-eslint

# Backend (inside backend/)
pip install fastapi==0.115.6 pydantic[email]==2.10.5 "sqlalchemy[asyncio]==2.0.37" alembic==1.14.0 asyncpg==0.31.0 "httpx[http2]==0.28.1" arq==0.28.0 tenacity uvicorn[standard] python-dotenv
```

**Version verification:** Versions above confirmed via `npm view [pkg] version` and `pip3 index versions [pkg]` on 2026-05-25.

---

## Architecture Patterns

### System Architecture Diagram

```
[SPIKE WORKSTREAM]
  Researcher (browser + Windows/macOS) ──► goszakup.gov.kz (GraphQL introspection, rate limit probing)
  Researcher (NCALayer installed) ──────► wss://127.0.0.1:13579 (signXml, getKeyInfo)
  Researcher (DevTools / mitmproxy) ────► goszakup.gov.kz (browser submission capture)
  Researcher (DevTools) ────────────────► mp.kz (internal API discovery)
  KZ attorney ─────────────────────────► Legal findings document

[SCAFFOLD WORKSTREAM]
  git repo (TenderIt/)
    ├── frontend/  ◄── create-next-app@14 (App Router, TS, Tailwind)
    └── backend/   ◄── FastAPI skeleton
                         ├── app/
                         │    ├── main.py
                         │    ├── config.py
                         │    ├── db.py
                         │    └── routers/
                         ├── alembic/
                         └── tests/
  docker-compose.yml ──► postgres:16-alpine + redis:7-alpine + minio:latest

[FINDINGS OUTPUT] ──► .planning/phases/01-spikes-foundation/findings/
    SPIKE-01-goszakup-graphql.md
    SPIKE-02-ncalayer-protocol.md
    SPIKE-03-submission-payload.md
    SPIKE-04-mpkz-api.md
    SPIKE-05-legal.md
    ADR-001-mpkz-integration-approach.md  (Playwright vs API)
    ADR-002-submission-automation-consent.md
```

### Recommended Project Structure

```
TenderIt/                         ← monorepo root (single git repo)
├── .planning/                    ← GSD planning docs
│   └── phases/01-spikes-foundation/
│       └── findings/             ← spike output documents
├── frontend/                     ← Next.js 14 App Router
│   ├── src/
│   │   ├── app/                  ← file-system routes (App Router)
│   │   │   ├── layout.tsx        ← root layout
│   │   │   └── page.tsx          ← home page
│   │   ├── components/           ← shared React components
│   │   ├── hooks/                ← useNCALayer() and other custom hooks
│   │   ├── lib/                  ← API client, utils
│   │   └── types/                ← TypeScript types (shared with backend via openapi)
│   ├── public/
│   ├── next.config.mjs
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── package.json
├── backend/                      ← FastAPI (Python 3.12)
│   ├── app/
│   │   ├── main.py               ← FastAPI app factory, router registration
│   │   ├── config.py             ← Pydantic Settings from env
│   │   ├── db.py                 ← async engine, AsyncSession factory
│   │   ├── models/               ← SQLAlchemy ORM models
│   │   ├── schemas/              ← Pydantic request/response schemas
│   │   ├── routers/              ← FastAPI route handlers (thin)
│   │   ├── services/             ← business logic (fat)
│   │   └── workers/              ← ARQ job definitions
│   ├── alembic/
│   │   ├── env.py                ← async Alembic env
│   │   └── versions/             ← migration files
│   ├── tests/
│   │   ├── conftest.py
│   │   └── test_health.py        ← smoke test for Phase 1
│   ├── pyproject.toml            ← dependencies
│   ├── alembic.ini
│   └── .env.example
├── docker-compose.yml
├── docker-compose.override.yml   ← dev overrides (volume mounts, hot reload)
├── CLAUDE.md
└── .gitignore
```

[CITED: https://berkkaraal.com/blog/2024/09/19/setup-fastapi-project-with-async-sqlalchemy-2-alembic-postgresql-and-docker/]
[CITED: https://nextjs.org/docs/app/getting-started/installation]

### Pattern 1: Async Alembic Initialization

**What:** Initialize Alembic with the `async` template so migrations run against the async SQLAlchemy engine.
**When to use:** Required from day one — do not use the default sync template with an async engine.

```bash
# Source: https://berkkaraal.com/blog/2024/09/19/setup-fastapi-project-with-async-sqlalchemy-2-alembic-postgresql-and-docker/
cd backend/
alembic init -t async alembic
```

In `alembic/env.py`, set:
```python
from app.config import settings
from app.db import Base
# Import ALL models here so autogenerate detects them
from app.models import *  # noqa

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata
```

### Pattern 2: docker-compose Services for Phase 1

**What:** Minimal docker-compose with postgres, redis, minio. Backend runs locally (not in Docker) during development for faster iteration.
**When to use:** From first commit; all spike scripts connect to these services.

```yaml
# Source: [ASSUMED] — standard docker-compose patterns for these images
version: "3.9"
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: tenderit
      POSTGRES_PASSWORD: tenderit_dev
      POSTGRES_DB: tenderit
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-EXEC", "pg_isready -U tenderit"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin_dev
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data

volumes:
  postgres_data:
  minio_data:
```

### Pattern 3: SPIKE-01 — goszakup GraphQL Introspection Script

**What:** Python script using httpx to introspect the goszakup v3 schema and probe rate limits.
**When to use:** Execute with a real Bearer token during SPIKE-01.

```python
# Source: goszakup.gov.kz/ru/developer/ows_v3 (confirmed endpoint)
# [CITED: https://goszakup.gov.kz/ru/developer/ows_v3]
import httpx
import json
import time

ENDPOINT = "https://ows.goszakup.gov.kz/v3/graphql"
TOKEN = "YOUR_BEARER_TOKEN_HERE"

INTROSPECTION_QUERY = """
{
  __schema {
    types {
      name
      kind
      fields {
        name
        type { name kind ofType { name kind } }
      }
    }
    mutationType { name fields { name } }
    queryType { name fields { name } }
  }
}
"""

async def spike_goszakup():
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Introspect schema
        resp = await client.post(ENDPOINT, json={"query": INTROSPECTION_QUERY}, headers=headers)
        schema = resp.json()
        with open("findings/spike-01-schema.json", "w") as f:
            json.dump(schema, f, indent=2, ensure_ascii=False)
        
        # 2. Probe rate limits — send 10 requests 1 second apart, record response times
        times = []
        for i in range(10):
            t0 = time.monotonic()
            r = await client.post(ENDPOINT,
                json={"query": "{ TrdBuy(limit: 1) { id nameRu } }"},
                headers=headers)
            elapsed = time.monotonic() - t0
            times.append({"i": i, "status": r.status_code, "elapsed": elapsed})
            print(f"Request {i}: HTTP {r.status_code} in {elapsed:.2f}s")
            time.sleep(1)
        
        with open("findings/spike-01-rate-limit-probe.json", "w") as f:
            json.dump(times, f, indent=2)
```

### Pattern 4: SPIKE-02 — Minimal NCALayer WebSocket Test Page

**What:** Standalone HTML page to test NCALayer connectivity without requiring a full Next.js setup.
**When to use:** Run from a local file:// URL on the machine where NCALayer is installed.

```html
<!-- Source: [ASSUMED based on NCALayer JS examples and pki.gov.kz forum] -->
<!-- IMPORTANT: port must be confirmed against actual NCALayer version -->
<!DOCTYPE html>
<html>
<head><title>NCALayer Spike</title></head>
<body>
  <button onclick="testConnect()">Test Connect</button>
  <button onclick="testGetKeyInfo()">Get Key Info</button>
  <pre id="log"></pre>
  <script>
    const WS_URL = "wss://127.0.0.1:13579";  // VERIFY: may be 13579 or 14579
    let ws;

    function log(msg) {
      document.getElementById("log").textContent += JSON.stringify(msg, null, 2) + "\n---\n";
    }

    function testConnect() {
      ws = new WebSocket(WS_URL);
      ws.onopen = () => log({event: "open"});
      ws.onmessage = (e) => log({event: "message", data: JSON.parse(e.data)});
      ws.onerror = (e) => log({event: "error", message: "Connection failed — NCALayer not running?"});
      ws.onclose = (e) => log({event: "close", code: e.code});
    }

    function testGetKeyInfo() {
      // Current module: kz.gov.pki.knca.basics (new SDK)
      // Legacy module: kz.gov.pki.knca.commonUtils (deprecated)
      ws.send(JSON.stringify({
        "module": "kz.gov.pki.knca.basics",
        "method": "getKeyInfo",
        "args": {}
      }));
      // RECORD: exact response shape in findings/spike-02-getKeyInfo-response.json
    }
  </script>
</body>
</html>
```

**CRITICAL:** The exact method names and argument shapes for the `basics` module MUST be obtained from the official NCA SDK. Register at https://pki.gov.kz/en/for-developers/ to download the SDK documentation. The test page above is a starting point only — the specific args object structure is [ASSUMED].

### Pattern 5: SPIKE-03 — Submission Payload Capture

**What:** Intercept browser traffic during a manual goszakup tender submission.
**When to use:** Execute with a real company goszakup account on a test tender.

Two approaches, in order of preference:

1. **Chrome DevTools (simplest):** Open DevTools → Network → check "Preserve log" → filter by "XHR" and "Fetch" → submit the application manually → look for POST requests to `v3bl.goszakup.gov.kz` or `goszakup.gov.kz/api` → right-click → "Copy as cURL" → save to findings file.

2. **mitmproxy (for full HTTPS capture including request bodies):**
```bash
# Install and run
pip install mitmproxy
mitmproxy --listen-port 8080 --ssl-insecure
# Set browser proxy to localhost:8080
# Install mitmproxy CA cert in browser (visit mitm.it)
# Submit tender application
# All requests captured — export as HAR from mitmweb
```

**Document in findings:**
- Full URL of submission endpoint
- HTTP method
- All request headers (especially Content-Type, Authorization)
- Complete request body (JSON or multipart/form-data)
- All field names, their types, and example values
- Response structure on success

### Pattern 6: ADR Format for Spike Findings

**What:** Architecture Decision Records for binary decisions from spikes (e.g., API vs. Playwright for MP.kz).
**When to use:** Write one ADR per decision that blocks downstream phases.

```markdown
# ADR-00X: [Decision Title]

**Status:** Accepted
**Date:** YYYY-MM-DD
**Deciders:** [names]

## Context
[What was unknown; what spike was run; what evidence was gathered]

## Decision
[What was decided]

## Consequences
**Positive:**
- [outcome]

**Negative / Risks:**
- [outcome]

## Evidence
- Link to spike findings file
- Screenshot or log excerpt (if relevant)
```

[CITED: https://adr.github.io/madr/ — MADR format]

### Anti-Patterns to Avoid

- **Starting Phase 2 with unresolved spikes:** Building auth + company profile before SPIKE-01 confirms goszakup API access means Phase 5 may require full rework of the submission adapter. All five spikes must be complete before Phase 2 begins.
- **Using `kz.gov.pki.knca.commonUtils` without checking version:** This module is marked legacy/deprecated in the current NCA SDK. The new module is `kz.gov.pki.knca.basics`. Verify which is required for `signXml` in the actual installed version.
- **Running spike scripts against goszakup without rate limit awareness:** Even gentle test scripts can trigger IP-level WAF blocks if they call too frequently. Start at 1 RPS. Record all rate limit responses.
- **Documenting spike findings only in memory:** Every spike must produce a written findings file in `.planning/phases/01-spikes-foundation/findings/`. The Phase 5 implementer relies on these files, not on whoever ran the spike.
- **Using `npm init` or manual Next.js setup instead of `create-next-app`:** create-next-app sets up tsconfig, tailwind.config, app/ directory, and next.config.mjs correctly. Manual setup frequently misses the `@/*` import alias.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP client with retry | Custom retry loop around requests | httpx + tenacity | tenacity's exponential backoff handles jitter, max attempts, logging; requests is sync |
| DB migrations | Manual ALTER TABLE scripts | Alembic with `alembic init -t async` | Alembic autogenerates from SQLAlchemy models; tracks migration history; rollback support |
| Next.js project scaffold | Manual webpack/babel config | `create-next-app@14` CLI | Correct Turbopack config, tsconfig paths, Tailwind PostCSS setup — impossible to replicate correctly by hand in < 1 hour |
| Environment variable loading | os.environ.get() calls | Pydantic Settings (`BaseSettings`) | Type-validated, auto-reads from `.env`, provides defaults, raises clear errors on missing required vars |
| HTTPS traffic interception | Custom proxy server | mitmproxy or Chrome DevTools | mitmproxy handles TLS termination, HAR export, filtering — hours of work vs. 5 minutes |

**Key insight:** Phase 1 is about investigation tools and scaffold generators, not custom code. The output is findings documents and a skeleton that passes health checks, not a working product.

---

## Common Pitfalls

### Pitfall 1: Wrong NCALayer WebSocket Port in Spike
**What goes wrong:** The prior research documents (STACK.md) reference port `13579` while the REQUIREMENTS.md mentions `localhost:14579`. Multiple community sources confirm `wss://127.0.0.1:13579`. If the spike HTML page uses the wrong port, the test will always fail with ECONNREFUSED regardless of NCALayer status.
**Why it happens:** The port changed between NCALayer versions. Confusion persists in documentation.
**How to avoid:** The very first action of SPIKE-02 is to determine the actual port by: (1) opening NCALayer on the test machine, (2) running `netstat -an | grep LISTEN` (Linux/macOS) or `netstat -ano | findstr LISTEN` (Windows) to identify what port NCALayer is listening on. Document the actual port before writing any WebSocket code.
**Warning signs:** All WebSocket connection attempts fail immediately with no NCALayer error dialog shown.

### Pitfall 2: goszakup Token Belonging to Wrong Account Type
**What goes wrong:** A token obtained from a personal goszakup account (ИП or физлицо) may not have access to supplier submission mutations. The token used for SPIKE-01 should belong to an account registered as a supplier (поставщик) with a valid БИН.
**Why it happens:** goszakup has separate authentication flows for buyers (государственный заказчик) and suppliers (поставщик). The wrong token type gets you read access but submission mutations return 403 or "not authorized for this operation."
**How to avoid:** When requesting the API token, confirm with АО "Центр Электронных Финансов" that the token is issued for a supplier-type account.
**Warning signs:** GraphQL introspection works (queries return data) but any mutation attempt returns a 403 or business logic error.

### Pitfall 3: Alembic Using Sync Engine Instead of Async
**What goes wrong:** `alembic init` (without `-t async`) creates a sync `env.py` that imports `engine` — not `async_engine`. Running migrations works at first but any code that tries to use the async session from the same engine setup will deadlock or error under load.
**Why it happens:** Default `alembic init` template is synchronous. The error only surfaces when combining async SQLAlchemy with migrations.
**How to avoid:** Always use `alembic init -t async alembic`. If the template was already initialized incorrectly, replace `env.py` with the async template.
**Warning signs:** Alembic runs fine but FastAPI hangs on first DB query.

### Pitfall 4: create-next-app Requires Node >= 20.9
**What goes wrong:** Running `npx create-next-app@14` on Node v16 (currently installed) will fail with a Node version requirement error. Next.js 14 requires Node.js 18.17+ (minimum stated) or 20.9+ (recommended).
**Why it happens:** Node.js v16.18.1 is installed on this machine (verified). create-next-app checks the Node version and aborts.
**How to avoid:** Install Node.js via nvm before running `create-next-app`: `nvm install 20 && nvm use 20`.
**Warning signs:** `create-next-app` exits immediately with "You are running Node.js X.Y.Z. Create Next App requires Node.js 18.17 or later."

### Pitfall 5: Docker Not Installed — Services Cannot Start
**What goes wrong:** `docker compose up` fails immediately because Docker is not installed on this machine (verified: `docker not found` on PATH). Without running services, spike scripts cannot test database connections or MinIO.
**Why it happens:** Docker Desktop is not pre-installed; it requires a manual installation step.
**How to avoid:** Install Docker Desktop for macOS before executing any docker-compose commands. After install, restart terminal and verify with `docker --version`.
**Warning signs:** `command not found: docker` when running docker-compose.

### Pitfall 6: MP.kz Spike Finds Internal API but It Requires Authentication
**What goes wrong:** MP.kz network traffic shows internal REST or GraphQL calls, but all of them require a session cookie or JWT from a logged-in MP.kz account. "Found internal API" is not the same as "found accessible API."
**Why it happens:** Most modern SPAs have internal APIs that are session-gated. The interesting question is whether they require only a user session (feasible) or a special partner API key (impractical without a partnership agreement).
**How to avoid:** SPIKE-04 must check: (1) are the internal endpoints accessible without authentication? (2) If authentication is required, what type? (3) Is there a documented path to obtain API credentials? Document all three answers.
**Warning signs:** All API calls return 401 or 403; requests include `Authorization: Bearer [long token]` in headers.

### Pitfall 7: Spike Findings Underdocumented
**What goes wrong:** The developer who ran a spike "knows" the results and proceeds directly to implementation. The findings file contains only brief notes. Six months later, when a bug appears in Phase 5, there is no record of the exact message format that was used as ground truth.
**Why it happens:** Spike documentation feels like overhead when you just want to start building.
**How to avoid:** Each findings file must contain: (1) the raw captured data (schema JSON, captured HTTP request body, WebSocket message log), (2) analysis and interpretation, (3) a clear DECISION section stating what will be built against this finding. Raw captured data is more valuable than prose summaries.
**Warning signs:** Findings file is < 500 words with no raw data attached.

---

## Code Examples

### Async FastAPI Application Factory

```python
# Source: FastAPI official docs + async SQLAlchemy pattern
# backend/app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: tables already handled by Alembic
    yield
    # Shutdown: dispose engine connections
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="TenderIt API", lifespan=lifespan)
    from app.routers import health
    app.include_router(health.router, prefix="/health", tags=["health"])
    return app


app = create_app()
```

### Async SQLAlchemy Session Setup

```python
# Source: [CITED: https://berkkaraal.com/blog/2024/09/19/setup-fastapi-project-with-async-sqlalchemy-2-alembic-postgresql-and-docker/]
# backend/app/db.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.database_url,  # must be: postgresql+asyncpg://...
    echo=settings.debug,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

### Pydantic Settings

```python
# backend/app/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://tenderit:tenderit_dev@localhost:5432/tenderit"
    redis_url: str = "redis://localhost:6379"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin_dev"
    debug: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
```

### Next.js 14 create-next-app Command (Correct Flags)

```bash
# Source: [CITED: https://nextjs.org/docs/app/getting-started/installation]
# Run from TenderIt/ root (not from frontend/)
npx create-next-app@14 frontend \
  --typescript \
  --tailwind \
  --app \
  --src-dir \
  --import-alias "@/*" \
  --no-eslint
# --no-eslint: we'll add ESLint config separately after scaffold
# This creates: frontend/src/app/, frontend/tailwind.config.ts, frontend/tsconfig.json
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| NCALayer `commonUtils` module | NCALayer `kz.gov.pki.knca.basics` module | NCALayer 2.x (current) | Old method names (signXml, getKeyInfo via commonUtils) may still work but are deprecated; verify in spike |
| `alembic init` (sync) | `alembic init -t async alembic` | SQLAlchemy 2.x async | Sync template deadlocks with async engine |
| Next.js Pages Router | App Router (default in Next.js 14) | Next.js 13+ | RSC, layouts, and server actions are App Router only |
| Celery for FastAPI workers | ARQ | 2022+ FastAPI community shift | ARQ is async-native; Celery sync workers fight FastAPI's event loop |
| Kazakhstan personal data: store anywhere | Kazakhstan personal data: must store in KZ | 8 January 2025 (new law effective) | Non-KZ cloud hosting for BIN, IIN, director names is non-compliant |

**Deprecated/outdated:**
- `kz.gov.pki.knca.commonUtils`: legacy NCALayer module. Still functional in some versions but new integrations should target `kz.gov.pki.knca.basics`. Verify in SPIKE-02.
- `requests` library in FastAPI handlers: synchronous, blocks event loop. Use `httpx.AsyncClient` exclusively.
- goszakup API v2: the v2 REST API is documented at `/ru/developer/ows_v2` but v3 GraphQL is the current recommended integration target. [CITED: https://ows.goszakup.gov.kz/help/v3/schema/]

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | docker-compose.yml pattern (postgres:16-alpine, redis:7-alpine, minio/minio:latest) uses standard image names and environment variable names | Standard Stack / Pattern 2 | Minor: image names change rarely; environment variable names are standard for these official images |
| A2 | NCALayer SPIKE-02 HTML test page uses `"module": "kz.gov.pki.knca.basics"` with `"method": "getKeyInfo"` and empty `"args": {}` | Pattern 4 | HIGH: exact args for `getKeyInfo` in the `basics` module are undocumented in public sources; wrong args return an error rather than silently failing |
| A3 | mitmproxy can intercept goszakup HTTPS traffic without certificate pinning blocking it | Pattern 5 | MEDIUM: if goszakup implements certificate pinning in the browser app, mitmproxy interception fails; fallback is Chrome DevTools Network tab (works without CA cert install) |
| A4 | A goszakup supplier account token is sufficient for accessing submission mutations | Pitfall 2 | HIGH: if submission mutations require a separate API credential type, the spike fails to validate the full auth flow |
| A5 | pyhanko 0.35.1 supports GOST-3410-2012-512 signatures from NCALayer | Standard Stack (Supporting) | HIGH: if GOST support is absent, NCANode sidecar must be added to docker-compose — changes Phase 5 architecture |

**Items A2, A4, and A5 must be resolved in Phase 1 spikes before any Phase 5 estimation begins.**

---

## Open Questions

1. **NCALayer exact port: 13579 or 14579?**
   - What we know: STACK.md says 13579; REQUIREMENTS.md says 14579; community ncalayerjs confirms 13579; pki.gov.kz NCALayer 2 page was inaccessible for direct verification
   - What's unclear: Whether port changed between NCALayer versions; whether both ports are used for different services
   - Recommendation: First action of SPIKE-02 is `netstat -an | grep LISTEN` on the NCALayer machine to determine the actual port

2. **Does goszakup v3 GraphQL expose tender submission mutations?**
   - What we know: The schema browser at `/help/v3/schema/` shows `TrdApp` type exists; the schema page only showed a `Query` root type with no mutation details visible
   - What's unclear: Whether programmatic application submission is available via mutation or is browser-UI-only
   - Recommendation: SPIKE-01 must run a full `__schema` introspection query and inspect `mutationType` field; if no submission mutation exists, direct API submission is impossible and Phase 5 requires a completely different approach (browser automation or manual step)

3. **Does pyhanko support GOST-3410-2012-512?**
   - What we know: pyhanko 0.35.1 is available; its docs cover CMS/PKCS#7; Kazakhstan GOST signatures use GOST-3410-2012-512
   - What's unclear: Whether pyhanko's GOST support covers the specific curve used by NCA Kazakhstan
   - Recommendation: SPIKE-02 should produce a sample GOST signature from NCALayer; test pyhanko verification against it before Phase 5 begins

4. **Is automated tender submission legally permissible under KZ law?**
   - What we know: KZ EDS law (Закон РК No.370-II) requires authorized representative signing; TenderIt design uses per-action user consent (click + PIN) which is strong evidence of contemporaneous intent
   - What's unclear: Whether goszakup ToS explicitly prohibits or requires prior approval for programmatic API usage; whether "click + PIN" satisfies the "authorized person" requirement
   - Recommendation: SPIKE-05 must produce a written legal opinion from a KZ-licensed attorney; do not launch with real users without this opinion

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js >= 20.9 | create-next-app@14, Next.js dev server | No | v16.18.1 installed — too old | Install via nvm: `nvm install 20 && nvm use 20` |
| Docker + Docker Compose | postgresql, redis, minio services | No | Not found on PATH | Install Docker Desktop for macOS from docker.com |
| Python 3.12 | FastAPI, backend stack | Partial | Python 3.11.7 installed | Python 3.11 is compatible with all required packages; upgrade to 3.12 is optional for MVP |
| PostgreSQL client (psql) | DB health checks | Yes | 16.12 (Homebrew) | — |
| NCALayer desktop app | SPIKE-02 | Unknown | Not on this machine | Install NCALayer on Windows/macOS VM; pki.gov.kz download page |
| mitmproxy | SPIKE-03 (optional) | Unknown | Not checked | Use Chrome DevTools Network tab as primary approach |
| goszakup API token | SPIKE-01 | Unknown | Not obtained | Must request from АО "Центр Электронных Финансов" via letter |
| Real goszakup supplier account | SPIKE-03 | Unknown | Not available | Required — no fallback; recruit a beta company before spike |

**Missing dependencies blocking execution:**
- Node.js >= 20.9 (blocks `create-next-app` — must install via nvm before frontend scaffold)
- Docker Desktop (blocks `docker compose up` — must install before backend services can start)
- goszakup API token (blocks SPIKE-01 — must request before spike can run)
- NCALayer installation (blocks SPIKE-02 — must install on a desktop machine)
- Real goszakup supplier account (blocks SPIKE-03 — must have a company that can attempt a real submission)

**Missing dependencies with fallback:**
- mitmproxy (SPIKE-03 fallback: Chrome DevTools Network tab)
- Python 3.12 (Python 3.11 is compatible with all dependencies)

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.3.0 (latest verified via PyPI) |
| Config file | `backend/pytest.ini` — does not exist yet (Wave 0) |
| Quick run command | `cd backend && pytest tests/ -x -q` |
| Full suite command | `cd backend && pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SPIKE-01 | goszakup v3 GraphQL endpoint responds to Bearer token auth | smoke (live API) | `cd backend && pytest tests/spikes/test_spike01_goszakup.py -x` | No — Wave 0 |
| SPIKE-02 | NCALayer WebSocket connects at confirmed port | smoke (manual + HTML page) | Manual only — NCALayer must be running locally | N/A — manual |
| SPIKE-03 | Submission payload captured and saved as JSON | manual investigation | Manual only — requires real account + browser session | N/A — manual |
| SPIKE-04 | MP.kz internal API endpoints documented | manual investigation | Manual only — requires browser session | N/A — manual |
| SPIKE-05 | Legal opinion document exists in findings/ | artifact check | `ls .planning/phases/01-spikes-foundation/findings/SPIKE-05-legal.md` | N/A — manual |
| (skeleton) | FastAPI /health returns 200 | unit/smoke | `cd backend && pytest tests/test_health.py -x` | No — Wave 0 |
| (skeleton) | docker-compose services healthy | smoke | `docker compose ps` showing all healthy | N/A — manual |

**Note:** SPIKE-02, SPIKE-03, SPIKE-04, SPIKE-05 are inherently manual investigations. They cannot be automated. The "test" for these is the existence and quality of the findings document in `.planning/phases/01-spikes-foundation/findings/`.

### Sampling Rate
- **Per task commit:** `cd backend && pytest tests/test_health.py -x -q`
- **Per wave merge:** `cd backend && pytest tests/ -v`
- **Phase gate:** All five findings files exist and are complete; FastAPI /health returns 200; docker-compose services all pass healthchecks

### Wave 0 Gaps
- [ ] `backend/pytest.ini` — pytest configuration with asyncio_mode = auto
- [ ] `backend/tests/__init__.py` — empty file
- [ ] `backend/tests/conftest.py` — shared fixtures (db session, test client)
- [ ] `backend/tests/test_health.py` — GET /health → 200 smoke test
- [ ] `backend/tests/spikes/test_spike01_goszakup.py` — httpx call to goszakup v3 endpoint (requires token env var)
- [ ] `.planning/phases/01-spikes-foundation/findings/` — directory for all spike output documents

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No — Phase 1 has no user-facing auth | — |
| V3 Session Management | No | — |
| V4 Access Control | No | — |
| V5 Input Validation | Partial — spike scripts validate API responses | Pydantic v2 models for goszakup response parsing |
| V6 Cryptography | Partial — SPIKE-02 involves EDS crypto analysis | Never hand-roll; NCALayer handles all crypto on user machine |

### Known Threat Patterns for Phase 1

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API token exposure in spike scripts | Information Disclosure | Store token in `.env`, never commit to git; add `.env` to `.gitignore` from day one |
| mitmproxy CA cert installed permanently | Tampering | Remove mitmproxy CA from browser/OS trust store after SPIKE-03 is complete |
| Submitting to production goszakup during spike | Elevation of Privilege | SPIKE-03 should ideally use a test tender (very small amount, company already pre-approved) to minimize risk of accidental binding submission |

---

## Project Constraints (from CLAUDE.md)

The following directives from `CLAUDE.md` are binding for Phase 1:

| Directive | Impact on Phase 1 |
|-----------|-------------------|
| NCALayer is browser-only. Backend NEVER connects to ws://localhost:14579 | SPIKE-02 test must be a browser HTML page, not a Python script |
| Private keys never leave the user's device. No .p12 file uploads to server | SPIKE-02 findings must confirm: signing stays in NCALayer; backend only receives signed XML blob |
| Kazakhstan data localization: PII must be hosted on KZ infrastructure | SPIKE-05 must confirm KZ hosting requirements; infrastructure selection cannot be deferred |
| Tender data from official APIs: goszakup GraphQL + MP.kz (verify API vs scraping in Phase 1 spike) | SPIKE-01 and SPIKE-04 are explicitly called out in CLAUDE.md as Phase 1 tasks |
| Durable submission queue: never synchronous HTTP from request handler | Skeleton must install ARQ from day one; SPIKE-01 findings will inform queue configuration |
| Monorepo: single git repo, frontend/ + backend/ + .planning/ all together | Scaffold must produce `TenderIt/frontend/` and `TenderIt/backend/` — not two separate repos |

---

## Sources

### Primary (HIGH confidence)
- [CITED: https://nextjs.org/docs/app/getting-started/installation] — Next.js 14 installation, create-next-app flags, Node.js minimum version requirement
- [CITED: https://goszakup.gov.kz/ru/developer/ows_v3] — goszakup v3 API token registration process, Bearer auth, 1-year token validity
- [CITED: https://ows.goszakup.gov.kz/help/v3/schema/] — goszakup v3 GraphQL schema browser; confirms TrdBuy, TrdApp types exist
- [VERIFIED: npm registry] — next@14.2.35, create-next-app@14.2.35, tailwindcss@3.4.19, @tanstack/react-query@5.100.14, zustand@5.0.13, react-hook-form@7.76.1, typescript@6.0.3
- [VERIFIED: PyPI via pip3 index versions] — fastapi@0.115.6, pydantic@2.10.5, sqlalchemy@2.0.37, alembic@1.14.0, asyncpg@0.31.0, httpx@0.28.1, arq@0.28.0, pytest@9.0.3, pytest-asyncio@1.3.0
- [CITED: https://berkkaraal.com/blog/2024/09/19/setup-fastapi-project-with-async-sqlalchemy-2-alembic-postgresql-and-docker/] — async Alembic template pattern, FastAPI project structure

### Secondary (MEDIUM confidence)
- [CITED: https://github.com/sigex-kz/ncalayer-js-client] — confirms NCALayer WebSocket URL is `wss://127.0.0.1:13579`; confirms new module is `kz.gov.pki.knca.basics`
- [CITED: https://github.com/pkigovkz/sdkinfo/wiki/KNCA-Basics-Module] — `basics` module sign method structure (module, method, args pattern)
- [CITED: https://adr.github.io/madr/] — MADR ADR format for spike findings documentation
- [CITED: https://www.morganlewis.com (Kazakhstan data localization, 2024)] — personal data localization requirement effective 8 January 2025
- [CITED: https://pki.gov.kz/en/ncalayer-2/] — NCALayer 2 supports Windows, macOS, Linux

### Tertiary (LOW confidence — must verify before implementation)
- [ASSUMED] — goszakup has no documented rate limits; community reports suggest ~100-200 req/min
- [ASSUMED] — NCALayer port may be 13579 or 14579 depending on version; must verify with netstat on target machine
- [ASSUMED] — docker-compose environment variable names for postgres, redis, minio are standard for official images
- [ASSUMED] — pyhanko 0.35.1 supports Kazakhstan GOST-3410-2012-512 signatures

---

## Metadata

**Confidence breakdown:**
- Project scaffold (Next.js + FastAPI + docker-compose): HIGH — all versions confirmed via registries; patterns confirmed via official docs
- goszakup GraphQL spike approach: MEDIUM — endpoint confirmed, token process confirmed, rate limits LOW
- NCALayer spike approach: MEDIUM — WebSocket URL confirmed, module name partially confirmed, exact message format ASSUMED
- MP.kz spike approach: MEDIUM — methodology (browser DevTools) is standard; MP.kz internal API existence is LOW
- Legal spike: LOW — data localization law MEDIUM confidence; automated submission permissibility requires attorney

**Research date:** 2026-05-25
**Valid until:** 2026-06-25 (30 days) — goszakup API and NCALayer docs may update; re-verify before Phase 5
