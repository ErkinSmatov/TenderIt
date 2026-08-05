"""ARQ cron job: poll_goszakup_discovery.

Runs every 15 minutes (WorkerSettings cron_jobs, unique=True). Fetches new and
updated tenders from goszakup GraphQL, upserts them to the tenders table, and
enqueues the run_matching ARQ task.

Registration: worker_settings.py (plan 07-03).

Security / invariants:
  - Uses ctx["db_session_factory"] (NEVER FastAPI get_db) — ARQ pitfall #6.
  - Bearer token for goszakup is read by goszakup_service (never logged).
  - DB writes are parameterised via SQLAlchemy pg_insert() — no raw f-string SQL.

Note: goszakup does NOT support 'offset' on TrdBuy (confirmed 2026-07-22).
Single page per poll (limit=50). Cursor pagination via pageInfo.lastId is a
known TODO — sufficient for a 15-min interval in practice.

DISC-02: ARQ worker reads/writes discovery:last_polled_at in Redis.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.tender import Tender
from app.services.goszakup_service import fetch_tenders_batch, parse_gz_date

logger = logging.getLogger(__name__)

# Redis key that stores the ISO-8601 timestamp of the last successful poll.
LAST_POLLED_KEY = "discovery:last_polled_at"

# On the very first run, fetch tenders updated within the last 7 days.
DEFAULT_LOOKBACK_DAYS = 7

# Page size for batch fetching. Matches fetch_tenders_batch default.
_BATCH_LIMIT = 50


async def poll_goszakup_discovery(ctx: dict) -> None:
    """ARQ cron: batch-fetch new/updated tenders from goszakup and upsert to DB.

    Called every 15 min by WorkerSettings.cron_jobs (unique=True prevents overlap).

    Flow:
      1. Compute since = now - DEFAULT_LOOKBACK_DAYS (always 7 days).
      2. Fetch one page of tenders from goszakup (single page — offset not supported).
      3. Upsert each tender to tenders table ON CONFLICT(number_anno) DO UPDATE.
      4. Write last_polled_at to Redis ONLY after successful upsert (for monitoring).
      5. Enqueue run_matching ARQ job with list of upserted tender IDs.

    Note on `since`: goszakup returns TrdBuy sorted by id DESC (newest created first),
    NOT by lastUpdateDate. Using last_polled_at (15-min window) as `since` filters out
    ALL results because the 50 newest tenders were published hours/days before the last
    poll interval. Always use DEFAULT_LOOKBACK_DAYS so recently-published tenders pass
    the client-side date filter every cycle. ON CONFLICT DO UPDATE makes upserts safe.
    """
    redis = ctx["redis"]

    # Step 1: Always look back DEFAULT_LOOKBACK_DAYS — goszakup returns newest by ID,
    # not by lastUpdateDate, so a 15-min window filters out all results.
    since = datetime.now(tz=timezone.utc) - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    logger.info("poll_goszakup_discovery: polling since %s", since.isoformat())

    # Step 2: Fetch tenders updated since `since` (single page — goszakup does not
    # support offset; cursor pagination via pageInfo.lastId is a known TODO).
    all_tender_dicts: list[dict] = await fetch_tenders_batch(since, limit=_BATCH_LIMIT)

    if not all_tender_dicts:
        logger.info(
            "poll_goszakup_discovery: no new/updated tenders since %s", since.isoformat()
        )
        # Still advance the timestamp so the next run only looks from now.
        await redis.set(LAST_POLLED_KEY, datetime.now(tz=timezone.utc).isoformat())
        return

    # Step 3: Upsert each tender to DB
    async with ctx["db_session_factory"]() as session:
        upserted_ids = await _upsert_tenders(session, all_tender_dicts)

    # Step 4: Write last_polled_at to Redis ONLY after successful upsert (atomicity)
    await redis.set(LAST_POLLED_KEY, datetime.now(tz=timezone.utc).isoformat())
    logger.info(
        "poll_goszakup_discovery: upserted %d tenders, enqueuing run_matching",
        len(upserted_ids),
    )

    # Step 5: Enqueue run_matching with list of upserted tender IDs
    if upserted_ids:
        await redis.enqueue_job("run_matching", upserted_ids)


async def _upsert_tenders(session, tender_dicts: list[dict]) -> list[int]:
    """Upsert a list of goszakup TrdBuy dicts to the tenders table.

    Uses pg_insert().on_conflict_do_update() — race-condition safe.
    Returns list of upserted tender IDs.
    """
    if not tender_dicts:
        return []

    rows = [_map_tender_dict(t) for t in tender_dicts]

    stmt = pg_insert(Tender).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["number_anno"],
        set_={
            "name_ru": stmt.excluded.name_ru,
            "name_kz": stmt.excluded.name_kz,
            "total_sum": stmt.excluded.total_sum,
            "customer_name_ru": stmt.excluded.customer_name_ru,
            "customer_name_kz": stmt.excluded.customer_name_kz,
            "status_id": stmt.excluded.status_id,
            "start_date": stmt.excluded.start_date,
            "end_date": stmt.excluded.end_date,
            "publish_date": stmt.excluded.publish_date,
            "lots_data": stmt.excluded.lots_data,
            "raw_data": stmt.excluded.raw_data,
            "source": stmt.excluded.source,
            "spgz_code": stmt.excluded.spgz_code,
            "cached_at": func.now(),
        },
    )
    result = await session.execute(stmt.returning(Tender.id))
    await session.commit()
    return [row[0] for row in result.fetchall()]


def _map_tender_dict(data: dict) -> dict:
    """Map a goszakup TrdBuy dict to a dict of Tender column values."""
    lots: list[dict] = data.get("Lots") or []
    # refEnstruCode confirmed invalid on 2026-07-23 — field does not exist on Lots type.
    # spgz_code stays None until correct field name is found via schema introspection.
    spgz_code: str | None = None

    return {
        "number_anno": data.get("numberAnno", ""),
        "name_ru": data.get("nameRu"),
        "name_kz": data.get("nameKz"),
        "total_sum": data.get("totalSum"),
        "customer_name_ru": data.get("customerNameRu"),
        "customer_name_kz": data.get("customerNameKz"),
        "status_id": data.get("refBuyStatusId"),
        "start_date": parse_gz_date(data.get("startDate")),
        "end_date": parse_gz_date(data.get("endDate")),
        "publish_date": parse_gz_date(data.get("publishDate")),
        "lots_data": lots or None,
        "raw_data": data,
        "source": "goszakup",
        "region": None,
        "spgz_code": spgz_code,
    }
