# Phase 7: Discovery & Matching — Research

**Researched:** 2026-07-19
**Domain:** ARQ batch polling / goszakup GraphQL / rule-based matching / Telegram bot extension / Next.js feed page
**Confidence:** HIGH (codebase is fully readable; goszakup filter field name is the only MEDIUM item)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01 — No zakup.sk.kz.** Only goszakup.gov.kz. No `source='sk_kz'` columns, workers, or routing.
- **D-02 — No profitability calculation.** `profitability_service.py` is NOT part of this phase. `tender_match` records have NO `profitability` column.
- **D-03 — Telegram depends on Phase 6.** Build the notification service in full, guard every send call with `if user.telegram_chat_id is None: skip`. Leave match in `matched` status (no `notified` transition) if no chat_id.
- **D-04 — Telegram callback prefix.** Phase 7 uses `disc:` prefix. Format: `disc:participate:{match_id}` and `disc:skip:{match_id}`. Phase 5 uses `confirm:` — no collision.
- **D-05 — "Участвуем" calls application_service.** The handler MUST call an application creation function — no separate state machine, no bridge table.
- **D-06 — Poll cadence 15 min.** ARQ cron `minute={0, 15, 30, 45}`, `unique=True`.
- **D-07 — Matching is a separate ARQ task.** `poll_goszakup_discovery` upserts, then enqueues `run_matching`. Matching logic lives in `services/matching_service.py`.
- **D-08 — Sidebar Telegram bot link.** Static link using `NEXT_PUBLIC_TELEGRAM_BOT_USERNAME` env var. Opens in new tab. No auth required.
- **D-09 — One bot.** Extend existing `/api/telegram/webhook` router with `disc:*` handlers. Do NOT create a new router file or second bot.
- **D-10 — One filter set per user, upsert semantics.** PUT replaces entire filter record.
- **D-11 — tender_matches status machine.** `matched` → `notified` → (`skipped` | `participating`). `UNIQUE(user_id, tender_id)`.
- **D-12 — Discovery feed at /discovery.** Shows `tender_match` records for the logged-in user, newest first.

### Claude's Discretion

- Exact GraphQL/REST query for batch goszakup fetch (fields, pagination strategy)
- Index strategy for keyword matching (ILIKE vs pg_trgm vs full-text)
- UI component library choices for DiscoveryFeed (follow existing patterns)
- ARQ retry/backoff config for poll worker (follow `auto_submit.py` pattern)

### Deferred Ideas (OUT OF SCOPE)

- zakup.sk.kz (v2 — legal review required)
- Profitability calculation (formula undefined)
- WhatsApp notifications for discovery (Phase 6 Twilio)
- Named filter presets / multiple filter sets (v2)
- Keyword subscription email digest (v2)
- MP.kz as second source (SPIKE-04 pending, v2)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DISC-01 | Пользователь может создать и редактировать набор фильтров (ключевые слова, СПГЗ-коды, регион, диапазон суммы) | `client_filters` table (migration 0006), CRUD router, single upsert endpoint; ILIKE matching strategy confirmed |
| DISC-02 | ARQ-воркер каждые 15 минут получает новые/изменённые тендеры из goszakup batch API и апсертит в БД | GraphQL `TrdBuy(filter:{lastUpdateDate:...})` + `cron(minute={0,15,30,45}, unique=True)` pattern documented |
| DISC-03 | Воркер матчинга сравнивает новые тендеры с фильтрами и создаёт `tender_match` записи | `run_matching` ARQ task enqueued by poll worker; `matching_service.py`; `tender_matches` table (migration 0007) |
| DISC-04 | Пользователь видит «Подборку» — ленту совпавших тендеров | `/discovery` page + `TenderMatchCard` component; `useQuery` pattern from `applications/page.tsx` |
| DISC-05 | Telegram-уведомление с кнопками «Участвуем» / «Пропустить»; «Участвуем» создаёт заявку | `send_discovery_notification()` in `telegram_service.py`; `disc:*` handlers extend existing webhook; **critical pitfall**: `ApplicationCreate` validator blocks empty lots — needs `create_discovery_draft()` |
| DISC-06 | В боковом меню — ссылка на Telegram-бот | `NEXT_PUBLIC_TELEGRAM_BOT_USERNAME` env var; extend `Sidebar.tsx` navItems + static external link |
</phase_requirements>

---

## Summary

Phase 7 extends three existing systems in place: (1) the goszakup GraphQL client gains a batch fetch function with `lastUpdateDate` filtering and pagination; (2) the ARQ worker settings gains two new entries — a cron for `poll_goszakup_discovery` and an on-demand `run_matching` function; (3) the Telegram webhook router gains `disc:*` callback handlers alongside the existing `confirm:*` handlers. Three new tables are needed (migration 0005 extends tenders with `source`/`spgz_code`/`region`; migrations 0006/0007 create `client_filters` and `tender_matches`).

The single most important constraint to communicate to the planner: **the existing `ApplicationCreate` Pydantic schema has a `lots_data_must_be_non_empty` validator** that will reject any call with `lots_data=[]`. The Telegram "Участвуем" handler cannot reuse the HTTP-layer `create_application` path. Phase 7 must add a new internal service function `create_discovery_draft(db, user_id, tender_id)` that constructs an `Application` ORM object directly (bypassing the schema) and commits it. This is the only new service code that touches the existing application pipeline.

