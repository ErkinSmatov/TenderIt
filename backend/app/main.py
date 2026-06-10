import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.db import engine
from app.routers import auth, company, documents, health, tenders
from app.routers.auth import limiter
from app.services.minio_service import ensure_bucket_exists


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize MinIO bucket on startup (idempotent — safe on restart)
    await asyncio.to_thread(ensure_bucket_exists)
    yield
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

    return application


app = create_app()
