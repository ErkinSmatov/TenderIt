"""ARQ WorkerSettings — durable auto-submission + discovery engine.

Run the worker:
    python -m arq app.workers.worker_settings.WorkerSettings

Worker lifecycle:
  on_startup: creates async DB engine + sessionmaker → stored in ctx.
  on_shutdown: disposes DB engine.

Jobs:
  functions:  [auto_submit_application]   — triggered on demand + 15-min fallback.
              [run_matching]               — enqueued by poll_goszakup_discovery (D-07).
  cron_jobs:  [poll_watchlist_tenders]    — every 5 min, unique=True.
              [poll_goszakup_discovery]   — every 15 min, unique=True (D-06).

Reference: 05-RESEARCH.md lines 377-419 (Pattern 2: WorkerSettings).
Pitfall:    05-RESEARCH.md lines 770-776 (ARQ startup without DB context manager).
"""

from __future__ import annotations

import logging

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.workers.tasks.auto_submit import auto_submit_application
from app.workers.tasks.poll_goszakup_discovery import poll_goszakup_discovery
from app.workers.tasks.poll_watchlist import poll_watchlist_tenders
from app.workers.tasks.run_matching import run_matching

logger = logging.getLogger(__name__)


async def startup(ctx: dict) -> None:
    """Initialize async DB engine + session factory for the ARQ worker process.

    These are stored in ctx so every job can open its own session without
    importing FastAPI's get_db dependency.
    """
    engine = create_async_engine(settings.database_url, echo=False)
    ctx["db_engine"] = engine
    ctx["db_session_factory"] = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    logger.info("ARQ worker: DB engine initialized")


async def shutdown(ctx: dict) -> None:
    """Dispose the DB engine on worker shutdown."""
    await ctx["db_engine"].dispose()
    logger.info("ARQ worker: DB engine disposed")


class WorkerSettings:
    """ARQ worker configuration for the TenderIt auto-submission + discovery engine."""

    redis_settings = RedisSettings.from_dsn(settings.redis_url)

    # On-demand jobs (enqueued by cron tasks or HTTP handlers)
    # run_matching is enqueued by poll_goszakup_discovery after each poll (D-07)
    functions = [auto_submit_application, run_matching]

    # Cron jobs:
    #   poll_watchlist_tenders  — every 5 min (Phase 5 auto-submit pipeline)
    #   poll_goszakup_discovery — every 15 min (Phase 7 discovery pipeline, D-06)
    cron_jobs = [
        cron(
            poll_watchlist_tenders,
            minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
            unique=True,
        ),
        cron(
            poll_goszakup_discovery,
            minute={0, 15, 30, 45},
            unique=True,
        ),
    ]

    on_startup = startup
    on_shutdown = shutdown