**Primary recommendation:** Wave 1 is pure backend (schema + workers + matching + CRUD endpoints); Wave 2 is Telegram extension + frontend. Both waves are independently testable. The two waves can be executed sequentially within a single agent pass or split across two parallel agents.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Batch goszakup fetch + upsert | Backend (ARQ worker) | — | External API call + DB write; browser never involved |
| Rule-based matching | Backend (ARQ task) | — | User filters are server-side data; matching is CPU-only |
| Telegram notification dispatch | Backend (ARQ task / service) | — | Bot token is server-only; sending from browser is impossible |
| Telegram callback handling | Backend (FastAPI webhook) | — | Telegram POST comes from Telegram servers to the backend |
| Discovery feed (read) | Frontend (Next.js client page) | Backend (REST API) | `useQuery` fetches `/api/discovery/matches` owned by backend |
| Filter settings (write) | Frontend (Next.js client page) | Backend (REST API) | PUT to `/api/discovery/filters` |
| Status badge rendering | Frontend (component) | — | Display-only, mirrors ApplicationStatusBadge pattern |
| IDOR enforcement | Backend (FastAPI) | — | All queries filter by `user_id` from JWT |

---

## Standard Stack

### Core (already in project — no new installs)

| Library | Version | Purpose | Source |
|---------|---------|---------|--------|
| arq | 0.28.0 | ARQ cron + job queue | `[VERIFIED: pyproject.toml]` |
| python-telegram-bot | 22.8 | Telegram send + webhook | `[VERIFIED: pyproject.toml]` |
| httpx | 0.28.1 | async HTTP for goszakup GraphQL | `[VERIFIED: pyproject.toml]` |
| tenacity | (pinned in prod) | retry/backoff on goszakup calls | `[VERIFIED: pyproject.toml]` |
| sqlalchemy[asyncio] | 2.0.37 | ORM + async session | `[VERIFIED: pyproject.toml]` |
| alembic | 1.14.0 | DB migrations | `[VERIFIED: pyproject.toml]` |
| pydantic v2 | 2.10.5 | schema validation | `[VERIFIED: pyproject.toml]` |

**No new dependencies required for Phase 7.** All needed libraries are already installed. pg_trgm extension is explicitly NOT recommended (see Matching Strategy section).

---

## Architecture Patterns

### System Architecture Diagram

```
[goszakup GraphQL API]
       │ TrdBuy batch query (every 15 min)
       ▼
[ARQ: poll_goszakup_discovery] ──upsert──► [PostgreSQL: tenders table]
       │                                          │
       │ enqueue_job("run_matching")              │ (new/updated tenders since last poll)
       ▼                                          │
[ARQ: run_matching] ◄──────────────────────────── ┘
       │
       │ for each (user, filter) combination
       │   apply ILIKE keywords, region, spgz_code, amount range
       │   ON CONFLICT (user_id, tender_id) DO NOTHING
       ▼
[PostgreSQL: tender_matches table]
       │
       │ (status=matched → notified if telegram_chat_id exists)
       ▼
[telegram_service.send_discovery_notification()]
       │
       │ disc:participate:{match_id} / disc:skip:{match_id}
       ▼
[Telegram User]
       │ callback_query to POST /api/telegram/webhook
       ▼
[FastAPI: telegram_webhook.py] ── disc:participate ──► [application_service.create_discovery_draft()]
       │                                                         ▼
       │                                              [PostgreSQL: applications table, status=draft]
       │
       └── disc:skip ──► [tender_matches.status = skipped]

[Frontend: /discovery page]
       │ useQuery GET /api/discovery/matches
       ▼
[FastAPI: discovery router] ── SELECT * FROM tender_matches WHERE user_id=? ORDER BY created_at DESC

[Frontend: /discovery/filters page]
       │ PUT /api/discovery/filters  (upsert semantics)
       ▼
[FastAPI: discovery router] ── INSERT ... ON CONFLICT (user_id) DO UPDATE
```

### Recommended Project Structure

```
backend/app/
├── models/
│   ├── tender.py            # EXTEND: add source, spgz_code, region columns
│   ├── client_filter.py     # NEW: ClientFilter ORM model
│   └── tender_match.py      # NEW: TenderMatch ORM model
├── schemas/
│   ├── client_filter.py     # NEW: ClientFilterCreate, ClientFilterResponse
│   └── tender_match.py      # NEW: TenderMatchResponse
├── routers/
│   ├── telegram_webhook.py  # EXTEND: add disc:* handler block
│   └── discovery.py         # NEW: /api/discovery/filters + /api/discovery/matches
├── services/
│   ├── goszakup_service.py  # EXTEND: add fetch_tenders_batch()
│   ├── telegram_service.py  # EXTEND: add send_discovery_notification()
│   ├── matching_service.py  # NEW: match_tenders_for_user()
│   └── application_service.py  # EXTEND: add create_discovery_draft()
└── workers/
    ├── tasks/
    │   ├── poll_goszakup_discovery.py  # NEW: ARQ cron task
    │   └── run_matching.py             # NEW: ARQ on-demand task
    └── worker_settings.py              # EXTEND: add new cron + function

frontend/src/
├── app/(dashboard)/
│   ├── discovery/
│   │   └── page.tsx              # NEW: discovery feed
│   └── discovery-filters/
│       └── page.tsx              # NEW: filter settings
├── components/
│   └── discovery/
│       ├── TenderMatchCard.tsx       # NEW: match card
│       └── TenderMatchStatusBadge.tsx # NEW: mirrors ApplicationStatusBadge
├── types/
│   └── discovery.ts              # NEW: TenderMatchResponse, ClientFilterResponse
├── middleware.ts                 # EXTEND: add /discovery to protectedRoutes
└── components/layout/
    └── Sidebar.tsx               # EXTEND: add /discovery nav item + Telegram bot link
```

