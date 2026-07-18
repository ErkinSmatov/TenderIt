"""ARQ cron job: poll_watchlist_tenders.

Runs every 5 minutes (WorkerSettings cron_jobs). Detects when a watched tender
transitions to status_id 220 (OPEN_FOR_APPLICATIONS_STATUS_ID) and triggers:
  1. Sets confirm:{app_id}=pending (900s TTL) in Redis.
  2. Sends Telegram Да/Нет notification if user.telegram_chat_id is set.
  3. Transitions Application status: waiting → submitting.
  4. Enqueues auto_submit_application with _defer_by=15min + stable _job_id.

Security / invariants:
  - Uses ctx["db_session_factory"] (never FastAPI get_db) — ARQ pitfall #6.
  - session/csrf values are NEVER logged (T-05-03).
  - notification_on=False in UserWatchlist suppresses the Telegram message but
    does NOT suppress the fallback submit (auto-submission still happens).
  - No telegram_chat_id → no crash, submit still enqueued (plan requirement).
"""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select

from app.models.tender import Tender, UserWatchlist
from app.models.user import User
from app.services.application_service import list_waiting_applications, mark_submitting
from app.services.goszakup_service import (
    OPEN_FOR_APPLICATIONS_STATUS_ID,
    fetch_tender_by_number_anno,
)
from app.services.redis_service import set_confirm_pending
from app.services.telegram_service import send_tender_notification

logger = logging.getLogger(__name__)


async def poll_watchlist_tenders(ctx: dict) -> None:
    """ARQ cron: check all waiting applications for tender status 220.

    Called every 5 minutes by WorkerSettings.cron_jobs (unique=True prevents
    concurrent runs on multiple workers).
    """
    redis = ctx["redis"]

    async with ctx["db_session_factory"]() as session:
        waiting_apps = await list_waiting_applications(session)

        if not waiting_apps:
            logger.debug("poll_watchlist: no waiting applications, skipping")
            return

        logger.info("poll_watchlist: checking %d waiting application(s)", len(waiting_apps))

        for app in waiting_apps:
            await _process_application(ctx, session, redis, app)


async def _process_application(ctx, session, redis, app) -> None:
    """Check a single waiting application and trigger submit if tender is open."""
    # Load tender from DB to get number_anno
    tender = await session.get(Tender, app.tender_id)
    if tender is None:
        logger.warning(
            "poll_watchlist: tender id=%s not found for app id=%s — skipping",
            app.tender_id,
            app.id,
        )
        return

    # Load user from DB to get telegram_chat_id
    user = await session.get(User, app.user_id)

    # Fetch live tender status from goszakup Unified Services GraphQL API
    try:
        tender_data = await fetch_tender_by_number_anno(tender.number_anno)
    except Exception as exc:
        logger.warning(
            "poll_watchlist: failed to fetch tender %s for app %s: %s",
            tender.number_anno,
            app.id,
            exc,
        )
        return

    if tender_data is None:
        logger.debug(
            "poll_watchlist: tender %s not found in goszakup API", tender.number_anno
        )
        return

    live_status_id = tender_data.get("refBuyStatusId")
    if live_status_id != OPEN_FOR_APPLICATIONS_STATUS_ID:
        logger.debug(
            "poll_watchlist: tender %s status=%s (not 220), skipping app %s",
            tender.number_anno,
            live_status_id,
            app.id,
        )
        return

    # Tender is now open for applications (status 220).
    logger.info(
        "poll_watchlist: tender %s status=220, triggering auto-submit for app %s",
        tender.number_anno,
        app.id,
    )

    # 1. Set confirm:{app_id}=pending (900s TTL — D-05-06)
    await set_confirm_pending(redis, app.id)

    # 2. Send Telegram notification if user has a chat_id and notification_on is True
    if user and user.telegram_chat_id:
        should_notify = await _should_send_notification(session, app.user_id, app.tender_id)
        if should_notify:
            try:
                from app.config import settings

                await send_tender_notification(
                    bot_token=settings.telegram_bot_token,
                    chat_id=user.telegram_chat_id,
                    number_anno=tender.number_anno,
                    application_id=app.id,
                )
            except Exception as exc:
                # Telegram failure must NOT block the fallback submit (D-05-06)
                logger.warning(
                    "poll_watchlist: telegram notification failed for app %s: %s",
                    app.id,
                    exc,
                )

    # 3. Transition waiting → submitting
    await mark_submitting(session, app)

    # 4. Enqueue 15-min fallback submit (T-05-32: stable _job_id deduplicates with
    #    the immediate submit enqueued by the Telegram webhook handler)
    await redis.enqueue_job(
        "auto_submit_application",
        app.id,
        _defer_by=timedelta(minutes=15),
        _job_id=f"submit:{app.id}",
    )
    logger.info(
        "poll_watchlist: enqueued submit job 'submit:%s' (15-min fallback)",
        app.id,
    )


async def _should_send_notification(session, user_id: int, tender_id: int) -> bool:
    """Check UserWatchlist.notification_on for this (user_id, tender_id) pair.

    Returns True if no watchlist entry found (default) or notification_on=True.
    Returns False only if an explicit notification_on=False entry exists.
    """
    result = await session.execute(
        select(UserWatchlist).where(
            UserWatchlist.user_id == user_id,
            UserWatchlist.tender_id == tender_id,
        )
    )
    watchlist = result.scalar_one_or_none()
    if watchlist is None:
        return True  # default: notify
    return watchlist.notification_on
