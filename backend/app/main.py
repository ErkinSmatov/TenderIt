import asyncio
import logging
from contextlib import asynccontextmanager

from arq.connections import ArqRedis, RedisSettings, create_pool
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.db import engine
from app.routers import auth, company, documents, health, tenders
from app.routers import applications, goszakup_proxy
from app.routers import telegram_webhook
from app.routers.auth import limiter
from app.services.minio_service import ensure_bucket_exists

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize MinIO bucket on startup (idempotent — safe on restart)
    await asyncio.to_thread(ensure_bucket_exists)

    # Initialize ARQ Redis pool for enqueue_job in the webhook handler
    arq_redis: ArqRedis = await create_pool(
        RedisSettings.from_dsn(settings.redis_url)
    )
    app.state.arq_redis = arq_redis

    # Register Telegram webhook — only when bot token is configured (T-05-31)
    if settings.telegram_bot_token:
        try:
            import telegram

            async with telegram.Bot(settings.telegram_bot_token) as bot:
                webhook_url = f"{settings.webhook_base_url}/api/telegram/webhook"
                await bot.set_webhook(
                    url=webhook_url,
                    secret_token=settings.telegram_webhook_secret,
                )
                logger.info("Telegram set_webhook registered: %s", webhook_url)
        except Exception as exc:
            # Non-fatal: app still works without Telegram if token is wrong
            logger.warning("Telegram set_webhook failed: %s", exc)

    yield

    await arq_redis.close()
    await engine.dispose()


def create_app() -> FastAPI:
    application = FastAPI(
        title="TenderIt API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Rate limiter state
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS — allow frontend origin with credentials
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health.router, prefix="/health", tags=["health"])
    application.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    application.include_router(company.router, prefix="/api/company", tags=["company"])
    application.include_router(tenders.router, prefix="/api", tags=["tenders"])
    application.include_router(documents.router, prefix="/api", tags=["documents"])
    application.include_router(applications.router, prefix="/api", tags=["applications"])
    application.include_router(goszakup_proxy.router, prefix="/api/goszakup", tags=["goszakup-proxy"])
    application.include_router(telegram_webhook.router, prefix="/api", tags=["telegram"])

    return application


app = create_app()