---

## Existing Code Inventory (read before writing)

### backend/app/models/tender.py — Current columns
`[VERIFIED: read from file]`

| Column | Type | Notes for Phase 7 |
|--------|------|-------------------|
| `id` | PK | — |
| `number_anno` | String(100), UNIQUE | serves as `external_number` for goszakup |
| `name_ru` | Text, nullable | used in ILIKE keyword matching |
| `name_kz` | Text, nullable | also used in keyword matching |
| `total_sum` | Numeric(18,2), nullable | used in amount range filter |
| `customer_name_ru` | String(500), nullable | displayed in TenderMatchCard |
| `customer_name_kz` | String(500), nullable | displayed in TenderMatchCard |
| `status_id` | Integer, nullable | — |
| `status_name_ru` | String(200), nullable | — |
| `start_date` | DateTime+tz, nullable | — |
| `end_date` | DateTime+tz, nullable | **IS the submission deadline** — use as `deadline_at` in the "Участвуем" guard; no new column needed |
| `publish_date` | DateTime+tz, nullable | — |
| `lots_data` | JSONB, nullable | raw lots array |
| `raw_data` | JSONB, nullable | spec calls it `raw_payload` — **already exists** |
| `cached_at` | DateTime+tz | — |
| `created_at` | DateTime+tz | — |

**New columns to add in migration 0005:**

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `source` | Text, NOT NULL | `'goszakup'` | future multi-source support |
| `region` | Text, nullable | NULL | region matching in client_filters |
| `spgz_code` | Text, nullable | NULL | СПГЗ code for exact-match filter |

**Do NOT add:** `deadline_at` (use `end_date` instead), `raw_payload` (already `raw_data`), `UNIQUE(source, external_number)` (D-01 locks sk.kz; existing `UNIQUE(number_anno)` is sufficient).

### backend/app/services/application_service.py — Critical constraint
`[VERIFIED: read from file]`

The public function `create_application(db, user_id, data: ApplicationCreate)` uses a Pydantic schema that has:

```python
@field_validator("lots_data")
@classmethod
def lots_data_must_be_non_empty(cls, v: list[LotOffer]) -> list[LotOffer]:
    if not v:
        raise ValueError("lots_data не может быть пустым — нужен хотя бы один лот")
    return v
```

**This validator blocks any call with `lots_data=[]`.** The "Участвуем" Telegram handler and the discovery feed "Участвуем" button cannot use `create_application` directly. Phase 7 MUST add a new internal service function:

```python
async def create_discovery_draft(
    db: AsyncSession,
    user_id: int,
    tender_id: int,
) -> Application:
    """Create an Application draft from a discovery match (no lots data yet).

    Bypasses ApplicationCreate schema validation — lots are filled in later
    via the application wizard. Status is always 'draft'.
    """
    app = Application(
        user_id=user_id,
        tender_id=tender_id,
        lots_data=[],
        document_ids=[],
        status="draft",
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return app
```

### backend/app/routers/telegram_webhook.py — Existing structure
`[VERIFIED: read from file]`

The existing webhook router:
1. Verifies `X-Telegram-Bot-Api-Secret-Token` header (T-05-31)
2. Parses `callback_query.data` splitting on `:`
3. Checks `parts[0] == "confirm"` (hard-coded string match)
4. Performs IDOR check: `caller_chat_id == owner.telegram_chat_id`

The `disc:*` handlers must be added as a second `elif parts[0] == "disc":` block in the same function body. The IDOR check pattern is identical — load `TenderMatch` by `match_id`, then verify `match.user_id`'s `telegram_chat_id` == `caller_chat_id`.

**Important:** The current parser `if len(parts) != 3 or parts[0] != "confirm": return {"ok": True}` will silently drop all `disc:*` callbacks. This guard must be changed to accept both prefixes before the action-specific dispatch:

```python
if len(parts) != 3 or parts[0] not in ("confirm", "disc"):
    return {"ok": True}
```

### backend/app/workers/worker_settings.py — ARQ cron registration
`[VERIFIED: read from file]`

Current pattern:
```python
from arq import cron

cron_jobs = [
    cron(
        poll_watchlist_tenders,
        minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
        unique=True,
    )
]
functions = [auto_submit_application]
```

Phase 7 additions:
```python
from app.workers.tasks.poll_goszakup_discovery import poll_goszakup_discovery
from app.workers.tasks.run_matching import run_matching

cron_jobs = [
    cron(poll_watchlist_tenders, minute={0,5,10,15,20,25,30,35,40,45,50,55}, unique=True),
    cron(poll_goszakup_discovery, minute={0, 15, 30, 45}, unique=True),
]
functions = [auto_submit_application, run_matching]
```

`run_matching` is in `functions` (not `cron_jobs`) because it is enqueued by `poll_goszakup_discovery`, not run on a schedule of its own.

---

## Architecture Patterns

### Pattern 1: goszakup Batch Fetch

