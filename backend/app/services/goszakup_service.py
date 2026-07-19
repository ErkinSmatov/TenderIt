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
from datetime import datetime

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

# Batch query for discovery polling. Fetches tenders without a server-side date
# filter (see SPIKE-BATCH comment above for rationale). Pagination stops
# client-side in fetch_tenders_batch when lastUpdateDate < since.
#
# T-07-04: asyncio.sleep(0.5) between paginated calls is applied in the CALLER
# (poll_goszakup_discovery.py), NOT inside this function. This function fetches
# exactly one page per call.
BATCH_QUERY = """
query TendersBatch($limit: Int!, $offset: Int!) {
  TrdBuy(limit: $limit, offset: $offset) {
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
      amount
      refEnstruCode
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
    offset: int = 0,
) -> list[dict]:
    """Fetch one page of tenders updated at or after `since` from goszakup GraphQL.

    Returns a filtered list of TrdBuy dicts for the requested page — only those
    whose lastUpdateDate >= since (client-side filter; see SPIKE-BATCH comment).
    Returns an empty list when there are no items at the given offset.

    Pagination is the responsibility of the CALLER (poll_goszakup_discovery.py):
      - Caller increments `offset` by `limit` and repeats until result is empty
        or len(result) < limit.
      # T-07-04: 0.5s inter-page delay to avoid hammering goszakup
      - asyncio.sleep(0.5) must be placed between calls in the caller, NOT here.

    Token is read from settings — never hardcoded (security invariant).
    """
    # Format since as ISO 8601 string for client-side date comparison.
    since_str = since.isoformat()

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            GRAPHQL_URL,
            json={
                "query": BATCH_QUERY,
                "variables": {"limit": limit, "offset": offset},
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

    if not items:
        return []

    # SPIKE-BATCH: Client-side stop condition — filter out items older than `since`.
    # Items with missing lastUpdateDate are included (err on side of inclusion).
    filtered = [item for item in items if _item_updated_since(item, since_str)]
    logger.debug(
        "fetch_tenders_batch: offset=%d raw=%d filtered=%d (since=%s)",
        offset,
        len(items),
        len(filtered),
        since_str,
    )
    return filtered


def _item_updated_since(item: dict, since_str: str) -> bool:
    """Return True if item.lastUpdateDate >= since_str (lexicographic ISO comparison).

    goszakup returns lastUpdateDate as an ISO 8601 string (e.g. '2026-07-19T12:00:00.000Z').
    Lexicographic string comparison is correct for ISO 8601 dates with consistent
    formatting (same timezone offset / both UTC).

    Returns True (include item) if lastUpdateDate is missing or None — err on
    the side of inclusion to avoid silently dropping tenders with missing dates.
    """
    last_update = item.get("lastUpdateDate")
    if not last_update:
        return True  # include items with missing lastUpdateDate
    return last_update >= since_str
