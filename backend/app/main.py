from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import engine
from app.routers import health


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    application = FastAPI(
        title="TenderIt API",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.include_router(health.router, prefix="/health", tags=["health"])
    return application


app = create_app()