The existing `goszakup_service.py` queries one tender by `numberAnno`. For batch discovery, extend with a new function `fetch_tenders_batch(since: datetime, limit: int = 50, offset: int = 0)`.

**Proposed GraphQL query** `[ASSUMED — lastUpdateDate as filter field not independently verified in this session, but field name confirmed in existing codebase response; multi-source goszakup docs are behind auth]`:

```python
BATCH_QUERY = """
query TendersBatch($since: String!, $limit: Int!, $offset: Int!) {
  TrdBuy(
    filter: { lastUpdateDate: $since }
    limit: $limit
    offset: $offset
  ) {
    id
    numberAnno
    nameRu
    nameKz
    totalSum
    customerBin
    customerNameRu
    customerNameKz
    refBuyStatusId
    RefBuyStatus { id nameRu }
    startDate
    endDate
    publishDate
    lastUpdateDate
    Lots {
      id
      lotNumber
      nameRu
      nameKz
      amount
      refEnstruCode       # СПГЗ code candidate — verify field name against live schema
    }
  }
}
"""
```

**СПГЗ code field name is ASSUMED.** The field `refEnstruCode` is the likely candidate for KTRU/СПГЗ codes in goszakup GraphQL Lots, but was not independently verified by running a live query. The migration adds `spgz_code` as nullable; the poll worker populates it once the correct field name is confirmed via a live schema introspection call.

**Pagination strategy:** Increment `offset` by `limit` until response contains fewer items than `limit`. Store `last_polled_at` timestamp in Redis key `discovery:last_polled_at`. On first run, default to 7 days ago.

**Redis state:**
```python
LAST_POLLED_KEY = "discovery:last_polled_at"

# Read:
ts = await redis.get(LAST_POLLED_KEY)
since = datetime.fromisoformat(ts) if ts else (utcnow() - timedelta(days=7))

# Write after successful poll:
await redis.set(LAST_POLLED_KEY, utcnow().isoformat())
```

**Upsert strategy:** `INSERT INTO tenders (...) ON CONFLICT (number_anno) DO UPDATE SET name_ru=..., total_sum=..., region=..., raw_data=..., cached_at=now()`. Use SQLAlchemy `insert().on_conflict_do_update()` — same pattern as any goszakup upsert.

### Pattern 2: Rule-based Matching

`matching_service.py` receives a list of `tender_ids` (those upserted in the current poll), loads each user's `ClientFilter`, and applies rules:

```python
async def match_tenders_for_user(
    db: AsyncSession,
    user_id: int,
    cf: ClientFilter,
    new_tender_ids: list[int],
) -> list[int]:
    """Return tender_ids from new_tender_ids that match cf.

    Rules (all nullable fields default to "no filter"):
    - keywords: any keyword ILIKE matches name_ru OR name_kz → include
    - region: cf.region is not None → tender.region == cf.region (exact)
    - spgz_codes: non-empty list → tender.spgz_code IN cf.spgz_codes
    - min_amount / max_amount: applied to tender.total_sum
    """
```

Keyword ILIKE example (SQLAlchemy):
```python
from sqlalchemy import or_

keyword_clauses = [
    or_(
        Tender.name_ru.ilike(f"%{kw}%"),
        Tender.name_kz.ilike(f"%{kw}%"),
    )
    for kw in cf.keywords
]
# OR-join across keywords: any keyword hit = match
filter_clause = or_(*keyword_clauses)
```

### Pattern 3: tender_match Upsert

After matching, insert into `tender_matches` with `ON CONFLICT (user_id, tender_id) DO NOTHING` to avoid duplicate notifications:

```python
from sqlalchemy.dialects.postgresql import insert as pg_insert

stmt = pg_insert(TenderMatch).values(
    user_id=user_id,
    tender_id=tender_id,
    status="matched",
).on_conflict_do_nothing(index_elements=["user_id", "tender_id"])
await db.execute(stmt)
```

### Pattern 4: Discovery Notification Message

Add to `telegram_service.py`:

```python
async def send_discovery_notification(
    bot_token: str,
    chat_id: int,
    match_id: int,
    tender_name: str,
    customer_name: str,
    total_sum: Decimal | None,
    deadline: datetime | None,
    region: str | None,
) -> None:
    """Send discovery match card with Участвуем/Пропустить buttons.

    callback_data format (D-04):
      disc:participate:{match_id}
      disc:skip:{match_id}
    """
    keyboard = [[
        InlineKeyboardButton("Участвуем", callback_data=f"disc:participate:{match_id}"),
        InlineKeyboardButton("Пропустить", callback_data=f"disc:skip:{match_id}"),
    ]]
    ...
```

### Pattern 5: Frontend Discovery Page

Mirrors `applications/page.tsx` exactly:

```tsx
'use client'

export default function DiscoveryPage() {
  const { data, error, isLoading } = useQuery<TenderMatchResponse[]>({
    queryKey: ['discovery-matches'],
    queryFn: () => api.get<TenderMatchResponse[]>('/api/discovery/matches'),
    retry: false,
  })
  // empty state / error / loading — same as applications/page.tsx
}
```

### Pattern 6: Sidebar Extension
`[VERIFIED: read from Sidebar.tsx]`

```tsx
// Add to navItems array:
{ href: '/discovery', label: 'Подборка', icon: SparklesIcon },

// Add as a separate non-nav anchor below navItems loop, above the Logout button:
<a
  href={`https://t.me/${process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME}`}
  target="_blank"
  rel="noopener noreferrer"
  className="flex items-center gap-3 px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground rounded-lg"
