# Phase 8: zakup.sk.kz Discovery — Pattern Map

**Mapped:** 2026-08-06
**Files analyzed:** 8 (5 new, 3 modified)
**Analogs found:** 8 / 8

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/services/sk_kz_service.py` | service | request-response | `backend/app/services/goszakup_service.py` | exact (REST vs GraphQL — same retry/httpx pattern) |
| `backend/app/workers/tasks/poll_sk_kz_discovery.py` | worker/task | batch, event-driven | `backend/app/workers/tasks/poll_goszakup_discovery.py` | exact |
| `backend/app/workers/worker_settings.py` | config | — | itself | modify — add one cron entry |
| `backend/app/services/telegram_service.py` | service | request-response | itself | modify — extend `send_discovery_notification` signature |
| `frontend/src/components/discovery/TenderMatchCard.tsx` | component | request-response | itself | modify — replace hardcoded badge with dynamic source |
| `frontend/src/types/discovery.ts` | utility/types | — | itself | modify — add `source` field |
| `backend/tests/test_sk_kz_service.py` | test | — | `backend/tests/test_goszakup_batch.py` | exact |
| `backend/tests/test_poll_sk_kz_discovery.py` | test | — | `backend/tests/test_poll_discovery.py` | exact |

---

## Pattern Assignments

### `backend/app/services/sk_kz_service.py` (service, request-response)

**Analog:** `backend/app/services/goszakup_service.py`

**Imports pattern** (lines 18-33 of analog):
```python
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings

logger = logging.getLogger(__name__)
```

**Base URL constant pattern** — sk.kz replaces GRAPHQL_URL:
```python
# All external endpoints share this prefix (confirmed from HAR 2026-08-06)
_SK_BASE = "https://zakup.sk.kz/eprocsearch/api/external/4dv3rts"

# POST body defaults
_DEFAULT_ADVERT_STATUS = "PUBLISHED"
_DEFAULT_LOT_STATUS = "PUBLISHED"
_PAGE_SIZE = 50
```

**Retryable-predicate pattern** (lines 161-171 of analog) — copy verbatim:
```python
def _is_retryable(exc: BaseException) -> bool:
    """Return True only for 5xx responses and network-level errors.

    NEVER retry 4xx (401/403/404) — doing so would hammer the API unnecessarily
    and would not fix authentication or not-found conditions.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        return True
    return False
```

**Retry decorator + async function pattern** (lines 174-204 of analog):
```python
@retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def fetch_sk_tenders_page(
    since: datetime,
    page: int = 0,
    size: int = _PAGE_SIZE,
) -> list[dict]:
    """Fetch one page of PUBLISHED tenders from zakup.sk.kz.

    POST /eprocsearch/api/external/4dv3rts/filter?size={size}&page={page}&sort=lastModifiedDate,desc
    Body: {"advertStatus": "PUBLISHED", "lotStatus": "PUBLISHED"}

    Returns tenders whose lastModifiedDate >= since (early-stop possible because
    sk.kz sorts by lastModifiedDate desc — unlike goszakup which sorts by id DESC).
    No auth required for this endpoint (confirmed from HAR 2026-08-06).
    """
    url = f"{_SK_BASE}/filter"
    params = {"size": size, "page": page, "sort": "lastModifiedDate,desc"}
    body = {
        "advertStatus": _DEFAULT_ADVERT_STATUS,
        "lotStatus": _DEFAULT_LOT_STATUS,
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, params=params, json=body)
        response.raise_for_status()

    items: list[dict] = response.json()  # array, not wrapped
    # Early-stop: sk.kz sorts by lastModifiedDate desc, so first item older than
    # since means the rest of the page is also older — caller decides whether to
    # fetch the next page.
    return [item for item in items if _item_updated_since(item, since)]
```

**Date parsing — sk.kz uses ISO 8601 with TZ (simpler than goszakup)**:
```python
def parse_sk_date(value: str | None) -> datetime | None:
    """Parse ISO 8601 date from sk.kz (e.g. '2026-08-17T05:00:00Z').

    sk.kz returns TZ-aware ISO strings — no manual timezone attachment needed
    (unlike goszakup which returns naive Almaty-local strings).
    Returns None on failure — never raises.
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _item_updated_since(item: dict, since: datetime) -> bool:
    """Return True if item['lastModifiedDate'] >= since. Includes on missing date."""
    dt = parse_sk_date(item.get("lastModifiedDate"))
    if dt is None:
        return True  # err on side of inclusion
    return dt >= since
