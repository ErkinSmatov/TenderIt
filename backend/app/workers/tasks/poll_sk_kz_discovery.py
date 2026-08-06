"""ARQ cron job: poll_sk_kz_discovery.

Runs every 15 minutes (WorkerSettings cron_jobs, unique=True). Fetches new and
updated tenders from zakup.sk.kz filter API, upserts them to the tenders table
with source='sk_kz', and enqueues the run_matching ARQ task.

Registration: worker_settings.py — add to cron_jobs list (plan 08-03).

Security / invariants:
  - Uses ctx["db_session_factory"] (NEVER FastAPI dependency injection) — ARQ pitfall #6.
  - No auth token required for sk.kz filter endpoint (public API).
  - DB writes are parameterised via SQLAlchemy pg_insert() — no raw f-string SQL.

Polling strategy (from 08-RESEARCH.md):
  sk.kz supports sort=lastModifiedDate,desc — incremental polling is reliable.
  Store sk_kz:last_polled_at in Redis to track the window. On first run,
  look back DEFAULT_LOOKBACK_HOURS (24h). Unlike goszakup which needs 7 days
  because it sorts by id DESC, sk.kz sorts by lastModifiedDate so a short
  window works correctly without returning stale duplicates every poll.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.tender import Tender
from app.services.sk_kz_service import fetch_sk_tenders_page, parse_sk_date, _map_sk_tender

logger = logging.getLogger(__name__)

# Redis key — separate namespace from goszakup ("discovery:last_polled_at")
LAST_POLLED_KEY = "sk_kz:last_polled_at"

# First run: look back 24 hours. sk.kz sorts by lastModifiedDate so a short
# window works correctly — no need for the 7-day goszakup fallback.
DEFAULT_LOOKBACK_HOURS = 24

# Page size for batch polling — matches sk_kz_service default
_PAGE_SIZE = 50


async def poll_sk_kz_discovery(ctx: dict) -> None:
    """ARQ cron: batch-fetch new/updated tenders from zakup.sk.kz and upsert to DB.

    Called every 15 min by WorkerSettings.cron_jobs (unique=True prevents overlap).

    Flow:
      1. Read sk_kz:last_polled_at from Redis (or use DEFAULT_LOOKBACK_HOURS on first run).
      2. Fetch page 0 from sk.kz filter API; early-stop when items older than since.
      3. Upsert each tender with source='sk_kz' via pg_insert ON CONFLICT(number_anno).
      4. Write sk_kz:last_polled_at to Redis ONLY after successful upsert (atomicity invariant).
      5. Enqueue run_matching ARQ job with list of upserted tender IDs.
    """
    redis = ctx["redis"]

    # Step 1: Compute since from Redis or use 24h lookback on first run
    raw_ts = await redis.get(LAST_POLLED_KEY)
    if raw_ts:
        since = datetime.fromisoformat(raw_ts)
    else:
        since = datetime.now(tz=timezone.utc) - timedelta(hours=DEFAULT_LOOKBACK_HOURS)
    logger.info("poll_sk_kz_discovery: polling since %s", since.isoformat())

    # Step 2: Fetch (single page — sufficient for 15-min interval with 24h lookback;
    # sk.kz sorts by lastModifiedDate desc so <50 new tenders is realistic)
    all_tender_dicts = await fetch_sk_tenders_page(since, page=0, size=_PAGE_SIZE)

    # Step 3: Early exit if no results
    if not all_tender_dicts:
        logger.info(
            "poll_sk_kz_discovery: no new/updated tenders since %s", since.isoformat()
        )
        # Still advance the timestamp so the next run only looks from now
        await redis.set(LAST_POLLED_KEY, datetime.now(tz=timezone.utc).isoformat())
        return

    # Step 4: Upsert inside the async context manager
    async with ctx["db_session_factory"]() as session:
        upserted_ids = await _upsert_tenders(session, all_tender_dicts)

    # Step 5: Write last_polled_at ONLY after successful upsert (atomicity invariant).
    # If _upsert_tenders raises, Redis stays at the old timestamp — next poll re-fetches
    # the same window and retries the upsert (ON CONFLICT DO UPDATE is idempotent).
    await redis.set(LAST_POLLED_KEY, datetime.now(tz=timezone.utc).isoformat())
    logger.info("poll_sk_kz_discovery: upserted %d tenders", len(upserted_ids))

    # Step 6: Enqueue matching for all newly upserted tenders
    if upserted_ids:
        await redis.enqueue_job("run_matching", upserted_ids)


async def _upsert_tenders(session, tender_dicts: list[dict]) -> list[int]:
    """Upsert sk.kz tenders to the tenders table.

    Uses pg_insert().on_conflict_do_update() — race-condition safe.
    number_anno for sk.kz: str(item["id"]) — e.g. "1242993" (integer ID cast to string).
    Returns list of upserted tender IDs (internal DB primary keys).
    """
    if not tender_dicts:
        return []

    rows = [_map_sk_tender(t) for t in tender_dicts]

    stmt = pg_insert(Tender).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["number_anno"],
        set_={
            "name_ru": stmt.excluded.name_ru,
            "name_kz": stmt.excluded.name_kz,
            "total_sum": stmt.excluded.total_sum,
            "customer_name_ru": stmt.excluded.customer_name_ru,
            "customer_name_kz": stmt.excluded.customer_name_kz,
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
