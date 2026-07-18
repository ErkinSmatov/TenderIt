"""ARQ job: auto_submit_application.

Submits a TenderIt application to the goszakup portal.

Called either:
  - As a delayed job (15-min fallback) enqueued by poll_watchlist_tenders.
  - Immediately when user clicks "Да" in the Telegram webhook handler.

Both use the same _job_id=f"submit:{application_id}" for deduplication (T-05-32).

Reference: 05-RESEARCH.md lines 427-480 (Pattern 3: Delayed Job + Retry).
Pitfall:    05-RESEARCH.md lines 740-746 (duplicate jobs — stable _job_id).
"""

from __future__ import annotations

import logging

from arq import Retry

from app.services.application_service import (
    get_user_application,
    increment_retry,
    mark_error,
    mark_submitted,
    mark_submitting,
)
from app.services.goszakup_portal_client import GoszakupPortalClient
from app.services.redis_service import get_confirm, get_goszakup_session

logger = logging.getLogger(__name__)

# Cumulative back-off in seconds (7 retries ≈ 35 min total — D-05-05 / T-05-34).
# Index maps to job_try (1-based from ARQ ctx).
BACKOFF_SECONDS = [0, 30, 90, 180, 300, 600, 900]


async def auto_submit_application(ctx: dict, application_id: int) -> None:
    """ARQ job: finalise submission via goszakup portal.

    Flow:
      1. Check confirm:{application_id} in Redis.
         - "no"           → mark_error("Cancelled by user") and return.
         - "yes"/pending/expired/None → proceed to submit.
      2. Load goszakup session from Redis.
         - Missing → raise Retry(defer=60) (await session refresh).
      3. Call GoszakupPortalClient.public_application.
         - {"status":"ok"} → mark_submitted.
         - error           → raise Retry(defer=BACKOFF_SECONDS[job_try]).
                             After 7 tries → mark_error(message).

    Security: session secrets (phpsessid, csrf) are NEVER logged (T-05-03).
    Dedup:    stable _job_id=f"submit:{application_id}" (T-05-32).
    """
    redis = ctx["redis"]
    job_try = ctx.get("job_try", 1)

    # Step 1: Check user confirmation
    confirm = await get_confirm(redis, application_id)
    if confirm == "no":
        logger.info(
            "auto_submit: app %s cancelled by user (confirm=no)", application_id
        )
        async with ctx["db_session_factory"]() as session:
            # Use a wide search (all users) since this runs in a background job
            from sqlalchemy import select
            from app.models.application import Application

            result = await session.execute(
                select(Application).where(Application.id == application_id)
            )
            app = result.scalar_one_or_none()
            if app:
                await mark_error(session, app, "Cancelled by user")
        return

    # Step 2: Load goszakup session from Redis
    async with ctx["db_session_factory"]() as session:
        from sqlalchemy import select
        from app.models.application import Application

        result = await session.execute(
            select(Application).where(Application.id == application_id)
        )
        app = result.scalar_one_or_none()

        if app is None:
            logger.error(
                "auto_submit: application %s not found in DB", application_id
            )
            return

        session_data = await get_goszakup_session(redis, app.user_id)
        if not session_data:
            logger.warning(
                "auto_submit: goszakup session missing for user %s (app %s), will retry",
                app.user_id,
                application_id,
            )
            raise Retry(defer=60)

        # Step 3: Submit via goszakup portal
        client = GoszakupPortalClient()
        try:
            result_data = await client.public_application(
                tender_buy_id=session_data["tender_buy_id"],
                application_id=session_data["application_id"],
                phpsessid=session_data["phpsessid"],
                csrf=session_data["csrf"],
            )
        except Exception as exc:
            logger.warning(
                "auto_submit: HTTP error for app %s (try %d): %s",
                application_id,
                job_try,
                exc,
            )
            if job_try <= len(BACKOFF_SECONDS):
                defer = BACKOFF_SECONDS[min(job_try - 1, len(BACKOFF_SECONDS) - 1)]
                await increment_retry(session, app)
                raise Retry(defer=defer) from exc
            await mark_error(session, app, str(exc))
            return

        if result_data.get("status") == "ok":
            logger.info("auto_submit: app %s submitted successfully", application_id)
            await mark_submitted(session, app)
        else:
            error_msg = result_data.get("message", "Unknown portal error")
            logger.warning(
                "auto_submit: portal error for app %s (try %d): %s",
                application_id,
                job_try,
                error_msg,
            )
            if job_try < len(BACKOFF_SECONDS):
                defer = BACKOFF_SECONDS[min(job_try, len(BACKOFF_SECONDS) - 1)]
                await increment_retry(session, app)
                raise Retry(defer=defer)
            # Exhausted all retries — mark final error (T-05-34)
            await mark_error(session, app, error_msg)
