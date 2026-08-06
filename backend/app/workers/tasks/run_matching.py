"""ARQ on-demand task: run_matching.

Called by poll_goszakup_discovery after each successful upsert batch.
Matches new/updated tenders against ALL active user filters, creates
tender_match records, and sends Telegram notifications.

Security:
  ON CONFLICT (user_id, tender_id) DO NOTHING prevents duplicate records
  even when concurrent run_matching jobs overlap (Pitfall 3 in 07-RESEARCH.md).
  The UNIQUE(user_id, tender_id) constraint in migration 0007 is the safety net.

Pitfall 5 (ARQ worker DB session): uses ctx["db_session_factory"],
  NOT FastAPI's get_db dependency. See poll_watchlist.py for the pattern.

D-03 (Telegram depends on Phase 6): send call is guarded by
  `if user.telegram_chat_id is not None` — no notification sent if no chat_id.
  The match record is still created (status stays "matched") even without chat_id.

D-07 (matching is a separate ARQ task): this task is in functions[] (not cron_jobs[])
  in WorkerSettings — it is enqueued on-demand by poll_goszakup_discovery, not
  scheduled independently.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.client_filter import ClientFilter
from app.models.tender import Tender
from app.models.tender_match import TenderMatch
from app.models.user import User
from app.services.matching_service import match_tenders_for_user

logger = logging.getLogger(__name__)


def _portal_url(source: str | None, number_anno: str | None) -> str | None:
    """Compute the public portal URL for a tender based on its source.

    sk.kz URL pattern: /eprocsearch/tender/{number_anno}
    Confirmed from URL structure analysis — verify by navigating to a published sk.kz tender.
    goszakup: no stable public read-only URL — returns None.
    """
    if source == "sk_kz" and number_anno:
        return f"https://zakup.sk.kz/eprocsearch/tender/{number_anno}"
    return None


def _utcnow() -> datetime:
    """Return current UTC time as a NAIVE datetime (no tzinfo).

    PostgreSQL TIMESTAMP WITHOUT TIME ZONE columns require naive datetimes.
    datetime.now(timezone.utc).replace(tzinfo=None) is the recommended approach;
    datetime.utcnow() is deprecated in Python 3.12.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def run_matching(ctx: dict, new_tender_ids: list[int]) -> None:
    """ARQ on-demand task: match new/updated tenders against all active user filters.

    Called by poll_goszakup_discovery after each successful upsert batch.

    Args:
        ctx: ARQ worker context dict (must contain "db_session_factory").
        new_tender_ids: IDs of tenders upserted in the current poll window.

    Behaviour:
        1. Load all ClientFilter rows (one per user, D-10).
        2. For each filter, call match_tenders_for_user to get matching IDs.
        3. For each matching ID, INSERT INTO tender_matches ON CONFLICT DO NOTHING.
           - ON CONFLICT returns None for new_match_id → skip notification (dupe).
        4. If new match + user.telegram_chat_id is set → send_discovery_notification.
           - Failure in step 4 is logged and swallowed (same pattern as poll_watchlist).
    """
    if not new_tender_ids:
        logger.debug("run_matching: empty new_tender_ids, skipping")
        return

    async with ctx["db_session_factory"]() as session:
        # Load all client filters (one per user — D-10)
        result = await session.execute(select(ClientFilter))
        filters = result.scalars().all()

        if not filters:
            logger.debug("run_matching: no active client_filters, skipping")
            return

        logger.info(
            "run_matching: checking %d filter(s) against %d new tender(s)",
            len(filters),
            len(new_tender_ids),
        )

        for cf in filters:
            matching_ids = await match_tenders_for_user(
                session, cf.user_id, cf, new_tender_ids
            )

            for tender_id in matching_ids:
                # Insert with UNIQUE(user_id, tender_id) guard (Pitfall 3).
                # on_conflict_do_nothing returns NO rows when there's a conflict.
                # .returning(TenderMatch.id) captures the new PK only on INSERT.
                stmt = (
                    pg_insert(TenderMatch)
                    .values(
                        user_id=cf.user_id,
                        tender_id=tender_id,
                        status="matched",
                    )
                    .on_conflict_do_nothing(index_elements=["user_id", "tender_id"])
                    .returning(TenderMatch.id)
                )
                insert_result = await session.execute(stmt)
                new_match_id = insert_result.scalar_one_or_none()
                await session.commit()

                if new_match_id is None:
                    # Already matched — skip notification (dedup guard)
                    logger.debug(
                        "run_matching: duplicate match user=%s tender=%s — skipped",
                        cf.user_id,
                        tender_id,
                    )
                    continue

                logger.info(
                    "run_matching: new match id=%s user=%s tender=%s",
                    new_match_id,
                    cf.user_id,
                    tender_id,
                )

                # Send Telegram notification if user has telegram_chat_id (D-03 guard)
                user = await session.get(User, cf.user_id)
                if user and user.telegram_chat_id is not None:
                    tender = await session.get(Tender, tender_id)
                    try:
                        # Lazy import — avoids ImportError when plan 07-03 and 07-04
                        # run in parallel (send_discovery_notification is created by 07-04)
                        from app.config import settings
                        from app.services.telegram_service import (
                            send_discovery_notification,
                        )

                        await send_discovery_notification(
                            bot_token=settings.telegram_bot_token,
                            chat_id=user.telegram_chat_id,
                            match_id=new_match_id,
                            tender_name=tender.name_ru if tender else None,
                            customer_name=tender.customer_name_ru if tender else None,
                            total_sum=tender.total_sum if tender else None,
                            # end_date = submission deadline in goszakup (Pitfall 4)
                            deadline=tender.end_date if tender else None,
                            region=tender.region if tender else None,
                            source=tender.source if tender else "goszakup",
                            portal_url=_portal_url(
                                tender.source if tender else None,
                                tender.number_anno if tender else None,
                            ),
                        )
                        # Transition match status: matched → notified
                        match = await session.get(TenderMatch, new_match_id)
                        if match:
                            match.status = "notified"
                            match.notified_at = _utcnow()
                            await session.commit()
                            logger.info(
                                "run_matching: match %s notified via Telegram",
                                new_match_id,
                            )
                    except Exception as exc:
                        # Telegram failure must NOT block matching (same pattern as poll_watchlist)
                        logger.warning(
                            "run_matching: telegram send failed for match %s: %s",
                            new_match_id,
                            exc,
                        )