```

**Key difference from goszakup_service.py:**
- No auth header — sk.kz filter endpoint is public (no `Authorization: Bearer` needed)
- Response is a raw JSON array, not `{"data": {"TrdBuy": [...]}}` — parse directly as `response.json()`
- ISO 8601 dates with TZ — use `datetime.fromisoformat()`, not `strptime`
- Supports `page` parameter (offset pagination works) — incremental fetch across pages is possible

---

### `backend/app/workers/tasks/poll_sk_kz_discovery.py` (worker/task, batch)

**Analog:** `backend/app/workers/tasks/poll_goszakup_discovery.py`

**Module docstring + imports pattern** (lines 1-32 of analog):
```python
"""ARQ cron job: poll_sk_kz_discovery.

Runs every 15 minutes (WorkerSettings cron_jobs, unique=True). Fetches new and
updated tenders from zakup.sk.kz filter API, upserts them to the tenders table
with source='sk_kz', and enqueues the run_matching ARQ task.

Registration: worker_settings.py — add to cron_jobs list.

Security / invariants:
  - Uses ctx["db_session_factory"] (NEVER FastAPI get_db) — ARQ pitfall #6.
  - No auth token required for sk.kz filter endpoint (public API).
  - DB writes are parameterised via SQLAlchemy pg_insert() — no raw f-string SQL.

Polling strategy (from RESEARCH.md):
  sk.kz supports sort=lastModifiedDate,desc — incremental polling is reliable.
  Store sk_kz:last_polled_at in Redis to track the window. On first run,
  look back DEFAULT_LOOKBACK_HOURS (unlike goszakup which needs 7 days because
  it sorts by id DESC; sk.kz sorts by lastModifiedDate so a short window works).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.tender import Tender
from app.services.sk_kz_service import fetch_sk_tenders_page, parse_sk_date

logger = logging.getLogger(__name__)
```

**Redis key + constants pattern** (lines 35-42 of analog):
```python
# Redis key — separate namespace from goszakup (sk_kz: prefix)
LAST_POLLED_KEY = "sk_kz:last_polled_at"

# First run: look back 24 hours (sk.kz sorts by lastModifiedDate, so a short
# window works correctly — no need for the 7-day goszakup fallback).
DEFAULT_LOOKBACK_HOURS = 24

_PAGE_SIZE = 50
```

**Main cron task pattern** (lines 44-94 of analog) — adapt for sk.kz incremental poll:
```python
async def poll_sk_kz_discovery(ctx: dict) -> None:
    """ARQ cron: batch-fetch new/updated tenders from zakup.sk.kz and upsert to DB.

    Called every 15 min by WorkerSettings.cron_jobs (unique=True prevents overlap).

    Flow:
      1. Read sk_kz:last_polled_at from Redis (or use DEFAULT_LOOKBACK_HOURS).
      2. Fetch page 0 from sk.kz filter API; early-stop when items older than since.
      3. Upsert each tender with source='sk_kz' via pg_insert ON CONFLICT(number_anno).
      4. Write sk_kz:last_polled_at to Redis ONLY after successful upsert.
      5. Enqueue run_matching ARQ job with list of upserted tender IDs.
    """
    redis = ctx["redis"]

    # Step 1: Compute since
    raw_ts = await redis.get(LAST_POLLED_KEY)
    if raw_ts:
        since = datetime.fromisoformat(raw_ts)
    else:
        since = datetime.now(tz=timezone.utc) - timedelta(hours=DEFAULT_LOOKBACK_HOURS)
    logger.info("poll_sk_kz_discovery: polling since %s", since.isoformat())

    # Step 2: Fetch (single page — sufficient for 15-min interval)
    all_tender_dicts = await fetch_sk_tenders_page(since, page=0, size=_PAGE_SIZE)

    if not all_tender_dicts:
        logger.info("poll_sk_kz_discovery: no new/updated tenders since %s", since.isoformat())
        await redis.set(LAST_POLLED_KEY, datetime.now(tz=timezone.utc).isoformat())
        return

    # Step 3: Upsert
    async with ctx["db_session_factory"]() as session:
        upserted_ids = await _upsert_tenders(session, all_tender_dicts)

    # Step 4: Write last_polled_at ONLY after successful upsert
    await redis.set(LAST_POLLED_KEY, datetime.now(tz=timezone.utc).isoformat())
    logger.info("poll_sk_kz_discovery: upserted %d tenders", len(upserted_ids))

    # Step 5: Enqueue matching
    if upserted_ids:
        await redis.enqueue_job("run_matching", upserted_ids)
```

**_upsert_tenders pattern** (lines 97-130 of analog) — identical structure, different source:
```python
async def _upsert_tenders(session, tender_dicts: list[dict]) -> list[int]:
    """Upsert sk.kz tenders to the tenders table.

    Uses pg_insert().on_conflict_do_update() — race-condition safe.
    number_anno for sk.kz: str(item["id"]) — e.g. "1242993"
    Returns list of upserted tender IDs.
    """
    if not tender_dicts:
        return []

    rows = [_map_sk_tender(t) for t in tender_dicts]

    stmt = pg_insert(Tender).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["number_anno"],
        set_={
            "name_ru": stmt.excluded.name_ru,
            "total_sum": stmt.excluded.total_sum,
            "customer_name_ru": stmt.excluded.customer_name_ru,
            "status_name_ru": stmt.excluded.status_name_ru,
            "start_date": stmt.excluded.start_date,
            "end_date": stmt.excluded.end_date,
            "lots_data": stmt.excluded.lots_data,
            "raw_data": stmt.excluded.raw_data,
            "source": stmt.excluded.source,
            "region": stmt.excluded.region,
            "spgz_code": stmt.excluded.spgz_code,
            "cached_at": func.now(),
        },
    )
    result = await session.execute(stmt.returning(Tender.id))
    await session.commit()
    return [row[0] for row in result.fetchall()]
```

**_map_tender_dict pattern** (lines 133-156 of analog) — adapt field names to sk.kz schema:
```python
def _map_sk_tender(data: dict) -> dict:
    """Map a zakup.sk.kz filter response item to Tender column values.

    Field mapping (from RESEARCH.md):
      data["id"]                   → number_anno (str)  — sk.kz tender ID
      data["nameRu"]               → name_ru
      data["sumTruNoNds"]          → total_sum           — sum without VAT
      data["acceptanceBeginDateTime"] → start_date
      data["acceptanceEndDateTime"]   → end_date
      data["customer"]["nameRu"]   → customer_name_ru    — nested object
      data["customer"]["bin"]      → customer_bin (raw_data only)
      data["advertStatus"]         → status_name_ru
      lots from GET /lots/{id}     → lots_data           — fetched separately if needed
      data["truHistory"]["code"]   → spgz_code           — TRU code from lots
      data["kato"]["code"]         → region
    """
    lots: list[dict] = data.get("lots") or []  # pre-fetched lots if available
    customer = data.get("customer") or {}

    # Extract TRU code from first lot if available (richer than goszakup)
    tru_history = data.get("truHistory") or {}
    spgz_code: str | None = tru_history.get("code")

    # Extract region from kato
    kato = data.get("kato") or {}
    region: str | None = kato.get("ru")  # human-readable; use code for matching

    return {
        "number_anno": str(data.get("id", "")),
        "name_ru": data.get("nameRu"),
        "name_kz": data.get("nameKk"),
        "total_sum": data.get("sumTruNoNds"),
        "customer_name_ru": customer.get("nameRu"),
        "customer_name_kz": None,
        "status_id": None,                        # sk.kz has no numeric status ID
        "status_name_ru": data.get("advertStatus"),
        "start_date": parse_sk_date(data.get("acceptanceBeginDateTime")),
        "end_date": parse_sk_date(data.get("acceptanceEndDateTime")),
        "publish_date": None,
        "lots_data": lots or None,
        "raw_data": data,
        "source": "sk_kz",
        "region": region,
        "spgz_code": spgz_code,
    }
```

---

### `backend/app/workers/worker_settings.py` (config, modify)

**Analog:** itself (lines 31-83)

**What to add — import line** (after line 32):
```python
from app.workers.tasks.poll_sk_kz_discovery import poll_sk_kz_discovery
```

**What to add — cron_jobs entry** (after line 82, inside `cron_jobs` list):
```python
        cron(
            poll_sk_kz_discovery,
            minute={0, 15, 30, 45},
            unique=True,
        ),
```

Full updated `cron_jobs` list will be:
```python
    cron_jobs = [
        cron(poll_watchlist_tenders,   minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}, unique=True),
        cron(poll_goszakup_discovery,  minute={0, 15, 30, 45}, unique=True),
        cron(poll_sk_kz_discovery,     minute={0, 15, 30, 45}, unique=True),
    ]
```

Note: `functions` list stays unchanged — `run_matching` is source-agnostic and handles both.

---

### `backend/app/services/telegram_service.py` (service, modify)

**Analog:** itself — `send_discovery_notification` function (lines 68-119)

**What to change:** Add `source: str` and `portal_url: str | None` parameters to `send_discovery_notification`. Include source badge and link in message text.

**Extend function signature** (line 68-82 of analog):
```python
async def send_discovery_notification(
    bot_token: str,
    chat_id: int,
    match_id: int,
    tender_name: str | None,
    customer_name: str | None,
    total_sum: Decimal | None,
    deadline: datetime | None,
    region: str | None,
    source: str = "goszakup",          # NEW — "goszakup" or "sk_kz"
    portal_url: str | None = None,     # NEW — direct link to tender on the portal
) -> None:
```

**Extend message text** (adapt lines 99-116 of analog):
```python
    # Source badge
    source_label = "ГОСЗАКУП" if source == "goszakup" else "SK.KZ"

    text = (
        f"[{source_label}] Новый тендер по вашим фильтрам\n\n"
        f"{name_display}\n\n"
        f"Заказчик: {customer_display}\n"
        f"Сумма: {amount_display}\n"
        f"Дедлайн: {deadline_display}\n"
        f"Регион: {region_display}"
    )
    if portal_url:
        text += f"\n\nСсылка: {portal_url}"
```

Portal URL for sk.kz: `https://zakup.sk.kz/eprocsearch/api/external/4dv3rts/{tender_id}`
(or the human-readable UI URL if discoverable from HAR — TBD in plan).

All existing callers of `send_discovery_notification` pass no `source`/`portal_url` — default
`source="goszakup"` keeps them backward-compatible.

---

### `frontend/src/components/discovery/TenderMatchCard.tsx` (component, modify)

**Analog:** itself (lines 1-162)

The "Источник" cell already exists in the details grid (lines 119-128). Currently hardcoded to `"goszakup"`. Change to use `match.source`:

**Current hardcoded pattern** (lines 119-128 of file):
```tsx
        <div>
          <span className="font-medium text-muted-foreground uppercase tracking-wide text-[10px]">
            Источник
          </span>
          <p className="mt-0.5">
            <span className="inline-flex items-center rounded-full border border-gray-200 bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-600">
              goszakup
            </span>
          </p>
        </div>
```

**Replace with dynamic source badge** — add helper function above component:
```tsx
function SourceBadge({ source }: { source: string | undefined }) {
  const label = source === 'sk_kz' ? 'SK.KZ' : 'ГОСЗАКУП'
  const colorClass =
    source === 'sk_kz'
      ? 'border-blue-200 bg-blue-50 text-blue-700'
      : 'border-gray-200 bg-gray-100 text-gray-600'
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium ${colorClass}`}
    >
      {label}
    </span>
  )
}
```

Then replace the hardcoded span with:
```tsx
            <p className="mt-0.5">
              <SourceBadge source={match.source} />
            </p>
```

For sk.kz tenders where `portal_url` is available, optionally wrap in `<a href={match.portal_url} target="_blank" rel="noopener noreferrer">`.

---

### `frontend/src/types/discovery.ts` (utility/types, modify)

**Analog:** itself (lines 14-28)

**Add `source` field to `TenderMatchResponse`** (after `region` on line 27):
```typescript
export interface TenderMatchResponse {
  id: number
  user_id: number
  tender_id: number
  status: TenderMatchStatus
  notified_at: string | null
  decided_at: string | null
  created_at: string
  // Denormalized tender fields (from JOIN in discovery router)
  tender_name_ru: string | null
  customer_name_ru: string | null
  total_sum: string | null
  end_date: string | null
  region: string | null
  source: string | null          // NEW — 'goszakup' | 'sk_kz'
  portal_url: string | null      // NEW — direct link to tender on the source portal
}
```

The discovery router (`backend/app/routers/discovery.py`) must also JOIN `tenders.source`
and include it in the response schema — check that file when writing the plan.

---

### `backend/tests/test_sk_kz_service.py` (test, new)

**Analog:** `backend/tests/test_goszakup_batch.py` (lines 1-173)

**Test file structure pattern** (lines 1-28 of analog):
```python
"""Unit tests for sk_kz_service.fetch_sk_tenders_page.