>
  <ExternalLink className="h-4 w-4 shrink-0" />
  Telegram бот
</a>
```

Import `SparklesIcon` or `Telescope` from `lucide-react` for the discovery icon (both available in Lucide).

---

## DB Schema — New Tables

### Migration 0005: extend_tenders_add_source_fields

```sql
ALTER TABLE tenders
  ADD COLUMN source TEXT NOT NULL DEFAULT 'goszakup',
  ADD COLUMN region TEXT,
  ADD COLUMN spgz_code TEXT;
```

**Do NOT add** `UNIQUE(source, external_number)` — D-01 locks out sk.kz so the existing `UNIQUE(number_anno)` constraint is sufficient.

**Do NOT add** `deadline_at` — `end_date` already exists and semantically equals the submission deadline.

**Do NOT rename** `raw_data` — spec calls it `raw_payload` but the column already exists as `raw_data`.

### Migration 0006: create_client_filters

```sql
CREATE TABLE client_filters (
  id          SERIAL PRIMARY KEY,
  user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  keywords    TEXT[] NOT NULL DEFAULT '{}',
  spgz_codes  TEXT[] NOT NULL DEFAULT '{}',
  region      TEXT,
  min_amount  NUMERIC(18, 2),
  max_amount  NUMERIC(18, 2),
  created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  UNIQUE (user_id)   -- one filter set per user (D-10)
);
```

### Migration 0007: create_tender_matches

```sql
CREATE TABLE tender_matches (
  id           SERIAL PRIMARY KEY,
  user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  tender_id    INTEGER NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
  status       TEXT NOT NULL DEFAULT 'matched',
  notified_at  TIMESTAMP WITH TIME ZONE,
  decided_at   TIMESTAMP WITH TIME ZONE,
  created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, tender_id)
);

CREATE INDEX idx_tender_matches_user_id ON tender_matches(user_id);
CREATE INDEX idx_tender_matches_status  ON tender_matches(status);
```

**No `profitability` column** (D-02).

**Status values:** `matched` | `notified` | `skipped` | `participating`

---

## Matching Strategy: ILIKE vs pg_trgm

**Recommendation: ILIKE for MVP.** `[ASSUMED — based on volume estimate; not benchmarked]`

Rationale:
- `run_matching` processes only tenders inserted/updated since the last poll (15-min window). In practice, goszakup publishes 50–200 tenders per 15-minute window at peak. The matching query scans this small subset (not the full tenders table).
- ILIKE `%keyword%` on 200 rows is instantaneous. No GIN index needed for this volume.
- pg_trgm requires `CREATE EXTENSION pg_trgm` in Alembic migration, adds complexity, and is needed only when matching runs on the full table or when keyword count per user is very high (> 20).
- Add pg_trgm index in v1.1 if matching latency is measured and exceeds 1 second on real workloads.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ARQ job dedup | manual Redis key check | stable `_job_id` parameter | ARQ handles dedup natively — confirmed in existing `auto_submit` code |
| Upsert with conflict | SELECT-then-INSERT | `pg_insert().on_conflict_do_nothing()` | race-condition safe; existing pattern in goszakup service |
| Telegram send | custom HTTP to Telegram API | `python-telegram-bot 22.8` (already installed) | `async with telegram.Bot(token)` pattern confirmed in `telegram_service.py` |
| Retry on goszakup failure | manual loop | `@retry(tenacity)` (already imported) | consistent retry across all goszakup calls; `_is_retryable` function reusable |
| IDOR protection | 403 on mismatch | return 404 always | existing pattern T-05-30 confirmed correct — don't leak resource existence |

---

## Common Pitfalls

### Pitfall 1: ApplicationCreate validator blocks "Участвуем"
**What goes wrong:** Calling `create_application(db, user_id, ApplicationCreate(tender_id=..., lots_data=[]))` raises `ValueError: lots_data не может быть пустым`.
**Why it happens:** The existing Pydantic schema validator was designed for the wizard flow where lots are always provided.
**How to avoid:** Add `create_discovery_draft(db, user_id, tender_id)` to `application_service.py`. This function constructs the ORM object directly, bypassing schema validation.
**Warning signs:** If the planner attempts to call `create_application` from the Telegram handler, it will fail at runtime with a 422-equivalent ValidationError.

### Pitfall 2: Telegram webhook drops disc:* callbacks silently
**What goes wrong:** The existing guard `if len(parts) != 3 or parts[0] != "confirm": return {"ok": True}` drops all `disc:*` callbacks with no log entry.
**Why it happens:** The guard was written for a single prefix.
**How to avoid:** Change guard to `parts[0] not in ("confirm", "disc")` before dispatching. Add the `disc:*` dispatch block as a separate `elif` branch.
**Warning signs:** Telegram callback buttons appear to send successfully (Telegram confirms 200) but no action occurs in the backend.

### Pitfall 3: Duplicate tender_match records on concurrent polls
**What goes wrong:** Two `run_matching` jobs run concurrently and both try to insert the same `(user_id, tender_id)` pair.
**Why it happens:** `unique=True` on the cron only prevents concurrent runs of the poll cron itself — it does not prevent concurrent `run_matching` on-demand jobs if the poll is fast.
**How to avoid:** Use `ON CONFLICT (user_id, tender_id) DO NOTHING` in the tender_match insert. The UNIQUE constraint is the safety net.
**Warning signs:** Duplicate notifications sent to the same user for the same tender.

### Pitfall 4: end_date vs deadline_at confusion
**What goes wrong:** Developer adds a new `deadline_at` column to tenders, runs migration, but the poll worker only populates `end_date` (from the existing mapping). The "Участвуем" guard checks `deadline_at` which is always NULL → no deadline enforcement.
**Why it happens:** Spec mentions `deadline_at` but the existing model already has `end_date` for the same field.
**How to avoid:** Use `tender.end_date` everywhere in Phase 7 code. Do NOT add `deadline_at`. Document this in a code comment: `# end_date = submission deadline in goszakup (called deadline_at in Phase 7 spec)`.

