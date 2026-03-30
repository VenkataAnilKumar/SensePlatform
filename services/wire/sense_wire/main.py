"""
Sense Wire — Real-time Messaging Server
========================================
WebSocket + REST messaging for Sense Platform.
No GetStream. No cloud. Runs on your own Postgres + Redis.

WebSocket:
    WS /ws/connect?token=<jwt>   — establish real-time connection

REST:
    POST   /channels                              — create channel
    GET    /channels/:type/:id                    — get channel
    POST   /channels/:type/:id/members            — add member
    GET    /channels/:type/:id/messages           — message history
    DELETE /channels/:type/:id/messages/:id       — delete message
    POST   /channels/:type/:id/messages/:id/pin   — pin message
    POST   /channels/:type/:id/event              — emit custom event
"""

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from sense_wire.config import get_settings
from sense_wire.database import Base, engine
from sense_wire.deps import get_ws_user
from sense_wire.pubsub.redis_pubsub import get_pubsub
from sense_wire.routers import channels, events, messages
from sense_wire.ws.events import ServerEvent, make_event
from sense_wire.ws.handler import WireEventHandler
from sense_wire.ws.manager import get_manager
from sense_wire.database import AsyncSessionLocal

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Sense Wire starting up...")

    if settings.debug:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # Connect Redis pub/sub
    pubsub = get_pubsub()
    try:
        await pubsub.connect()
        logger.info("Wire Redis pub/sub ready")
    except Exception as e:
        logger.warning("Wire Redis unavailable — cross-instance fan-out disabled: %s", e)

    logger.info("Sense Wire ready on %s:%d", settings.host, settings.port)
    yield

    logger.info("Sense Wire shutting down...")
    await pubsub.close()
    await engine.dispose()
    logger.info("Sense Wire stopped.")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sense Wire",
        description=(
            "Real-time messaging for Sense Platform. "
            "WebSocket channels with Postgres persistence and Redis pub/sub fan-out."
        ),
        version=settings.version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── REST routers ──────────────────────────────────────────────────────────
    app.include_router(channels.router)
    app.include_router(messages.router)
    app.include_router(events.router)

    # ── WebSocket endpoint ────────────────────────────────────────────────────
    @app.websocket("/ws/connect")
    async def websocket_endpoint(websocket: WebSocket, token: str):
        """
        Establish a real-time WebSocket connection to Sense Wire.

        **Auth**: Pass your Sense Gate JWT as a query parameter:
            ws://localhost:3001/ws/connect?token=<jwt>

        Once connected, send JSON events:
            {"type": "channel.subscribe", "channel_type": "room", "channel_id": "my-room"}
            {"type": "message.new", "channel_type": "room", "channel_id": "my-room", "text": "Hello"}
            {"type": "typing.start", "channel_type": "room", "channel_id": "my-room"}

        Receive events:
            {"type": "message.new", "message": {...}}
            {"type": "typing.start", "user_id": "...", "channel_id": "..."}
            {"type": "lens.event", "data": {"mood": "frustrated", ...}}
        """
        # Validate JWT
        try:
            user = await get_ws_user(token)
        except Exception:
            await websocket.close(code=4001, reason="Unauthorized")
            return

        manager = get_manager()
        conn = await manager.connect(
            websocket,
            user_id=user.get("sub", "anonymous"),
            tenant_id=user.get("tenant_id", ""),
        )

        # Send connection acknowledgement
        await conn.send(make_event(
            ServerEvent.CONNECTED,
            user_id=conn.user_id,
            tenant_id=conn.tenant_id,
        ))

        try:
            async with AsyncSessionLocal() as db:
                handler = WireEventHandler(conn, manager, db)

                while True:
                    raw = await websocket.receive_text()
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        await conn.send(make_event(ServerEvent.ERROR, message="Invalid JSON"))
                        continue

                    await handler.handle(event)
                    await db.commit()

        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error("WebSocket error for user=%s: %s", conn.user_id, e, exc_info=True)
        finally:
            await manager.disconnect(websocket)

    # ── Health ────────────────────────────────────────────────────────────────
    @app.get("/health", tags=["System"])
    async def health():
        manager = get_manager()
        return {
            "status": "ok",
            "service": "sense-wire",
            "version": settings.version,
            "connections": manager.connection_count(),
        }

    @app.get("/", tags=["System"])
    async def root():
        return {"service": "Sense Wire", "version": settings.version, "docs": "/docs"}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )
    uvicorn.run("sense_wire.main:app", host=settings.host, port=settings.port, reload=settings.debug)
