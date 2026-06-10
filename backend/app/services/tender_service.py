"""
tender_service — cache-aside tender lookup and watchlist management.

Cache strategy:
- tenders table acts as a 30-min write-through cache on number_anno.
- On hit with cached_at < 30 min old: return DB row (no API call).
- On miss or stale: call goszakup_service.fetch_tender_by_number_anno, upsert via pg_insert.
- 404 (API returns None): return None and do NOT insert anything.

Upsert is atomic (ON CONFLICT DO UPDATE on unique number_anno index) — safe under
concurrent requests for the same tender.

Date parsing: goszakup returns "YYYY-MM-DD HH:MM:SS" (no tz suffix, UTC+5 Kazakhstan).
Wave 1 attaches UTC+5 on parse; all DB columns are TIMESTAMPTZ.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.tender import Tender, UserWatchlist
from app.services.goszakup_service import fetch_tender_by_number_anno

CACHE_TTL_MINUTES = 30

# Kazakhstan (Almaty) timezone — UTC+5, used to interpret goszakup naive datetimes.
_ALMATY_TZ = timezone(timedelta(hours=5))


def _parse_gz_date(value: str | None) -> Optional[datetime]:
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


async def get_or_fetch_tender(
    db: AsyncSession, number_anno: str
) -> Optional[Tender]:
    """Return a Tender from the cache or fetch fresh from goszakup (30-min TTL).

    Never caches 404 responses (API returns empty TrdBuy array → returns None).
    Upsert is atomic: concurrent callers converge on the same DB row.
    """
    result = await db.execute(
        select(Tender).where(Tender.number_anno == number_anno)
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        # tz-aware comparison: cached_at is TIMESTAMPTZ stored in DB
        age = datetime.now(tz=timezone.utc) - existing.cached_at
        if age.total_seconds() < CACHE_TTL_MINUTES * 60:
            return existing  # cache hit — no API call

    # Cache miss or stale: hit the API
    data = await fetch_tender_by_number_anno(number_anno)
    if data is None:
        return None  # 404 — do NOT cache

    status = data.get("RefBuyStatus") or {}
    now_utc = datetime.now(tz=timezone.utc)
    values: dict = {
        "number_anno": data.get("numberAnno", number_anno),
        "name_ru": data.get("nameRu"),
        "name_kz": data.get("nameKz"),
        "total_sum": data.get("totalSum"),
        "customer_name_ru": data.get("customerNameRu"),
        "customer_name_kz": data.get("customerNameKz"),
        "status_id": data.get("refBuyStatusId"),
        "status_name_ru": status.get("nameRu"),
        "start_date": _parse_gz_date(data.get("startDate")),
        "end_date": _parse_gz_date(data.get("endDate")),
        "publish_date": _parse_gz_date(data.get("publishDate")),
        "lots_data": data.get("Lots"),
        "raw_data": data,
        "cached_at": now_utc,
    }

    stmt = (
        pg_insert(Tender)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["number_anno"],
            set_={k: v for k, v in values.items() if k != "number_anno"},
        )
        .returning(Tender)
    )
    upsert_result = await db.execute(stmt)
    await db.commit()
    return upsert_result.scalar_one()


async def add_to_watchlist(
    db: AsyncSession, user_id: int, number_anno: str
) -> Optional[UserWatchlist]:
    """Add a tender to a user's watchlist. Idempotent.

    Fetches (or retrieves cached) the tender first.
    Returns None if the tender does not exist in goszakup.
    Returns the UserWatchlist row (existing or newly created).
    """
    tender = await get_or_fetch_tender(db, number_anno)
    if tender is None:
        return None

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
        # Already existed — SELECT the existing entry
        existing = await db.execute(
            select(UserWatchlist).where(
                UserWatchlist.user_id == user_id,
                UserWatchlist.tender_id == tender.id,
            )
        )
        row = existing.scalar_one_or_none()
    return row


async def remove_from_watchlist(
    db: AsyncSession, user_id: int, number_anno: str
) -> bool:
    """Remove a tender from the user's watchlist. IDOR-safe.

    Filters by BOTH user_id (from JWT) and the tender's number_anno so a user
    can only remove their own watchlist entries — never another user's.
    Returns True if a row was deleted, False if not found.
    """
    result = await db.execute(
        select(Tender).where(Tender.number_anno == number_anno)
    )
    tender = result.scalar_one_or_none()
    if tender is None:
        return False

    del_result = await db.execute(
        delete(UserWatchlist).where(
            UserWatchlist.user_id == user_id,
            UserWatchlist.tender_id == tender.id,
        )
    )
    await db.commit()
    return del_result.rowcount > 0


async def list_watchlist(
    db: AsyncSession, user_id: int
) -> list[UserWatchlist]:
    """Return all watched tenders for a user, ordered by added_at desc.

    Uses selectinload to eagerly load the related Tender for each row
    (consistent with Phase 2 selectin pattern — avoids N+1 queries).
    """
    result = await db.execute(
        select(UserWatchlist)
        .options(selectinload(UserWatchlist.tender))
        .where(UserWatchlist.user_id == user_id)
        .order_by(UserWatchlist.added_at.desc())
    )
    return list(result.scalars().all())