Covers Phase 8 DISC-02 extension:
  - Single-page fetch returns items filtered by lastModifiedDate
  - No Authorization header is sent (sk.kz filter is public — no auth required)
  - Items older than `since` are excluded (datetime comparison)
  - Empty API response returns []
  - HTTP 500 raises HTTPStatusError (retryable by tenacity)
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
import respx

from app.services.sk_kz_service import fetch_sk_tenders_page

_SINCE = datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)
_RECENT_DATE = "2026-08-05T10:00:00Z"   # after _SINCE
_OLD_DATE    = "2026-07-25T00:00:00Z"   # before _SINCE

_FILTER_URL = "https://zakup.sk.kz/eprocsearch/api/external/4dv3rts/filter"
```

**Mock helper pattern** (lines 31-53 of analog) — adapt for sk.kz array response:
```python
def _make_sk_tender(n: int, modified: str = _RECENT_DATE) -> dict:
    """Generate a minimal sk.kz filter response item for test purposes."""
    return {
        "id": 1000000 + n,
        "number": str(1000000 + n),
        "nameRu": f"Тендер {n}",
        "nameKk": None,
        "tenderType": "OTP",
        "sumTruNoNds": 1000000.0,
        "acceptanceBeginDateTime": "2026-08-06T05:00:00Z",
        "acceptanceEndDateTime": "2026-08-17T05:00:00Z",
        "advertStatus": "PUBLISHED",
        "lastModifiedDate": modified,
    }
