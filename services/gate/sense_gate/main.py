"""
Sense Gate — FastAPI Application
API gateway, auth, multi-tenancy, and agent orchestration for Sense Platform.

Endpoints:
    POST   /auth/token                   — issue JWT for a tenant user
    POST   /rooms/{room_id}/join         — get LiveKit relay token
    GET    /rooms                        — list active rooms
    POST   /agents/start                 — launch a Sense Mind agent
    POST   /agents/stop                  — stop an agent
    GET    /agents/status                — get agent status
    POST   /tenants                      — create tenant
    GET    /tenants/me                   — get current tenant
    POST   /tenants/me/api-keys          — create API key
    GET    /tenants/me/api-keys          — list API keys
    DELETE /tenants/me/api-keys/{id}     — revoke API key
    POST   /webhooks                     — register webhook
    GET    /webhooks                     — list webhooks
    DELETE /webhooks/{id}                — delete webhook
    POST   /webhooks/{id}/test           — test webhook delivery
    GET    /usage                        — usage metrics
"""

import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sense_gate.config import get_settings
from sense_gate.database import engine, Base
from sense_gate.middleware.rate_limit import RateLimitMiddleware
from sense_gate.routers import agents, auth, rooms, tenants, usage, webhooks

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info("Sense Gate starting up...")
    insecure = settings.insecure_defaults()
    if insecure and settings.is_production:
        raise RuntimeError(
            "Refusing to start in production with default secrets: " + ", ".join(insecure)
        )
    for name in insecure:
        logger.warning("%s is still the default value — change it before production!", name)
    if settings.is_production and not settings.admin_api_key:
        logger.warning("ADMIN_API_KEY is unset — POST /tenants is disabled in production")

    # Auto-create tables (dev mode — use Alembic in production)
    if settings.debug:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created (debug mode)")

    # Connect to Redis for rate limiting
    redis_client = None
    try:
        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        await redis_client.ping()
        app.state.redis = redis_client
        logger.info("Redis connected: %s", settings.redis_url)
    except Exception as e:
        logger.warning("Redis unavailable — rate limiting disabled: %s", e)
        app.state.redis = None

    logger.info("Sense Gate ready on %s:%d", settings.host, settings.port)

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("Sense Gate shutting down...")
    if redis_client:
        await redis_client.aclose()

    from sense_gate.services.agent_service import get_agent_service
    await get_agent_service().close()

    await engine.dispose()
    logger.info("Sense Gate stopped.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sense Gate",
        description=(
            "API gateway, authentication, multi-tenancy, and agent orchestration "
            "for Sense Platform — the self-hosted AI video/voice/vision developer platform."
        ),
        version=settings.version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()] or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        # Browsers reject credentialed requests with a wildcard origin
        allow_credentials="*" not in origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Rate Limiting (resolves app.state.redis per request) ──────────────────
    app.add_middleware(RateLimitMiddleware)

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(auth.router)
    app.include_router(rooms.router)
    app.include_router(agents.router)
    app.include_router(tenants.router)
    app.include_router(webhooks.router)
    app.include_router(usage.router)

    # ── Health ────────────────────────────────────────────────────────────────
    @app.get("/health", tags=["System"])
    async def health():
        return {"status": "ok", "service": "sense-gate", "version": settings.version}

    @app.get("/", tags=["System"])
    async def root():
        return {
            "service": "Sense Gate",
            "version": settings.version,
            "docs": "/docs",
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )
    uvicorn.run(
        "sense_gate.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
