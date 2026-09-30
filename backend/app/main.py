"""Application factory and ASGI entry point (``uvicorn app.main:app``)."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.error_handlers import register_error_handlers
from app.api.middleware import REQUEST_ID_HEADER, RequestContextMiddleware
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import create_engine, create_session_factory

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Creating the engine does not connect; connectivity is reported by /health/ready
        # so the API can start (and explain what is wrong) while a dependency is down.
        engine = create_engine(settings)
        http_client = httpx.AsyncClient(timeout=settings.health_check_timeout_seconds)
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        app.state.http_client = http_client
        logger.info(
            "Application started",
            extra={"environment": settings.environment.value, "version": __version__},
        )
        try:
            yield
        finally:
            await http_client.aclose()
            await engine.dispose()
            logger.info("Application stopped")

    app = FastAPI(
        title=f"{settings.app_name} API",
        version=__version__,
        description="Production RAG evaluation and observability platform.",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings

    register_error_handlers(app)
    # Middleware added last runs first: request context wraps CORS so preflight
    # responses also carry a request ID.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(RequestContextMiddleware)

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