### Pitfall 5: DB session in ARQ worker
**What goes wrong:** `run_matching` calls `get_db()` FastAPI dependency or imports `AsyncSessionLocal` directly instead of using `ctx["db_session_factory"]`.
**Why it happens:** FastAPI's `get_db` is a dependency injection for HTTP request handlers, not for ARQ workers.
**How to avoid:** Follow existing pattern from `poll_watchlist.py`: `async with ctx["db_session_factory"]() as session:`. This is documented as ARQ pitfall #6 in the existing code comments.

### Pitfall 6: Middleware doesn't protect /discovery
**What goes wrong:** Unauthenticated users can access `/discovery` without a JWT cookie.
**Why it happens:** `frontend/src/middleware.ts` has a hardcoded list: `const protectedRoutes = ['/dashboard', '/profile', '/tenders', '/applications', '/documents']`. `/discovery` is not in this list.
**How to avoid:** Add `'/discovery'` and `'/discovery-filters'` to `protectedRoutes` in `middleware.ts`.

### Pitfall 7: SPGZ field name in goszakup GraphQL
**What goes wrong:** The batch query requests `refEnstruCode` (ASSUMED field name) but the actual field is different → query returns null for all lots, no СПГЗ matching works.
**Why it happens:** The existing `TENDER_QUERY` doesn't fetch classifier codes; the correct field name was not verified in this research session.
**How to avoid:** Before coding the batch query, run a GraphQL introspection on the live API: `query { __type(name: "Lot") { fields { name } } }`. Use the confirmed field name. Add to migration 0005 comment: "populate spgz_code from field X once confirmed".

---

## Wave Structure

### Wave 1 — Backend (can be executed by backend agent alone)

**Task 1: DB Schema**
- Migration 0005: extend tenders table (`source`, `region`, `spgz_code`)
- Migration 0006: create `client_filters` table
- Migration 0007: create `tender_matches` table
- `models/client_filter.py` — ClientFilter ORM
- `models/tender_match.py` — TenderMatch ORM
- Pydantic schemas: `schemas/client_filter.py`, `schemas/tender_match.py`

**Task 2: Data Pipeline**
- Extend `goszakup_service.py` with `fetch_tenders_batch(since, limit, offset)`
- `workers/tasks/poll_goszakup_discovery.py` — ARQ cron, reads/writes `discovery:last_polled_at`
- `services/matching_service.py` — `match_tenders_for_user()` with ILIKE + region + spgz + amount
- `workers/tasks/run_matching.py` — ARQ on-demand task, calls matching_service, creates tender_match records
- Extend `worker_settings.py` (add to `cron_jobs` + `functions`)

**Task 3: CRUD Endpoints**
- `routers/discovery.py` — `GET /api/discovery/matches`, `GET /api/discovery/filters`, `PUT /api/discovery/filters`
- `services/application_service.py` — add `create_discovery_draft(db, user_id, tender_id)` (new internal function)
- Register router in `main.py`: `app.include_router(discovery.router, prefix="/api", tags=["discovery"])`

### Wave 2 — Telegram + Frontend

**Task 4: Telegram Extension**
- Extend `telegram_service.py` with `send_discovery_notification()`
- Extend `telegram_webhook.py`: fix prefix guard, add `disc:participate` and `disc:skip` handlers
  - `disc:participate`: load TenderMatch → IDOR check → `create_discovery_draft()` → update match status → answer callback
  - `disc:skip`: load TenderMatch → IDOR check → update match status → answer callback
- Call `send_discovery_notification` from `run_matching` (after inserting match records)

