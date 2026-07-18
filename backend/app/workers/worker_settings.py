"""ARQ WorkerSettings — durable auto-submission engine.

Run the worker:
    python -m arq app.workers.worker_settings.WorkerSettings

Worker lifecycle:
  on_startup: creates async DB engine + sessionmaker → stored in ctx.
  on_shutdown: disposes DB engine.

Jobs:
  functions:  [auto_submit_application]  — triggered on demand + 15-min fallback.
  cron_jobs:  [poll_watchlist_tenders]   — every 5 min, unique=True.

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
from app.workers.tasks.poll_watchlist import poll_watchlist_tenders

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
    """ARQ worker configuration for the TenderIt auto-submission engine."""

    redis_settings = RedisSettings.from_dsn(settings.redis_url)

    # Triggered jobs (enqueued by poll_watchlist or Telegram webhook)
    functions = [auto_submit_application]

    # Cron: poll every 5 minutes; unique=True prevents overlap on multiple workers
    cron_jobs = [
        cron(
            poll_watchlist_tenders,
            minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
            unique=True,
        )
    ]

    on_startup = startup
    on_shutdown = shutdown
