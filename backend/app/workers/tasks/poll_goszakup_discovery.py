"""ARQ cron job: poll_goszakup_discovery.

Runs every 15 minutes (WorkerSettings cron_jobs, unique=True). Fetches new and
updated tenders from goszakup GraphQL in paginated batches, upserts them to the
tenders table, and enqueues the run_matching ARQ task.

Registration: worker_settings.py (plan 07-03 — MUST import run_matching.py at
the same time, so registration is deferred to avoid a partial import cycle).

Security / invariants:
  - Uses ctx["db_session_factory"] (NEVER FastAPI get_db) — ARQ pitfall #6.
  - Bearer token for goszakup is read by goszakup_service (never logged).
  - T-07-04: asyncio.sleep(0.5) between paginated batch calls prevents goszakup
    rate-limit.
  - DB writes are parameterised via SQLAlchemy pg_insert() — no raw f-string SQL
    (T-07-ext-01).

DISC-02: ARQ worker reads/writes discovery:last_polled_at in Redis.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.tender import Tender
from app.services.goszakup_service import fetch_tenders_batch

logger = logging.getLogger(__name__)

# Redis key that stores the ISO-8601 timestamp of the last successful poll.
LAST_POLLED_KEY = "discovery:last_polled_at"

# On the very first run, fetch tenders updated within the last 7 days.
DEFAULT_LOOKBACK_DAYS = 7

# Page size for batch fetching. Matches fetch_tenders_batch default.
_BATCH_LIMIT = 50

# Kazakhstan (Almaty) timezone — UTC+5, used to interpret goszakup naive datetimes.
_ALMATY_TZ = timezone(timedelta(hours=5))


def _parse_gz_date(value: str | None) -> datetime | None:
    """Parse a goszakup date string into a tz-aware datetime.

    Format confirmed in SPIKE-01: "YYYY-MM-DD HH:MM:SS" (no tz suffix).
    Attaches UTC+5 (Almaty) timezone.
    Returns None on any parse failure — never raises.
    """
    if not value:
        return None
    try:
        dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        return dt.replace(tzinfo=_ALMATY_TZ)
    except (ValueError, TypeError):
        return None


async def poll_goszakup_discovery(ctx: dict) -> None:
    """ARQ cron: batch-fetch new/updated tenders from goszakup and upsert to DB.

    Called every 15 min by WorkerSettings.cron_jobs (unique=True prevents overlap).

    Flow:
      1. Read last_polled_at from Redis (default: 7 days ago on first run).
      2. Paginate fetch_tenders_batch until response < _BATCH_LIMIT.
         T-07-04: asyncio.sleep(0.5) between paginated calls.
      3. Upsert each tender to tenders table ON CONFLICT(number_anno) DO UPDATE.
      4. Write last_polled_at to Redis ONLY after successful upsert.
      5. Enqueue run_matching ARQ job with list of upserted tender IDs.
    """
    redis = ctx["redis"]

    # Step 1: Read last_polled_at from Redis (default to 7 days ago on first run)
    ts = await redis.get(LAST_POLLED_KEY)
    if ts:
        # Redis may return bytes or str depending on decode_responses setting
        ts_str = ts.decode() if isinstance(ts, bytes) else ts
        since = datetime.fromisoformat(ts_str)
    else:
        since = datetime.now(tz=timezone.utc) - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    logger.info("poll_goszakup_discovery: polling since %s", since.isoformat())

    # Step 2: Paginated batch fetch with T-07-04 inter-page delay
    all_tender_dicts: list[dict] = []
    offset = 0
    while True:
        batch = await fetch_tenders_batch(since, limit=_BATCH_LIMIT, offset=offset)
        if not batch:
            break
        all_tender_dicts.extend(batch)
        if len(batch) < _BATCH_LIMIT:
            break
        offset += _BATCH_LIMIT
        # T-07-04: conservative rate — goszakup has no public SLA
        await asyncio.sleep(0.5)  # T-07-04: 0.5s inter-page delay to avoid hammering goszakup

    if not all_tender_dicts:
        logger.info(
            "poll_goszakup_discovery: no new/updated tenders since %s", since.isoformat()
        )
        # Still advance the timestamp so the next run only looks from now.
        await redis.set(LAST_POLLED_KEY, datetime.now(tz=timezone.utc).isoformat())
        return

    # Step 3: Upsert each tender batch to DB
    # Note: source, region, spgz_code columns are added by migration 0005 (plan 07-01).
    # This code runs AFTER the migration is applied.
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

    Uses pg_insert().on_conflict_do_update() — race-condition safe and avoids
    duplicate rows on concurrent poll runs (T-07-ext-01: parameterized SQL only).

    Columns source, region, spgz_code are from migration 0005 (plan 07-01).
    region is always NULL (goszakup API does not expose a region field in TrdBuy).

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
            # New columns from migration 0005:
            "source": stmt.excluded.source,
            "spgz_code": stmt.excluded.spgz_code,
            # region always NULL from goszakup — set only on first insert
            # cached_at always refreshed on each upsert
            "cached_at": func.now(),
        },
    )
    result = await session.execute(stmt.returning(Tender.id))
    await session.commit()
    return [row[0] for row in result.fetchall()]


def _map_tender_dict(data: dict) -> dict:
    """Map a goszakup TrdBuy dict to a dict of Tender column values.

    Handles date parsing (goszakup format: "YYYY-MM-DD HH:MM:SS", UTC+5 Almaty).
    Extracts СПГЗ code from Lots[0].refEnstruCode if present.
    # end_date = submission deadline in goszakup (called deadline_at in Phase 7 spec)
    """
    lots: list[dict] = data.get("Lots") or []
    # SPIKE-BATCH: СПГЗ field = refEnstruCode (ASSUMED — verify via introspection)
    spgz_code: str | None = None
    if lots:
        spgz_code = lots[0].get("refEnstruCode")

    return {
        "number_anno": data.get("numberAnno", ""),
        "name_ru": data.get("nameRu"),
        "name_kz": data.get("nameKz"),
        "total_sum": data.get("totalSum"),
        "customer_name_ru": data.get("customerNameRu"),
        "customer_name_kz": data.get("customerNameKz"),
        "status_id": data.get("refBuyStatusId"),
        "start_date": _parse_gz_date(data.get("startDate")),
        "end_date": _parse_gz_date(data.get("endDate")),
        "publish_date": _parse_gz_date(data.get("publishDate")),
        "lots_data": lots or None,
        "raw_data": data,
        # New columns from migration 0005 (plan 07-01):
        "source": "goszakup",  # D-01: only goszakup source in v1
        "region": None,  # goszakup TrdBuy does not expose region — stays NULL
        "spgz_code": spgz_code,
    }