**Task 5: Frontend**
- `/discovery/page.tsx` — discovery feed with `useQuery`, TenderMatchCard list, empty/error/loading states
- `/discovery-filters/page.tsx` — filter form with PUT to `/api/discovery/filters`
- `components/discovery/TenderMatchCard.tsx` — card: title, customer, amount, deadline, region, source badge, status badge, action buttons
- `components/discovery/TenderMatchStatusBadge.tsx` — mirrors `ApplicationStatusBadge`; statuses: `matched`→"Новый", `notified`→"Уведомлён", `skipped`→"Пропущен", `participating`→"Участвуем"
- `types/discovery.ts` — `TenderMatchResponse`, `ClientFilterResponse`
- Extend `Sidebar.tsx` — add `/discovery` nav item + Telegram bot external link
- Extend `middleware.ts` — add `/discovery` and `/discovery-filters` to `protectedRoutes`
- Add `NEXT_PUBLIC_TELEGRAM_BOT_USERNAME` to `.env.example` and `frontend/.env.example`

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| Config file | `backend/pytest.ini` (exists) |
| Quick run command | `cd backend && pytest tests/test_matching_service.py -x` |
| Full suite command | `cd backend && pytest tests/ -x` |
| Mock library | respx 0.23.1 (for goszakup HTTP mocks), fakeredis (for Redis) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | File |
|--------|----------|-----------|------|
| DISC-01 | PUT /api/discovery/filters upserts correctly; second PUT replaces | integration | `tests/test_discovery_filters.py` |
| DISC-01 | GET /api/discovery/filters returns current filter set | integration | `tests/test_discovery_filters.py` |
| DISC-02 | `fetch_tenders_batch` calls goszakup with correct lastUpdateDate + paginates | unit (respx) | `tests/test_goszakup_batch.py` |
| DISC-02 | `poll_goszakup_discovery` writes `last_polled_at` to Redis | unit (fakeredis) | `tests/test_poll_discovery.py` |
| DISC-03 | `match_tenders_for_user` returns tender when keyword ILIKE matches `name_ru` | unit | `tests/test_matching_service.py` |
| DISC-03 | `match_tenders_for_user` respects region exact-match | unit | `tests/test_matching_service.py` |
| DISC-03 | `match_tenders_for_user` respects amount range | unit | `tests/test_matching_service.py` |
| DISC-03 | ON CONFLICT (user_id, tender_id) DO NOTHING prevents duplicates | integration | `tests/test_matching_service.py` |
| DISC-04 | GET /api/discovery/matches returns only current user's matches | integration (IDOR) | `tests/test_discovery_matches.py` |
| DISC-05 | `disc:participate:{match_id}` from wrong chat_id is silently ignored | integration | `tests/test_telegram_disc_webhook.py` |
| DISC-05 | `disc:participate:{match_id}` creates Application with status=draft | integration | `tests/test_telegram_disc_webhook.py` |
| DISC-05 | `disc:skip:{match_id}` sets match status=skipped | integration | `tests/test_telegram_disc_webhook.py` |
| DISC-05 | `create_discovery_draft` creates Application with empty lots_data | unit | `tests/test_application_service.py` |

### Wave 0 Gaps (test files to create before implementation)

- [ ] `tests/test_matching_service.py` — unit tests for matching_service (no DB needed, mock Tender objects)
- [ ] `tests/test_goszakup_batch.py` — respx mocks for batch endpoint
- [ ] `tests/test_poll_discovery.py` — integration test with fakeredis
- [ ] `tests/test_discovery_filters.py` — CRUD integration tests
- [ ] `tests/test_discovery_matches.py` — IDOR integration tests
- [ ] `tests/test_telegram_disc_webhook.py` — webhook handler tests (extend existing `test_telegram_webhook.py` pattern)

---

## Environment Availability

| Dependency | Required By | Available | Notes |
|------------|-------------|-----------|-------|
| PostgreSQL | All DB migrations | Assumed up (existing phases use it) | `[ASSUMED — not probed in this session]` |
| Redis | ARQ cron + `discovery:last_polled_at` key | Assumed up | `[ASSUMED]` |
| ARQ worker process | Cron jobs | Assumed running (existing phases) | Must restart after `worker_settings.py` change |
| goszakup GraphQL API | `fetch_tenders_batch` | Confirmed reachable (SPIKE-01, existing code) | `[VERIFIED: existing goszakup_service.py]` |
| python-telegram-bot | send_discovery_notification | 22.8 installed | `[VERIFIED: pyproject.toml]` |
| NEXT_PUBLIC_TELEGRAM_BOT_USERNAME | Sidebar Telegram link | Not in codebase yet | Must be added to `.env.example` |

**Missing with no fallback:** None that block execution.

**New env var required:** `NEXT_PUBLIC_TELEGRAM_BOT_USERNAME` — must be added to `frontend/.env.example` and documented.

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V4 Access Control | YES | `user_id` from JWT always; all tender_match queries filter by `user_id`; return 404 on mismatch |
| V5 Input Validation | YES | Pydantic schemas for ClientFilterCreate; keywords sanitized before ILIKE (no SQL injection risk with SQLAlchemy parameterized queries) |
| V3 Session Management | No | No new session logic |
| V2 Authentication | No | Existing JWT middleware covers /discovery routes |
| V6 Cryptography | No | No new crypto operations |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| IDOR on `disc:*` Telegram callbacks | Elevation of Privilege | Verify `caller_chat_id == match.owner.telegram_chat_id` — mirror of existing T-05-30 pattern |
| IDOR on GET /api/discovery/matches | Information Disclosure | `WHERE user_id = <jwt_user_id>` — return 404 on non-owned match_id |
| ILIKE injection (e.g., `%` in keywords) | Tampering | SQLAlchemy `.ilike()` uses parameterized queries — safe by default; PostgreSQL `%` in ILIKE is a valid wildcard, not a security risk |
| Open filter PUT replaces entire record | Denial of Service (self) | Upsert semantics are correct; validate keyword list length (max N, e.g. 20) |
| Telegram message flooding per match | Denial of Service | `ON CONFLICT DO NOTHING` dedup + `UNIQUE(user_id, tender_id)` — one notification per match |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `lastUpdateDate` is a valid filter field in `TrdBuy` goszakup GraphQL | Pattern 1 (batch query) | Poll worker would need to paginate all tenders and filter in-app instead; higher load, same results |
| A2 | `refEnstruCode` is the GraphQL field name for СПГЗ code in Lots | Pattern 1 + migration 0005 | Field would return null; spgz_code column stays NULL; СПГЗ filter silently does nothing |
| A3 | goszakup publishes 50–200 tenders per 15-min window (volume estimate for ILIKE strategy) | Matching Strategy | If volume is 10,000+/window, ILIKE will be slow; add pg_trgm index as emergency mitigation |
| A4 | `end_date` in goszakup = submission deadline (deadline_at in spec) | DB Schema section | If wrong field is used for deadline check, "Участвуем" guard may reject valid or accept expired tenders |
| A5 | PostgreSQL and Redis are running in the development environment | Environment Availability | Execution would fail; developer must start Docker Compose services |

