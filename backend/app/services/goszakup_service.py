"""
goszakup_service — goszakup.gov.kz Unified Services GraphQL client.

Security invariant (CLAUDE.md):
- The Bearer token is NEVER hardcoded.
- It is read exclusively from settings.goszakup_api_token (env: GOSZAKUP_API_TOKEN).
- This module NEVER logs or prints the token value.

Retry policy: 5xx + network errors only (never 4xx — don't retry 401/403/404).
Max attempts: 3, exponential back-off 1-10s.

SPIKE-01 findings (2026-06-10):
- Endpoint confirmed: https://ows.goszakup.gov.kz/v3/graphql
- TrdBuy query with nested Lots can take ~70s on the live API;
  production timeout set to 20s (service-to-service, no spike overhead).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings

logger = logging.getLogger(__name__)

GRAPHQL_URL = "https://ows.goszakup.gov.kz/v3/graphql"

# Kazakhstan (Almaty) timezone — UTC+5, used to parse goszakup naive datetimes.
_ALMATY_TZ = timezone(timedelta(hours=5))


def parse_gz_date(value: str | None) -> datetime | None:
    """Parse a goszakup date string ("YYYY-MM-DD HH:MM:SS") into a tz-aware datetime.

    Attaches UTC+5 (Almaty) timezone — goszakup returns naive local times.
    Returns None on any parse failure — never raises.
    """
    if not value:
        return None
    try:
        dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=_ALMATY_TZ)
    except (ValueError, TypeError):
        return None

# Full TrdBuy query for tender lookup by numberAnno.
# Includes nested RefBuyStatus and Lots for a one-shot fetch.
# Confirmed working in SPIKE-01 (2026-06-10).
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
      count
      amount
      refLotStatusId
    }
  }
}
"""

# SPIKE-BATCH: GraphQL introspection findings (07-02, 2026-07-19)
#
# Introspection was ATTEMPTED via STEP 1 of 07-02 Task 1 but the live API
# (https://ows.goszakup.gov.kz/v3/graphql) was unreachable from the execution
# environment (worktree/CI network isolation). Results are ASSUMED per research:
#
#   lastUpdateDate filter operator:
#     ASSUMED: goszakup TrdBuyFilter may NOT expose a gte/range operator for
#     lastUpdateDate (the existing numberAnno filter uses simple string equality).
#     Chosen approach (safe fallback): no server-side date filter; paginate all
#     tenders and stop in-code when item.lastUpdateDate < since.
#     This approach is correct regardless of filter support.
#     ACTION: re-run introspection with a live API connection to confirm whether
#     `filter: { lastUpdateDate: {gte: $since} }` is supported; if yes, switch
#     BATCH_QUERY to use the server-side filter for efficiency.
#
#   СПГЗ code field name in Lots:
#     ASSUMED: refEnstruCode (confidence: LOW — not verified against live schema)
#     The migration adds spgz_code as nullable so the app works correctly even
#     if this field returns null (СПГЗ filter simply won't match anything).
#     ACTION: run `query { __type(name: "Lot") { fields { name } } }` and update
#     this constant + the BATCH_QUERY below once the correct field name is known.

# SPIKE-BATCH: СПГЗ field = refEnstruCode (ASSUMED — verify via introspection)
_SPGZ_LOT_FIELD = "refEnstruCode"

# Batch query for discovery polling.
#
# Confirmed 2026-07-22 against live API: goszakup does NOT support 'offset' on TrdBuy
# ("Unknown argument offset"). Results are sorted by id DESC (newest first).
# Cursor pagination via lastId (returned in extensions.pageInfo) is not yet
# implemented — single page per poll covers all practical cases for a 15-min interval.
BATCH_QUERY = """
query TendersBatch($limit: Int!) {
  TrdBuy(limit: $limit) {
    id
    numberAnno
    nameRu
    nameKz
    totalSum
    customerBin
    customerNameRu
    customerNameKz
    refBuyStatusId
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
      count
      amount
    }
  }
}
"""

# refBuyStatusId value for "Опубликовано (прием заявок)" / PublishedOrderTaking.
# Confirmed in SPIKE-01 findings (2026-06-10). Used by Phase 5 ARQ polling.
OPEN_FOR_APPLICATIONS_STATUS_ID = 220


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


@retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def fetch_tender_by_number_anno(number_anno: str) -> dict | None:
    """Fetch a single tender by its numberAnno (e.g. '17163708-1') from goszakup GraphQL.

    Returns the TrdBuy dict on success, None if not found (empty TrdBuy array).
    Raises httpx.HTTPStatusError on non-200 responses (after retries on 5xx).

    Uses a short-lived per-call AsyncClient (NOT a singleton) to avoid
    event-loop lifetime issues in async contexts.
    Token is read from settings — never hardcoded.
    """
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            GRAPHQL_URL,
            json={"query": TENDER_QUERY, "variables": {"numberAnno": number_anno}},
            headers={
                "Authorization": f"Bearer {settings.goszakup_api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        response.raise_for_status()

    body = response.json()
    items = body.get("data", {}).get("TrdBuy", [])
    return items[0] if items else None


@retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def fetch_tenders_batch(
    since: datetime,
    limit: int = 50,
) -> list[dict]:
    """Fetch one page of recent tenders from goszakup GraphQL.

    Returns TrdBuy dicts whose lastUpdateDate >= since (client-side filter).
    Results are sorted by id DESC (newest first) — confirmed 2026-07-22.

    goszakup does NOT support 'offset' (confirmed 2026-07-22: "Unknown argument offset").
    Cursor pagination via pageInfo.lastId is not yet implemented; single page per call
    covers all practical cases for a 15-minute polling interval.

    Token is read from settings — never hardcoded (security invariant).
    """
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            GRAPHQL_URL,
            json={
                "query": BATCH_QUERY,
                "variables": {"limit": limit},
            },
            headers={
                "Authorization": f"Bearer {settings.goszakup_api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        response.raise_for_status()

    body = response.json()
    items: list[dict] = body.get("data", {}).get("TrdBuy", [])

    page_info = body.get("extensions", {}).get("pageInfo", {})
    if page_info.get("hasNextPage"):
        logger.warning(
            "fetch_tenders_batch: hasNextPage=True (lastId=%s) — cursor pagination not "
            "yet implemented; tenders beyond the first %d may be missed this cycle",
            page_info.get("lastId"),
            limit,
        )

    if not items:
        return []

    filtered = [item for item in items if _item_updated_since(item, since)]
    logger.debug(
        "fetch_tenders_batch: raw=%d filtered=%d (since=%s)",
        len(items),
        len(filtered),
        since.isoformat(),
    )
    return filtered


def _item_updated_since(item: dict, since: datetime) -> bool:
    """Return True if item.lastUpdateDate is at or after `since`.

    goszakup returns lastUpdateDate as "YYYY-MM-DD HH:MM:SS" (Almaty UTC+5, no tz suffix).
    Uses _parse_gz_date for proper timezone-aware comparison — avoids the broken
    lexicographic comparison between space-separated goszakup dates ("2026-07-22 19:34:49")
    and T-separated ISO datetimes ("2026-07-22T14:30:00+00:00") where ASCII space (32)
    < T (84) causes all same-day tenders to be incorrectly excluded.

    Returns True (include) when lastUpdateDate is missing — err on side of inclusion.
    """
    last_update_str = item.get("lastUpdateDate")
    if not last_update_str:
        return True
    last_update = parse_gz_date(last_update_str)
    if last_update is None:
        return True
    return last_update >= since
