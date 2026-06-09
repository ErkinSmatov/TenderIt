# Phase 3: Tender Lookup — Research

**Researched:** 2026-06-10
**Domain:** FastAPI async GraphQL client, SQLAlchemy 2.x JSONB + upsert, Next.js 14 App Router search UX
**Confidence:** HIGH (all claims verified against codebase, Context7, or official docs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

1. **API transport:** GraphQL POST to `https://ows.goszakup.gov.kz/v3/graphql` — Bearer token, one query for TrdBuy+Lots
2. **DB schema:** Two tables — `tenders` (cache, `number_anno` VARCHAR UNIQUE) + `user_watchlist` (user_id FK, tender_id FK) — exact DDL in CONTEXT.md
3. **Cache strategy:** 30-min TTL on `cached_at`, always cache on lookup, never cache 404s
4. **Validation:** Accept any non-empty string ≤100 chars, strip whitespace — no regex until Wave 0 spike confirms format
5. **Wave 0 spike first:** Confirm token works, get `refBuyStatusId` values for "open" status, record real `numberAnno` format — Wave 1 is blocked on this
6. **Backend routes:** `GET /api/tenders/{number_anno}`, `POST /api/watchlist`, `DELETE /api/watchlist/{number_anno}`, `GET /api/watchlist`
7. **Token security:** NEVER in code — only `settings.goszakup_api_token` from `.env` (CLAUDE.md directive)

### Claude's Discretion

- GraphQL service layer internal structure (class vs module-level functions)
- Race condition handling strategy for concurrent watchlist additions
- Frontend search UX details (loading state, error presentation)
- Test fixture design for mocking the goszakup API

### Deferred Ideas (OUT OF SCOPE)

- Keyword search / filters (SRCH-FILTER, SRCH-KEYWORD) — v2
- MP.kz integration — v2
- ARQ polling jobs — Phase 5
- Notification logic — Phase 6
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SRCH-01 | User can find a tender by номер объявления via search field | Frontend: search page pattern; Backend: `GET /api/tenders/{number_anno}` route |
| SRCH-02 | System loads tender data from goszakup Unified Services API | httpx async GraphQL client, tenacity retry, 30-min cache-aside pattern |
| SRCH-03 | User sees tender card: title, lot, customer, amount, deadline, status | Pydantic response schema mapping TrdBuy fields; frontend TenderCard component |
| SRCH-04 | User can add tender to watchlist; persisted and visible on dashboard | `user_watchlist` table, `POST /api/watchlist`, upsert race condition pattern |
</phase_requirements>

---

## Summary

Phase 3 is a vertical-slice CRUD feature with an external API call at its core. The API contract is fully known (confirmed in 03-CONTEXT.md). The three main engineering challenges are: (1) structuring a safe async httpx GraphQL service with retry and timeout, (2) implementing cache-aside upsert correctly against a PostgreSQL JSONB table, and (3) handling the concurrent-insert race condition on `user_watchlist`. All three have established patterns in the existing stack.

The codebase from Phase 2 provides direct reuse points: `httpx` is already a project dependency (`httpx[http2]==0.28.1`), `tenacity` is already installed (v9.1.4), and the SQLAlchemy 2.x async session pattern (`AsyncSession`, `async_sessionmaker`) is already in use. The frontend already has `@tanstack/react-query@5.100.14` in `package.json` (currently unused — Phase 3 is its first use). `respx` (httpx mock library, v0.23.1 — latest) is available but not yet in `pyproject.toml dev` deps and must be added.

The Wave 0 spike is the only true gate: it must confirm the token works against the live API and record the real `numberAnno` format before any cache/validation code is written.

**Primary recommendation:** Implement the goszakup client as a thin module (`backend/app/services/goszakup_service.py`) — `httpx.AsyncClient` with Bearer auth, tenacity `@retry` for 5xx only, 20-second timeout. Cache-aside logic lives in the tender service layer, not in the client. Frontend uses a single `'use client'` search page with `useQuery` from react-query for the tender lookup call.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Tender lookup (goszakup API call) | API / Backend | — | Server-to-server call; token must never reach browser |
| 30-min cache check + upsert | API / Backend (PostgreSQL) | — | Cache lives in DB, managed by backend service layer |
| Watchlist CRUD | API / Backend | Database/Storage | Business logic in service, persistence in DB |
| Search input + result display | Browser / Client | — | Interactive form; no initial SSR data needed |
| Tender card + watchlist list | Browser / Client | — | Derived from API response; client-side state |
| Dashboard watchlist section | Frontend Server (SSR) | Browser / Client | Page shell is server component; watchlist data fetched client-side via react-query |

---

## Standard Stack

### Core (already in project)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx[http2] | 0.28.1 | Async HTTP client for goszakup GraphQL calls | Already in `pyproject.toml`; http2 enabled for better multiplexing |
| tenacity | 9.1.4 | Retry decorator for 5xx API failures | Already installed; used in `spike_goszakup.py` |
| SQLAlchemy[asyncio] | 2.0.37 | Async ORM + PostgreSQL JSONB + upsert | Already in project; 2.x dialect has full `JSONB` support |
| asyncpg | 0.31.0 | PostgreSQL async driver | Already in project |
| Pydantic v2 | 2.10.5 | Request/response schemas | Already in project; `@field_validator` pattern established |
| alembic | 1.14.0 | DB migrations | Already in project; revision pattern confirmed |
| @tanstack/react-query | 5.100.14 | Async data fetching + cache on frontend | Already in `package.json`; not yet used — Phase 3 is its first consumer |
| react-hook-form + zod | 7.76.1 / 3.25.0 | Search form validation | Already in project; `CompanyProfileForm` is the reference implementation |

### New Dependency to Add

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| respx | 0.23.1 | Mock httpx in pytest | Required for `test_goszakup_service.py` unit tests — add to `[project.optional-dependencies] dev` in pyproject.toml |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| respx (httpx mock) | `unittest.mock.patch` on httpx | respx intercepts at transport level — no patching internals; cleaner fixture isolation |
| react-query for search | local useState + useEffect | react-query gives automatic loading/error states, deduplication, and retry — no boilerplate |
| JSONB for lots_data | Separate `lots` table | Phase 3 only needs display; JSONB avoids JOIN complexity. Phase 5 can add the table if per-lot targeting is needed |

**Installation (dev deps only):**
```bash
cd backend && pip install respx==0.23.1
# Add to pyproject.toml [project.optional-dependencies] dev:
#   "respx==0.23.1",
```

**Version verification:** All versions verified against pip registry and node_modules on 2026-06-10. [VERIFIED: pip3 index versions, node_modules inspection]

---

## Architecture Patterns

### System Architecture Diagram

```
Browser                   FastAPI Backend              PostgreSQL         goszakup API
  │                            │                           │              (external)
  │  GET /api/tenders/{num}    │                           │
  │ ─────────────────────────► │                           │
  │                            │  SELECT tenders WHERE     │
  │                            │  number_anno = {num}  ──► │
  │                            │  ◄── row / None           │
  │                            │                           │
  │                            │  [cache hit, age < 30m]   │
  │                            │ ◄─────────────────────────│
  │  200 TenderResponse        │                           │
  │ ◄───────────────────────── │                           │
  │                            │  [cache miss / stale]     │
  │                            │  POST /v3/graphql ─────────────────────►
  │                            │                           │  TrdBuy query
  │                            │  ◄─── {"data":{          │  with Bearer
  │                            │        "TrdBuy": [...]}}  │  token
  │                            │                           │
  │                            │  [TrdBuy = []] → 404      │
  │  404 not found             │                           │
  │ ◄───────────────────────── │                           │
  │                            │  [TrdBuy has data]        │
  │                            │  INSERT ... ON CONFLICT   │
  │                            │  DO UPDATE ─────────────► │
  │  200 TenderResponse        │                           │
  │ ◄───────────────────────── │                           │
  │                            │                           │
  │  POST /api/watchlist       │                           │
  │ ─────────────────────────► │                           │
  │                            │  [ensure tender cached]   │
  │                            │  SELECT / INSERT tender   │
  │                            │  INSERT user_watchlist ─► │
  │                            │  ON CONFLICT DO NOTHING   │
  │  201 WatchlistResponse     │                           │
  │ ◄───────────────────────── │                           │
```

### Recommended Project Structure

```
backend/app/
├── models/
│   ├── tender.py              # Tender + UserWatchlist SQLAlchemy models
│   └── __init__.py            # ADD: Tender, UserWatchlist imports
├── schemas/
│   └── tender.py              # TenderResponse, WatchlistResponse, WatchlistAddRequest
├── services/
│   ├── goszakup_service.py    # httpx GraphQL client (token, retry, timeout)
│   └── tender_service.py      # cache-aside logic, watchlist CRUD
├── routers/
│   └── tenders.py             # GET /api/tenders/{number_anno}, POST/DELETE/GET /api/watchlist
└── main.py                    # ADD: include_router(tenders.router, ...)

backend/tests/
├── test_tenders.py            # Route integration tests (SRCH-01, SRCH-03, SRCH-04)
├── test_tender_service.py     # Cache logic unit tests (SRCH-02)
└── spikes/
    └── test_spike01_goszakup.py  # UPDATE: add TrdBuy query test (Wave 0)

frontend/src/
├── app/(dashboard)/
│   ├── tenders/
│   │   └── page.tsx           # 'use client' — search page
│   └── dashboard/
│       └── page.tsx           # UPDATE: add watchlist section
└── components/tenders/
    ├── TenderSearch.tsx        # Search input + submit
    ├── TenderCard.tsx          # Display tender details
    └── WatchlistButton.tsx     # Add/remove from watchlist
```

### Pattern 1: Async GraphQL Client Service

**What:** `httpx.AsyncClient` with Bearer auth, tenacity retry on 5xx only (NOT on 4xx — 401/403 require human action), 20-second timeout. Client is created per-request (no global client) to avoid event loop issues in tests.

**When to use:** Every call to `goszakup_service.fetch_tender_by_number_anno()`

```python
# Source: existing spike_goszakup.py pattern + Context7 SQLAlchemy docs
# backend/app/services/goszakup_service.py

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.config import settings

GRAPHQL_URL = "https://ows.goszakup.gov.kz/v3/graphql"

TENDER_QUERY = """
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
    RefBuyStatus { id nameRu nameKz code }
    startDate
    endDate
    publishDate
    lastUpdateDate
    Lots {
      id lotNumber nameRu nameKz descriptionRu amount refLotStatusId
    }
  }
}
"""


def _is_retryable(exc: BaseException) -> bool:
    """Retry on 5xx only. Never retry 4xx — those require token refresh or human action."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        return True
    return False


@retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def fetch_tender_by_number_anno(number_anno: str) -> dict | None:
    """Call goszakup GraphQL and return the TrdBuy object, or None if not found.

    Token is read from settings — never hardcoded (CLAUDE.md directive).
    Returns None when TrdBuy array is empty (tender does not exist on portal).
    Raises httpx.HTTPStatusError on unrecoverable 4xx/5xx.
    """
    headers = {
        "Authorization": f"Bearer {settings.goszakup_api_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "query": TENDER_QUERY,
        "variables": {"numberAnno": number_anno},
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(GRAPHQL_URL, json=payload, headers=headers)
        response.raise_for_status()

    body = response.json()
    items = body.get("data", {}).get("TrdBuy") or []
    return items[0] if items else None
```

[VERIFIED: existing spike_goszakup.py pattern] [CITED: https://docs.python-tenacity.readthedocs.io — retry_if_exception]

### Pattern 2: Cache-Aside Upsert (30-min TTL)

**What:** Check DB first, return if fresh. Fetch from API if stale/missing. Use PostgreSQL `INSERT ... ON CONFLICT DO UPDATE` for atomic write — avoids SELECT+INSERT race condition when two requests arrive simultaneously for the same `number_anno`.

**When to use:** Inside `tender_service.get_or_fetch_tender()`

```python
# Source: Context7 SQLAlchemy docs /websites/sqlalchemy_en_20
# backend/app/services/tender_service.py

from datetime import datetime, timedelta, timezone
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.tender import Tender
from app.services import goszakup_service

CACHE_TTL_MINUTES = 30


async def get_or_fetch_tender(
    db: AsyncSession, number_anno: str
) -> Tender | None:
    """Cache-aside: return cached tender if fresh, else fetch from API and upsert."""
    # 1. Check cache
    result = await db.execute(
        select(Tender).where(Tender.number_anno == number_anno)
    )
    cached = result.scalar_one_or_none()

    cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=CACHE_TTL_MINUTES)
    if cached and cached.cached_at >= cutoff:
        return cached  # Cache hit — fresh

    # 2. Fetch from API
    raw = await goszakup_service.fetch_tender_by_number_anno(number_anno)
    if raw is None:
        return None  # Not found on portal — do NOT cache

    # 3. Upsert — atomic, handles concurrent requests for same number_anno
    lots = raw.get("Lots") or []
    status_obj = raw.get("RefBuyStatus") or {}

    stmt = pg_insert(Tender).values(
        number_anno=raw["numberAnno"],
        name_ru=raw.get("nameRu"),
        name_kz=raw.get("nameKz"),
        total_sum=raw.get("totalSum"),
        customer_name_ru=raw.get("customerNameRu"),
        customer_name_kz=raw.get("customerNameKz"),
        status_id=raw.get("refBuyStatusId"),
        status_name_ru=status_obj.get("nameRu"),
        start_date=raw.get("startDate"),
        end_date=raw.get("endDate"),
        publish_date=raw.get("publishDate"),
        lots_data=lots,
        raw_data=raw,
        cached_at=datetime.now(tz=timezone.utc),
    ).on_conflict_do_update(
        index_elements=["number_anno"],
        set_=dict(
            name_ru=raw.get("nameRu"),
            status_id=raw.get("refBuyStatusId"),
            status_name_ru=status_obj.get("nameRu"),
            end_date=raw.get("endDate"),
            lots_data=lots,
            raw_data=raw,
            cached_at=datetime.now(tz=timezone.utc),
        ),
    ).returning(Tender)

    result = await db.execute(stmt)
    await db.commit()
    return result.scalar_one()
```

[VERIFIED: Context7 /websites/sqlalchemy_en_20 — "Implementing INSERT...ON CONFLICT in SQLAlchemy"]

### Pattern 3: JSONB Column Declaration in SQLAlchemy 2.x

**What:** Use `sqlalchemy.dialects.postgresql.JSONB` as the column type in the ORM model. Assign Python `list` or `dict` directly — SQLAlchemy handles serialization.

```python
# Source: Context7 /websites/sqlalchemy_en_20 — "Define and Insert Data into JSONB Column"
# backend/app/models/tender.py

from sqlalchemy import Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime

from app.db import Base


class Tender(Base):
    __tablename__ = "tenders"

    id: Mapped[int] = mapped_column(primary_key=True)
    number_anno: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name_ru: Mapped[str | None] = mapped_column(Text)
    name_kz: Mapped[str | None] = mapped_column(Text)
    total_sum: Mapped[float | None] = mapped_column(Numeric(18, 2))
    customer_name_ru: Mapped[str | None] = mapped_column(String(500))
    customer_name_kz: Mapped[str | None] = mapped_column(String(500))
    status_id: Mapped[int | None] = mapped_column(Integer)
    status_name_ru: Mapped[str | None] = mapped_column(String(200))
    start_date: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    publish_date: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    lots_data: Mapped[list | None] = mapped_column(JSONB)
    raw_data: Mapped[dict | None] = mapped_column(JSONB)
    cached_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

[VERIFIED: Context7 /websites/sqlalchemy_en_20]

### Pattern 4: Alembic Migration with JSONB + TIMESTAMPTZ

**What:** Use `sa.dialects.postgresql.JSONB` in the migration file and `sa.TIMESTAMP(timezone=True)` for timezone-aware columns. The existing `0001_...` migration uses `sa.DateTime()` (timezone-naive) — Phase 3 migration uses `TIMESTAMP(timezone=True)` consistently.

```python
# Source: existing 0001_create_users_company_profiles.py pattern
# backend/alembic/versions/0002_create_tenders_watchlist.py

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade() -> None:
    op.create_table(
        "tenders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("number_anno", sa.String(100), unique=True, nullable=False),
        sa.Column("name_ru", sa.Text(), nullable=True),
        sa.Column("total_sum", sa.Numeric(18, 2), nullable=True),
        sa.Column("customer_name_ru", sa.String(500), nullable=True),
        sa.Column("customer_name_kz", sa.String(500), nullable=True),
        sa.Column("status_id", sa.Integer(), nullable=True),
        sa.Column("status_name_ru", sa.String(200), nullable=True),
        sa.Column("start_date", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("end_date", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("publish_date", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("lots_data", postgresql.JSONB(), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(), nullable=True),
        sa.Column("cached_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_tenders_number_anno", "tenders", ["number_anno"], unique=True)

    op.create_table(
        "user_watchlist",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tender_id", sa.Integer(), sa.ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("added_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("notification_on", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("user_id", "tender_id", name="uq_user_watchlist"),
    )
```

[VERIFIED: existing alembic/versions/0001 pattern] [VERIFIED: Context7 /websites/sqlalchemy_en_20]

### Pattern 5: Watchlist POST — Race Condition Handling

**What:** Two concurrent users adding the same tender to watchlist must not cause a duplicate insert. Use `INSERT ... ON CONFLICT DO NOTHING` on the `(user_id, tender_id)` unique constraint. The prior `get_or_fetch_tender` call ensures the `tenders` row exists before the watchlist insert.

```python
# backend/app/services/tender_service.py (continued)

from app.models.tender import UserWatchlist

async def add_to_watchlist(
    db: AsyncSession, user_id: int, number_anno: str
) -> UserWatchlist | None:
    """Add tender to watchlist. Creates tender cache entry if missing.

    Returns the watchlist entry (new or existing) or None if tender not found.
    """
    tender = await get_or_fetch_tender(db, number_anno)
    if tender is None:
        return None  # Caller raises 404

    stmt = (
        pg_insert(UserWatchlist)
        .values(user_id=user_id, tender_id=tender.id)
        .on_conflict_do_nothing(constraint="uq_user_watchlist")
        .returning(UserWatchlist)
    )
    result = await db.execute(stmt)
    await db.commit()
    row = result.scalar_one_or_none()
    if row is None:
        # Already exists — fetch it
        existing = await db.execute(
            select(UserWatchlist).where(
                UserWatchlist.user_id == user_id,
                UserWatchlist.tender_id == tender.id,
            )
        )
        row = existing.scalar_one()
    return row
```

[VERIFIED: Context7 /websites/sqlalchemy_en_20 — "INSERT...ON CONFLICT (Upsert)"]

### Pattern 6: Pydantic v2 Schema for GraphQL Response

**What:** The goszakup response has shape `{"data": {"TrdBuy": [...]}}`. The service layer extracts `TrdBuy[0]` before handing off to Pydantic — the schema only validates the inner TrdBuy object. Dates arrive as strings from goszakup; use `@field_validator` to parse.

```python
# backend/app/schemas/tender.py

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class LotItem(BaseModel):
    model_config = {"from_attributes": True}
    lot_number: Optional[int] = None
    name_ru: Optional[str] = None
    name_kz: Optional[str] = None
    description_ru: Optional[str] = None
    amount: Optional[float] = None


class TenderResponse(BaseModel):
    model_config = {"from_attributes": True}

    number_anno: str
    name_ru: Optional[str] = None
    name_kz: Optional[str] = None
    total_sum: Optional[float] = None
    customer_name_ru: Optional[str] = None
    customer_name_kz: Optional[str] = None
    status_id: Optional[int] = None
    status_name_ru: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    publish_date: Optional[datetime] = None
    lots_data: Optional[list] = None
    cached_at: datetime


class WatchlistAddRequest(BaseModel):
    number_anno: str = Field(min_length=1, max_length=100)

    @field_validator("number_anno")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class WatchlistEntryResponse(BaseModel):
    model_config = {"from_attributes": True}
    tender: TenderResponse
    notification_on: bool
    added_at: datetime
```

[VERIFIED: existing backend/app/schemas/company.py pattern]

### Pattern 7: Frontend Search Page (Next.js 14 App Router)

**What:** The search page is a `'use client'` component — no SSR initial data is needed (user types the ID). Uses `useQuery` with `enabled: false` + manual `refetch()` on form submit. This avoids a fetch on page load while still benefiting from react-query's loading/error state management.

```tsx
// Source: Context7 /vercel/next.js — Server Component + Client Component pattern
// frontend/src/app/(dashboard)/tenders/page.tsx
'use client'

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import TenderCard from '@/components/tenders/TenderCard'

const searchSchema = z.object({
  number_anno: z.string().min(1, 'Введите номер объявления').max(100),
})
type SearchValues = z.infer<typeof searchSchema>

export default function TendersPage() {
  const [queryNumber, setQueryNumber] = useState<string | null>(null)

  const { register, handleSubmit, formState: { errors } } = useForm<SearchValues>({
    resolver: zodResolver(searchSchema),
  })

  const { data: tender, isLoading, error, isError } = useQuery({
    queryKey: ['tender', queryNumber],
    queryFn: () => api.get<TenderResponse>(`/api/tenders/${queryNumber}`),
    enabled: queryNumber !== null,
    retry: false,  // Don't retry 404s
  })

  const onSubmit = (values: SearchValues) => {
    setQueryNumber(values.number_anno.trim())
  }

  return (
    <div>
      <h1>Поиск тендера</h1>
      <form onSubmit={handleSubmit(onSubmit)}>
        <input {...register('number_anno')} placeholder="Номер объявления" />
        {errors.number_anno && <p>{errors.number_anno.message}</p>}
        <button type="submit" disabled={isLoading}>
          {isLoading ? 'Поиск...' : 'Найти'}
        </button>
      </form>
      {isError && <p>Тендер с номером {queryNumber} не найден на портале</p>}
      {tender && <TenderCard tender={tender} />}
    </div>
  )
}
```

[VERIFIED: Context7 /vercel/next.js — "Server Component Page Fetching Data"]

**Note:** `api.ts` currently has no `delete` method — add it for `DELETE /api/watchlist/{number_anno}`:
```typescript
delete: <T>(path: string) => apiFetch<T>(path, { method: 'DELETE' }),
```

### Pattern 8: respx Mock in pytest (httpx)

**What:** Use `respx` fixture or `@respx.mock` decorator to intercept httpx calls to goszakup in unit tests. The service creates `httpx.AsyncClient` per-call — respx intercepts at the transport level, no patching needed.

```python
# Source: Context7 /lundberg/respx
# backend/tests/test_tender_service.py

import pytest
import respx
import httpx

GRAPHQL_URL = "https://ows.goszakup.gov.kz/v3/graphql"

@pytest.mark.asyncio
@respx.mock
async def test_fetch_tender_found():
    respx.post(GRAPHQL_URL).mock(return_value=httpx.Response(
        200,
        json={"data": {"TrdBuy": [{"numberAnno": "123456", "nameRu": "Test"}]}},
    ))
    result = await goszakup_service.fetch_tender_by_number_anno("123456")
    assert result["numberAnno"] == "123456"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_tender_not_found():
    respx.post(GRAPHQL_URL).mock(return_value=httpx.Response(
        200,
        json={"data": {"TrdBuy": []}},
    ))
    result = await goszakup_service.fetch_tender_by_number_anno("NOPE")
    assert result is None
```

[VERIFIED: Context7 /lundberg/respx — "Pytest: Async Test Cases with Decorator"]

### Anti-Patterns to Avoid

- **Global httpx.AsyncClient as module-level singleton:** Causes event loop binding issues in tests; create per-request instead.
- **Hardcoding goszakup token:** CLAUDE.md directive — always `settings.goszakup_api_token`. Token must be added to `Settings` class in `config.py`.
- **Caching 404 (tender not found):** CONTEXT.md decision — never insert a row for a non-existent tender.
- **Retrying 401/403 from goszakup:** These indicate token issues — retry will just hammer the API. Only retry 5xx and network errors.
- **SELECT then INSERT for watchlist:** Race condition. Use `INSERT ... ON CONFLICT DO NOTHING` instead.
- **Timezone-naive datetime comparisons:** All `cached_at` comparisons must use `datetime.now(tz=timezone.utc)` — the column is TIMESTAMPTZ.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| httpx retry on transient failures | Custom retry loop | `tenacity @retry` | Already in codebase; handles exponential backoff, reraise, predicate-based retry |
| PostgreSQL upsert | SELECT + INSERT in Python | `pg_insert().on_conflict_do_update()` | Atomic — no race condition even under concurrent load |
| httpx mocking in tests | `unittest.mock.patch` on httpx internals | `respx` | Transport-level interception — works with `AsyncClient`, sync client, and `httpx.MockTransport` |
| Frontend loading/error state | useState + useEffect | `@tanstack/react-query` `useQuery` | Already in package.json; handles deduplication, retry config, stale-while-revalidate |
| Frontend form validation | Manual input validation | `react-hook-form` + `zod` | Already established in `CompanyProfileForm.tsx` |

---

## Common Pitfalls

### Pitfall 1: `settings.goszakup_api_token` Not Yet in Settings

**What goes wrong:** `AttributeError: Settings has no field 'goszakup_api_token'` at startup.
**Why it happens:** `config.py` was written in Phase 2 and doesn't include the goszakup token field yet.
**How to avoid:** Wave 1 task must add `goszakup_api_token: str = ""` to `Settings` in `backend/app/config.py`. The `""` default lets tests run without a real token (goszakup service will fail, but service tests use respx mocks).
**Warning signs:** Import error or AttributeError in any test that imports `goszakup_service`.

### Pitfall 2: TIMESTAMPTZ Comparison with Timezone-Naive datetime

**What goes wrong:** `can't compare offset-naive and offset-aware datetimes` at cache freshness check.
**Why it happens:** Python's `datetime.now()` (no tz) vs. PostgreSQL TIMESTAMPTZ returned as aware datetime by asyncpg.
**How to avoid:** Always use `datetime.now(tz=timezone.utc)` in cache TTL comparisons. [VERIFIED: Python datetime docs]
**Warning signs:** TypeError in `get_or_fetch_tender()` on the `cached_at >= cutoff` comparison.

### Pitfall 3: GraphQL "Not Found" Is HTTP 200 With Empty Array

**What goes wrong:** Backend returns 200 to frontend for an unknown tender ID.
**Why it happens:** goszakup returns `{"data": {"TrdBuy": []}}` — valid HTTP 200 — when `numberAnno` doesn't match.
**How to avoid:** In `fetch_tender_by_number_anno`, return `None` when `len(items) == 0`. Router raises `HTTPException(status_code=404)` on `None`. [VERIFIED: CONTEXT.md confirmed]
**Warning signs:** Frontend shows blank tender card instead of "not found" message.

### Pitfall 4: `models/__init__.py` Missing New Model Imports

**What goes wrong:** Alembic `--autogenerate` doesn't detect the new `tenders`/`user_watchlist` tables.
**Why it happens:** `alembic/env.py` does `import app.models` — if `__init__.py` doesn't import `Tender` and `UserWatchlist`, they're invisible to autogenerate.
**How to avoid:** Add `from app.models.tender import Tender, UserWatchlist` to `backend/app/models/__init__.py` in the same commit as the model file. [VERIFIED: existing `__init__.py` pattern]
**Warning signs:** `alembic revision --autogenerate` produces an empty migration.

### Pitfall 5: `pg_insert` vs `sqlalchemy.insert`

**What goes wrong:** `ON CONFLICT` clause not available; `AttributeError: 'Insert' object has no attribute 'on_conflict_do_update'`.
**Why it happens:** Using `from sqlalchemy import insert` instead of `from sqlalchemy.dialects.postgresql import insert as pg_insert`.
**How to avoid:** Always import the PostgreSQL-specific insert for upsert operations.
**Warning signs:** AttributeError on `.on_conflict_do_update()` call.

### Pitfall 6: `@tanstack/react-query` QueryClient Not Provided

**What goes wrong:** `useQuery` throws "No QueryClient set, use QueryClientProvider to set one".
**Why it happens:** `@tanstack/react-query` is in `package.json` but no `QueryClientProvider` wraps the app.
**How to avoid:** Wave 3 task must add a `QueryClientProvider` wrapper. Options: add to `frontend/src/app/layout.tsx` (global) or to `(dashboard)/layout.tsx` (scoped). Dashboard scope is preferred — avoids providing react-query to unauthenticated pages.
**Warning signs:** Runtime error on first `useQuery` call on the tenders page.

### Pitfall 7: `DELETE` Method Missing from `api.ts`

**What goes wrong:** `api.delete` is `undefined` — TypeScript error or runtime error when removing from watchlist.
**Why it happens:** `api.ts` only defines `get`, `post`, `put`. Phase 3 is the first consumer of DELETE.
**How to avoid:** Add `delete: <T>(path: string) => apiFetch<T>(path, { method: 'DELETE' })` to `api.ts` in Wave 3.
**Warning signs:** TypeScript: `Property 'delete' does not exist on type ...`

---

## Code Examples

### goszakup Bearer auth headers (established pattern)

```python
# Source: backend/spikes/spike_goszakup.py (existing project code)
headers = {
    "Authorization": f"Bearer {settings.goszakup_api_token}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}
```

### PostgreSQL INSERT...ON CONFLICT (SQLAlchemy 2.x)

```python
# Source: Context7 /websites/sqlalchemy_en_20 — "Implementing INSERT...ON CONFLICT"
from sqlalchemy.dialects.postgresql import insert as pg_insert

stmt = pg_insert(MyModel).values(**data).on_conflict_do_update(
    index_elements=["unique_column"],
    set_={"field": new_value},
).returning(MyModel)
result = await db.execute(stmt)
obj = result.scalar_one()
```

### JSONB column type in ORM model

```python
# Source: Context7 /websites/sqlalchemy_en_20 — "Define and Insert Data into JSONB Column"
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

lots_data: Mapped[list | None] = mapped_column(JSONB)
raw_data: Mapped[dict | None] = mapped_column(JSONB)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Session.bulk_insert_mappings()` | `session.execute(insert(Model), [...])` | SQLAlchemy 2.0 | New API supports RETURNING; old is deprecated |
| `asyncio_mode = "strict"` in pytest-asyncio | `asyncio_mode = auto` | pytest-asyncio 0.21+ | Already configured in `pytest.ini`; all async tests work without `@pytest.mark.asyncio` individually |
| `Query` API (`session.query(Model)`) | `select(Model)` + `session.execute()` | SQLAlchemy 2.0 | Old Query API removed in 2.0; already using new style in project |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `refBuyStatusId` integer for "open for applications" status is unknown — requires Wave 0 spike | User Constraints (Wave 0) | Phase 5 polling logic will use wrong status code; app cannot detect when tender opens |
| A2 | `numberAnno` format is a plain string (not prefixed like "RU-2025-XXXX") | Standard Stack, validation | Regex validator in Phase 5 may need updating; display formatting in UI may look odd |
| A3 | goszakup API has no documented rate limits — conservative 1 req/2s assumed | Pitfalls | If actual limit is lower, production polling in Phase 5 will hit 429s |
| A4 | goszakup dates (`startDate`, `endDate`) come as ISO-8601 strings parseable by Python's `datetime.fromisoformat()` | Patterns | Dates stored as NULL if format is unexpected; Wave 0 spike must record actual date format |

---

## Open Questions

1. **`refBuyStatusId` value for "open for applications"**
   - What we know: `status_id` column exists; the value is needed by Phase 5 ARQ polling
   - What's unclear: The integer code — Wave 0 must query the справочник endpoint or introspect `RefBuyStatus` enum
   - Recommendation: Wave 0 spike records all `refBuyStatusId` values and their meanings; store in `SPIKE-01-GRAPHQL-FINDINGS.md`

2. **`numberAnno` exact format**
   - What we know: It's a String in the GraphQL schema
   - What's unclear: Whether it's purely numeric (`"123456"`) or has a prefix/separator
   - Recommendation: Wave 0 spike records the actual value from a real TrdBuy query response; add to `SPIKE-01-GRAPHQL-FINDINGS.md`

3. **goszakup API rate limits**
   - What we know: SPIKE-01 probe planned 15 req/1-per-second; probe results pending
   - What's unclear: Actual 429 threshold; Retry-After header format
   - Recommendation: Phase 3 uses conservative 20-second timeout + at most 3 retries on 5xx; rate limit enforcement is deferred to Phase 5 ARQ design

4. **Date string format from goszakup**
   - What we know: Fields `startDate`, `endDate`, `publishDate` are String in the schema
   - What's unclear: Actual format — ISO-8601? Unix timestamp? Kazakhstan timezone?
   - Recommendation: Wave 0 spike records the raw date string from the TrdBuy response; service layer handles parsing with a fallback to `None` on parse failure

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | DB (tenders, user_watchlist) | ✓ | 16.12 | — |
| httpx[http2] | goszakup API client | ✓ | 0.28.1 | — |
| tenacity | Retry decorator | ✓ | 9.1.4 | — |
| respx | httpx mocking in tests | ✓ (pip) | 0.23.1 | — (must add to pyproject.toml dev deps) |
| @tanstack/react-query | Frontend data fetching | ✓ | 5.100.14 | — |
| goszakup API token | Live API calls | [ASSUMED] | — | Spike tests skip via `pytest.mark.skipif` |

[VERIFIED: pip3 index, node_modules inspection, psql --version — 2026-06-10]

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** `goszakup_api_token` — all tests using the live API are gated by `pytest.mark.skipif(not HAS_TOKEN, ...)` (pattern from `test_spike01_goszakup.py`).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| Config file | `backend/pytest.ini` (asyncio_mode = auto) |
| Quick run command | `cd backend && pytest tests/test_tenders.py tests/test_tender_service.py -x -q` |
| Full suite command | `cd backend && pytest -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SRCH-01 | `GET /api/tenders/{number_anno}` returns tender | integration | `pytest tests/test_tenders.py::test_get_tender_found -x` | ❌ Wave 0 |
| SRCH-01 | Unknown ID returns 404 | integration | `pytest tests/test_tenders.py::test_get_tender_not_found -x` | ❌ Wave 0 |
| SRCH-02 | goszakup service returns TrdBuy object | unit (respx) | `pytest tests/test_tender_service.py::test_fetch_tender_found -x` | ❌ Wave 0 |
| SRCH-02 | 30-min cache hit skips API call | unit | `pytest tests/test_tender_service.py::test_cache_hit_skips_api -x` | ❌ Wave 0 |
| SRCH-02 | Stale cache triggers re-fetch | unit | `pytest tests/test_tender_service.py::test_cache_stale_refetches -x` | ❌ Wave 0 |
| SRCH-03 | TenderResponse schema includes all required fields | unit | `pytest tests/test_tender_service.py::test_tender_response_schema -x` | ❌ Wave 0 |
| SRCH-04 | `POST /api/watchlist` adds entry | integration | `pytest tests/test_tenders.py::test_add_to_watchlist -x` | ❌ Wave 0 |
| SRCH-04 | Duplicate watchlist POST is idempotent | integration | `pytest tests/test_tenders.py::test_add_watchlist_idempotent -x` | ❌ Wave 0 |
| SRCH-04 | `DELETE /api/watchlist/{number_anno}` removes entry | integration | `pytest tests/test_tenders.py::test_remove_from_watchlist -x` | ❌ Wave 0 |
| SRCH-04 | `GET /api/watchlist` lists watched tenders | integration | `pytest tests/test_tenders.py::test_get_watchlist -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `cd backend && pytest tests/test_tenders.py tests/test_tender_service.py -x -q`
- **Per wave merge:** `cd backend && pytest -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/test_tenders.py` — covers SRCH-01, SRCH-04 (route integration tests)
- [ ] `backend/tests/test_tender_service.py` — covers SRCH-02 cache logic (unit tests with respx)
- [ ] `respx==0.23.1` added to `pyproject.toml` `[project.optional-dependencies] dev`
- [ ] `QueryClientProvider` wrapper in `frontend/src/app/(dashboard)/layout.tsx`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | `get_current_user` dependency (JWT httpOnly cookie) — already implemented Phase 2 |
| V3 Session Management | no | Sessions managed in Phase 2; no new session logic |
| V4 Access Control | yes | Watchlist routes: `user_id` derived from JWT — never from request body |
| V5 Input Validation | yes | Pydantic `WatchlistAddRequest` — `min_length=1, max_length=100, strip whitespace` |
| V6 Cryptography | no | No new crypto; Bearer token is read-only config value |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| IDOR: user accesses another user's watchlist | Elevation of Privilege | `DELETE /api/watchlist/{number_anno}` filters by both `user_id` (from JWT) AND `number_anno` — never by watchlist ID alone |
| Token leakage in logs | Information Disclosure | `settings.goszakup_api_token` — never log the Bearer value; existing spike pattern never prints it |
| JSONB injection (stored XSS via raw_data) | Tampering | `raw_data` and `lots_data` are displayed read-only; frontend renders via React (auto-escapes); no `dangerouslySetInnerHTML` |
| Excessive API calls (DoS on goszakup) | Denial of Service | 30-min cache means max 2 live API calls/hour per unique tender; no unauthenticated lookup endpoint |

---

## Sources

### Primary (HIGH confidence)
- Existing codebase: `backend/spikes/spike_goszakup.py`, `backend/app/models/`, `backend/tests/conftest.py`, `frontend/src/lib/api.ts`, `frontend/src/components/profile/CompanyProfileForm.tsx` — patterns verified by direct file read
- Context7 `/websites/sqlalchemy_en_20` — JSONB, upsert, async session patterns
- Context7 `/lundberg/respx` — httpx mocking patterns
- Context7 `/vercel/next.js` — App Router server/client component patterns
- `.planning/phases/03-tender-lookup/03-CONTEXT.md` — locked decisions, API contract, DB schema

### Secondary (MEDIUM confidence)
- `backend/spikes/findings/SPIKE-01-FINDINGS.md` — goszakup endpoint confirmation (partial; token pending)
- `backend/pyproject.toml` — confirmed library versions in use
- `frontend/package.json` — confirmed frontend library versions

### Tertiary (LOW confidence)
- goszakup rate limit behavior — inferred from SPIKE-01 conservative default (1 req/2s); not yet measured against live API with a token

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified from pyproject.toml and node_modules on 2026-06-10
- Architecture: HIGH — direct reuse of established Phase 2 patterns; JSONB/upsert verified via Context7
- Pitfalls: HIGH — derived from actual codebase inspection (missing `delete` in api.ts, missing token in Settings, models/__init__ pattern)
- goszakup behavior: MEDIUM — endpoint confirmed reachable; schema contract from official docs; rate limits and date formats are ASSUMED pending Wave 0

**Research date:** 2026-06-10
**Valid until:** 2026-07-10 (stable stack; goszakup API contract could shift if portal updates)
