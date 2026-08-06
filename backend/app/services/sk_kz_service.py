"""REST client for zakup.sk.kz public filter API.

Captured from HAR 2026-08-06. No authentication is required for the
/eprocsearch/api/external/4dv3rts/filter endpoint — it is intentionally
public (/api/external/ path prefix).

Key differences from goszakup_service.py:
  - Response is a raw JSON array, NOT a GraphQL envelope {"data": {"TrdBuy": [...]}}
  - No auth header required — public endpoint (no Bearer token)
  - Dates are ISO 8601 with explicit TZ ("2026-08-17T05:00:00Z") — no manual
    timezone attachment needed (unlike goszakup which returns naive Almaty strings)
  - Supports sort=lastModifiedDate,desc — incremental polling is reliable
"""

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

logger = logging.getLogger(__name__)

# All external endpoints share this prefix (confirmed from HAR 2026-08-06)
_SK_BASE = "https://zakup.sk.kz/eprocsearch/api/external/4dv3rts"

# POST body defaults for the filter endpoint
_DEFAULT_ADVERT_STATUS = "PUBLISHED"
_DEFAULT_LOT_STATUS = "PUBLISHED"

# Page size for batch polling — matches goszakup convention
_PAGE_SIZE = 50


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


def parse_sk_date(value: str | None) -> datetime | None:
    """Parse ISO 8601 date from sk.kz (e.g. '2026-08-17T05:00:00Z').

    sk.kz returns TZ-aware ISO strings — no manual timezone attachment needed
    (unlike goszakup which returns naive Almaty-local strings that require
    attaching UTC+5 explicitly).
    Returns None on failure — never raises.
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _item_updated_since(item: dict, since: datetime) -> bool:
    """Return True if item['lastModifiedDate'] >= since.

    If lastModifiedDate is missing or unparseable, returns True to err
    on the side of inclusion (do not silently drop a tender).
    """
    dt = parse_sk_date(item.get("lastModifiedDate"))
    if dt is None:
        return True  # err on side of inclusion
    return dt >= since


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

    Returns tenders whose lastModifiedDate >= since (early-stop is possible because
    sk.kz sorts by lastModifiedDate desc — unlike goszakup which sorts by id DESC and
    requires a 7-day lookback window regardless of poll interval).

    No auth header is sent — this endpoint is public (confirmed from HAR 2026-08-06).
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

    # Response is a raw JSON array — NOT wrapped in {"data": ...} like goszakup GraphQL.
    items = response.json()

    if not isinstance(items, list):
        logger.error(
            "sk.kz filter returned unexpected type %s (expected list): %r",
            type(items).__name__,
            str(items)[:200],
        )
        return []

    # Filter by lastModifiedDate client-side.
    # Items are sorted by lastModifiedDate desc; filter keeps only items >= since.
    return [item for item in items if _item_updated_since(item, since)]


def map_sk_tender(data: dict) -> dict:
    """Map a zakup.sk.kz filter response item to Tender column values.

    Field mapping (from 08-RESEARCH.md and 08-PATTERNS.md):
      data["id"]                      → number_anno (str) — sk.kz integer tender ID
      data["nameRu"]                  → name_ru
      data["nameKk"]                  → name_kz
      data["sumTruNoNds"]             → total_sum (sum without VAT)
      data["advertStatus"]            → status_name_ru (e.g. "PUBLISHED")
      data["acceptanceBeginDateTime"] → start_date (parse_sk_date)
      data["acceptanceEndDateTime"]   → end_date (parse_sk_date)
      data.get("customer")["nameRu"]  → customer_name_ru (nested object)
      data.get("kato")["ru"]          → region (human-readable city/region name)
      data.get("truHistory")["code"]  → spgz_code (TRU/СПГЗ code from lots)
      always: source = "sk_kz"        — NEVER "goszakup"
      always: status_id = None        — sk.kz has no numeric status ID

    Known limitation: region (kato.ru) and spgz_code (truHistory.code) are only
    guaranteed on lot-level detail endpoint responses (GET /eprocsearch/api/external/
    4dv3rts/lots/{tender_id}). The filter endpoint may omit these nested objects for
    some tenders. Values are mapped to None when absent — matching_service handles
    None gracefully (NULL in DB, filter simply won't match on these fields).
    """
    customer = data.get("customer") or {}
    tru_history = data.get("truHistory") or {}
    kato = data.get("kato") or {}
    lots = data.get("lots") or []

    return {
        "number_anno": str(data.get("id", "")),
        "name_ru": data.get("nameRu"),
        "name_kz": data.get("nameKk"),
        "total_sum": data.get("sumTruNoNds"),
        "customer_name_ru": customer.get("nameRu"),
        "customer_name_kz": None,
        "status_id": None,                          # sk.kz has no numeric status ID
        "status_name_ru": data.get("advertStatus"),
        "start_date": parse_sk_date(data.get("acceptanceBeginDateTime")),
        "end_date": parse_sk_date(data.get("acceptanceEndDateTime")),
        "publish_date": None,
        "lots_data": lots or None,
        "raw_data": data,
        "source": "sk_kz",                          # ALWAYS — never "goszakup"
        "region": kato.get("ru"),                   # human-readable KATO name, e.g. "г.Астана"
        "spgz_code": tru_history.get("code"),       # TRU code, e.g. "711211.000.000001"
    }