```

**respx mock pattern** — sk.kz returns a raw array (not GraphQL envelope):
```python
@pytest.mark.asyncio
@respx.mock
async def test_fetch_page_returns_recent_items():
    items = [_make_sk_tender(i) for i in range(10)]
    respx.post(_FILTER_URL).mock(
        return_value=httpx.Response(200, json=items)   # raw array, not {"data": ...}
    )
    result = await fetch_sk_tenders_page(since=_SINCE)
    assert len(result) == 10
```

**No-auth-header test** (inverse of test_fetch_batch_sends_bearer_token in analog):
```python
@pytest.mark.asyncio
@respx.mock
async def test_fetch_page_sends_no_auth_header():
    """sk.kz filter is public — no Authorization header should be sent."""
    captured: list[str] = []

    def capture(request: httpx.Request) -> httpx.Response:
        captured.append(request.headers.get("Authorization", "NONE"))
        return httpx.Response(200, json=[])

    respx.post(_FILTER_URL).mock(side_effect=capture)
    await fetch_sk_tenders_page(since=_SINCE)

    assert captured[0] == "NONE", f"Should not send auth header, got: {captured[0]!r}"
```

---

### `backend/tests/test_poll_sk_kz_discovery.py` (test, new)

**Analog:** `backend/tests/test_poll_discovery.py` (lines 1-240)

**ctx helper pattern** (lines 31-41 of analog) — copy verbatim:
```python
def _make_ctx(redis_client) -> dict:
    """Build a minimal fake ARQ ctx with fakeredis and a mock session factory."""
    mock_session = AsyncMock()
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return {
        "redis": redis_client,
        "db_session_factory": mock_factory,
    }