---

## Open Questions

1. **What is the exact СПГЗ code field name in goszakup GraphQL Lots?**
   - What we know: `lots_data` JSONB in the DB holds the raw Lots array; existing query fetches `id, lotNumber, nameRu, nameKz, descriptionRu, amount, refLotStatusId`
   - What's unclear: the field name for KTRU/СПГЗ classifier code (might be `refEnstruCode`, `ktruCode`, or something else)
   - Recommendation: Add a one-time GraphQL introspection task in Wave 1, Task 2: `query { __type(name: "Lot") { fields { name } } }`. Use the result to populate `spgz_code` mapping. Make `spgz_code` nullable so the column exists even before the field name is confirmed.

2. **Does goszakup GraphQL `TrdBuy` filter support `lastUpdateDate` comparison operators (gte)?**
   - What we know: the `numberAnno` filter uses direct string equality. The `lastUpdateDate` field appears in responses.
   - What's unclear: whether the filter API supports range operators like `{gte: "..."}`
   - Recommendation: If `gte` is not supported, alternative is to paginate all tenders ordered by `lastUpdateDate` DESC and stop when `lastUpdateDate < last_polled_at`. Document whichever approach works in a `# SPIKE-BATCH` comment in the code.

3. **Should /discovery-filters be a separate page or a section within /profile?**
   - What we know: D-10 says one filter set per user; D-12 says /discovery is the feed page
   - What's unclear: whether the filter configuration lives at `/discovery-filters`, `/settings/discovery`, or as a drawer/modal on `/discovery` itself
   - Recommendation: Create `/discovery-filters` as a standalone page (simplest; follows existing pattern of separate pages for profile, documents, etc.)

---

## Sources

### Primary (HIGH confidence)
- `[VERIFIED: backend/app/models/tender.py]` — existing tenders table columns
- `[VERIFIED: backend/app/schemas/application.py]` — ApplicationCreate validator, lots_data_must_be_non_empty
- `[VERIFIED: backend/app/workers/worker_settings.py]` — ARQ cron registration pattern
- `[VERIFIED: backend/app/workers/tasks/poll_watchlist.py]` — ARQ cron task pattern with ctx["db_session_factory"]
- `[VERIFIED: backend/app/workers/tasks/auto_submit.py]` — ARQ Retry/backoff pattern
- `[VERIFIED: backend/app/routers/telegram_webhook.py]` — existing webhook structure, prefix guard, IDOR check
- `[VERIFIED: backend/app/services/telegram_service.py]` — existing send_tender_notification pattern
- `[VERIFIED: backend/app/services/goszakup_service.py]` — GraphQL endpoint, TENDER_QUERY structure, lastUpdateDate in response
- `[VERIFIED: backend/app/services/application_service.py]` — create_application signature and ORM pattern
- `[VERIFIED: backend/alembic/versions/]` — migration file list, next number is 0005
- `[VERIFIED: frontend/src/app/(dashboard)/applications/page.tsx]` — useQuery pattern, error/loading/empty states
- `[VERIFIED: frontend/src/components/layout/Sidebar.tsx]` — navItems array pattern, logout section
- `[VERIFIED: frontend/src/middleware.ts]` — protectedRoutes list (missing /discovery)
- `[VERIFIED: frontend/src/components/applications/ApplicationStatusBadge.tsx]` — STATUS_CONFIG pattern to replicate
- `[VERIFIED: backend/pyproject.toml]` — all installed dependencies confirmed

### Secondary (MEDIUM confidence)
- `[CITED: .planning/phases/07-discovery-matching/07-CONTEXT.md]` — locked decisions, deferred items
- `[CITED: .planning/REQUIREMENTS.md]` — DISC-01 through DISC-06 requirement text

### Tertiary (LOW / ASSUMED)
- A1–A5 listed in Assumptions Log above

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries confirmed in pyproject.toml; no new installs needed
- DB schema (existing columns): HIGH — read from ORM model directly
- DB schema (new columns): HIGH — derived from CONTEXT.md decisions + confirmed missing from existing model
- ARQ cron pattern: HIGH — copied from existing worker_settings.py
- Telegram webhook extension pattern: HIGH — read from existing router file
- goszakup batch query filter syntax: MEDIUM — field names confirmed from existing code; filter operator syntax ASSUMED
- СПГЗ code field name: LOW — not verified against live GraphQL schema
- Matching ILIKE strategy: MEDIUM — volume estimate is assumed; correctness of ILIKE approach HIGH

**Research date:** 2026-07-19
**Valid until:** 2026-08-19 (stable stack; goszakup GraphQL may change schema without notice)
