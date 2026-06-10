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

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings

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