```

**fake_redis fixture pattern** (lines 63-69 of analog) — copy verbatim:
```python
@pytest.fixture
async def fake_redis():
    """fakeredis client with enqueue_job mock (ARQ-compatible API)."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    client.enqueue_job = AsyncMock()
    yield client
    await client.aclose()
```

**Patch target for sk.kz** (adapt lines 88-98 of analog):
```python
with patch(
    "app.workers.tasks.poll_sk_kz_discovery.fetch_sk_tenders_page",
    new_callable=AsyncMock,
    return_value=fake_tenders,
):
    ...
with patch(
    "app.workers.tasks.poll_sk_kz_discovery._upsert_tenders",
    new_callable=AsyncMock,
    return_value=[1, 2, 3],
):
    ...
```

**Key difference in test_poll_always_uses_short_lookback** (vs analog test_poll_always_uses_7_day_lookback):
sk.kz uses `DEFAULT_LOOKBACK_HOURS = 24` (not 7 days) because sort by lastModifiedDate is reliable.
```python
async def test_poll_uses_24h_lookback_on_first_run(fake_redis):
    """since is ~24 hours ago on first run (no Redis key)."""
    # ... same pattern as analog test 3, but check timedelta(hours=24) not timedelta(days=7)
    diff = abs((since_used - expected_since).total_seconds())
    assert diff < 10
```

---

## Shared Patterns

### ARQ Context Access
**Source:** `backend/app/workers/tasks/poll_goszakup_discovery.py` (lines 62-83)
**Apply to:** `poll_sk_kz_discovery.py`
```python
redis = ctx["redis"]
# DB: always use ctx["db_session_factory"](), NEVER FastAPI get_db
async with ctx["db_session_factory"]() as session:
    upserted_ids = await _upsert_tenders(session, ...)
```

### PostgreSQL Upsert (ON CONFLICT DO UPDATE)
**Source:** `backend/app/workers/tasks/poll_goszakup_discovery.py` (lines 97-130)
**Apply to:** `poll_sk_kz_discovery.py` `_upsert_tenders`
```python
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import func

stmt = pg_insert(Tender).values(rows)
stmt = stmt.on_conflict_do_update(
    index_elements=["number_anno"],
    set_={..., "cached_at": func.now()},
)
result = await session.execute(stmt.returning(Tender.id))
await session.commit()
return [row[0] for row in result.fetchall()]
```

### tenacity Retry Decorator
**Source:** `backend/app/services/goszakup_service.py` (lines 174-179)
**Apply to:** All fetch functions in `sk_kz_service.py`
```python
@retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
```

### Redis Last-Polled Timestamp
**Source:** `backend/app/workers/tasks/poll_goszakup_discovery.py` (lines 35-36, 78-86)
**Apply to:** `poll_sk_kz_discovery.py`
```python
LAST_POLLED_KEY = "sk_kz:last_polled_at"   # separate namespace from goszakup

# Write ONLY after successful upsert (atomicity invariant)
await redis.set(LAST_POLLED_KEY, datetime.now(tz=timezone.utc).isoformat())
```

### respx + pytest-asyncio Test Pattern
**Source:** `backend/tests/test_goszakup_batch.py` (lines 61-72)
**Apply to:** `test_sk_kz_service.py`
```python
@pytest.mark.asyncio
@respx.mock
async def test_...:
    respx.post(URL).mock(return_value=httpx.Response(200, json=payload))
    result = await fetch_fn(...)
    assert ...
```

### fakeredis + patch Test Pattern
**Source:** `backend/tests/test_poll_discovery.py` (lines 77-108)
**Apply to:** `test_poll_sk_kz_discovery.py`
```python
@pytest.mark.asyncio
async def test_...(fake_redis):
    ctx = _make_ctx(fake_redis)
    with (
        patch("app.workers.tasks.poll_sk_kz_discovery.fetch_sk_tenders_page",
              new_callable=AsyncMock, return_value=...),
        patch("app.workers.tasks.poll_sk_kz_discovery._upsert_tenders",
              new_callable=AsyncMock, return_value=[1, 2, 3]),
    ):
        await poll_sk_kz_discovery(ctx)
    ts_raw = await fake_redis.get(LAST_POLLED_KEY)
    assert ts_raw is not None
```

---

## No Analog Found

All files have close analogs. No files require falling back to RESEARCH.md-only patterns.

---

## Key Deviations from Analog (goszakup → sk.kz)

| Concern | goszakup pattern | sk.kz pattern |
|---|---|---|
| Protocol | GraphQL POST, `{"data": {"TrdBuy": [...]}}` | REST POST, raw JSON array response |
| Auth | `Authorization: Bearer <token>` (from settings) | No auth header — public endpoint |
| Date format | `"YYYY-MM-DD HH:MM:SS"` naive Almaty local → parse + attach UTC+5 | ISO 8601 `"2026-08-17T05:00:00Z"` → `datetime.fromisoformat()` |
| Sort | `id DESC` (newest created, not modified) → always look back 7 days | `lastModifiedDate,desc` → short 24h window is reliable |
| Pagination | Offset not supported — single page per poll | Offset supported (`page=` param) — can walk pages if needed |
| `number_anno` | `data["numberAnno"]` (string like `"1234567-1"`) | `str(data["id"])` (integer ID) |
| `source` column value | `"goszakup"` | `"sk_kz"` |
| `spgz_code` | None (field name unknown from introspection) | `data["truHistory"]["code"]` — confirmed in HAR |
| `region` | None (not in goszakup response) | `data["kato"]["ru"]` — confirmed in HAR |

---

## Metadata

**Analog search scope:** `backend/app/services/`, `backend/app/workers/tasks/`, `backend/tests/`, `frontend/src/components/discovery/`, `frontend/src/types/`
**Files scanned:** 10 source files read in full
**Pattern extraction date:** 2026-08-06
