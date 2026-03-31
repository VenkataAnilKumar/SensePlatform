"""
SenseRunner — Agent Lifecycle Manager
======================================
Manages the full lifecycle of Sense Mind agents:

  Pool mode (default):
    - Start/stop agents per room via REST API
    - Supports multiple concurrent agents across many rooms
    - Auto-streams lens events to Sense Wire (if SENSE_WIRE_URL is set)

  Legacy single-agent mode (backward compatible):
    - Pass a SenseMind instance + set SENSE_ROOM to auto-start on boot
    - SenseRunner(agent).serve()

HTTP Control API (port 8080 by default):
    GET  /health                         — health check
    GET  /status                         — alias: all agents status
    GET  /agents/status                  — all agents status
    POST /agents/start                   — launch agent in a room
    POST /agents/stop                    — stop agent in a room
    GET  /agents/{room}/lenses           — list lenses for a room
    POST /agents/{room}/lenses/configure — update lens settings at runtime
    POST /shutdown                       — graceful shutdown

Usage (pool mode):
    runner = SenseRunner()
    runner.serve(port=8080)
    # Then: POST /agents/start {"room": "tenant__room1", "lenses": ["MoodLens"]}

Usage (legacy single-agent mode):
    agent = SenseMind(instructions="...", llm=anthropic.LLM())
    SenseRunner(agent).serve()
"""

import asyncio
import logging
import os
import signal
from typing import Optional

from sense_mind.bridge import LensEventBridge
from sense_mind.pool import AgentConfig, AgentPool

logger = logging.getLogger(__name__)


class SenseRunner:
    """
    Runs Sense Mind as a multi-agent HTTP service.

    Args:
        agent:      Optional SenseMind to auto-start in SENSE_ROOM on boot.
                    Keeps backward compat with SenseRunner(agent).serve().
        host:       HTTP bind host (default: 0.0.0.0).
        port:       HTTP bind port (default: 8080 or SENSE_MIND_PORT env var).
        room:       Default room for legacy auto-start (default: SENSE_ROOM env).
        log_level:  Logging level string (default: info).
    """

    def __init__(
        self,
        agent=None,
        host: str = "0.0.0.0",
        port: int = None,
        room: Optional[str] = None,
        log_level: str = "info",
    ):
        self._host = host
        self._port = port or int(os.environ.get("SENSE_MIND_PORT", "8080"))
        self._default_room = room or os.environ.get("SENSE_ROOM", "")
        self._legacy_agent = agent   # SenseMind instance for auto-start
        self._log_level = log_level
        self._shutdown_event = asyncio.Event()
        self._pool = AgentPool()
        self._bridge = LensEventBridge()
        self._bridge.attach_to_pool(self._pool)

    def serve(self, port: int = None):
        """
        Start the service. Blocks until shutdown.

        Args:
            port: Override the port set in the constructor.
        """
        if port:
            self._port = port

        logging.basicConfig(
            level=self._log_level.upper(),
            format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        )

        logger.info("SenseRunner starting — port: %d", self._port)
        asyncio.run(self._run())

    # ── Internal entry point ──────────────────────────────────────────────────

    async def _run(self):
        loop = asyncio.get_event_loop()

        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, self._shutdown_event.set)
            except NotImplementedError:
                pass  # Windows

        try:
            tasks = [self._run_http_api()]

            # Legacy mode: auto-start the provided agent in the default room
            if self._legacy_agent and self._default_room:
                tasks.append(self._auto_start_legacy())

            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
        finally:
            await self._cleanup()

    async def _auto_start_legacy(self):
        """
        Backward-compat: directly connect the pre-built SenseMind instance.
        Runs until shutdown_event fires.
        """
        try:
            logger.info("Auto-starting legacy agent in room: %s", self._default_room)
            agent = self._legacy_agent
            await agent.edge.authenticate(agent._agent_user)
            call = await agent.edge.create_call(self._default_room)
            await agent.edge.join(agent, call)
            logger.info("Legacy agent joined room: %s", self._default_room)
            await self._shutdown_event.wait()
        except Exception as e:
            logger.error("Legacy agent error: %s", e, exc_info=True)
            self._shutdown_event.set()

    async def _cleanup(self):
        logger.info("SenseRunner shutting down...")
        await self._pool.stop_all()
        await self._bridge.close()
        if self._legacy_agent:
            try:
                await self._legacy_agent.edge.close()
            except Exception:
                pass
        logger.info("SenseRunner stopped.")

    # ── HTTP API ──────────────────────────────────────────────────────────────

    async def _run_http_api(self):
        try:
            import uvicorn
            from fastapi import FastAPI, HTTPException
            from pydantic import BaseModel

            app = FastAPI(title="Sense Mind", version="0.2.0")

            # ── Request / Response models ─────────────────────────────────────

            class StartRequest(BaseModel):
                room: str
                instructions: str | None = None
                lenses: list[str] = []
                llm: str = "claude-sonnet-4-6"
                agent_id: str = "sense-agent"
                agent_name: str = "Sense AI"

            class StopRequest(BaseModel):
                room: str

            class LensConfigRequest(BaseModel):
                throttle_seconds: float | None = None
                enabled: bool | None = None

            # ── Health ────────────────────────────────────────────────────────

            @app.get("/health")
            async def health():
                pool_status = self._pool.status()
                return {
                    "status": "ok",
                    "agents": pool_status.get("count", 0),
                }

            # ── Legacy /status (single-room compat) ───────────────────────────

            @app.get("/status")
            async def status_all(room: str | None = None):
                return self._pool.status(room=room)

            # ── Agent pool endpoints ──────────────────────────────────────────

            @app.get("/agents/status")
            async def agents_status(room: str | None = None):
                return self._pool.status(room=room)

            @app.post("/agents/start")
            async def agents_start(req: StartRequest):
                config = AgentConfig(
                    room=req.room,
                    instructions=req.instructions or "You are a helpful AI assistant.",
                    lenses=req.lenses,
                    llm=req.llm,
                    agent_id=req.agent_id,
                    agent_name=req.agent_name,
                )
                result = await self._pool.start(config)
                if result.get("status") == "already_running":
                    return result  # 200 with idempotent response
                return result

            @app.post("/agents/stop")
            async def agents_stop(req: StopRequest):
                result = await self._pool.stop(req.room)
                if result.get("status") == "not_found":
                    raise HTTPException(status_code=404, detail=result)
                return result

            # ── Lens management per room ──────────────────────────────────────

            @app.get("/agents/{room}/lenses")
            async def get_lenses(room: str):
                lenses = self._pool.get_lenses(room)
                if lenses is None:
                    raise HTTPException(status_code=404, detail={"room": room, "status": "not_found"})
                return {"room": room, "lenses": lenses}

            @app.post("/agents/{room}/lenses/{lens_name}/configure")
            async def configure_lens(room: str, lens_name: str, req: LensConfigRequest):
                result = self._pool.configure_lens(
                    room=room,
                    lens_name=lens_name,
                    throttle_seconds=req.throttle_seconds,
                    enabled=req.enabled,
                )
                if result.get("status") == "not_found":
                    raise HTTPException(status_code=404, detail=result)
                if result.get("status") == "lens_not_found":
                    raise HTTPException(status_code=404, detail=result)
                return result

            # ── Shutdown ──────────────────────────────────────────────────────

            @app.post("/shutdown")
            async def shutdown():
                self._shutdown_event.set()
                return {"status": "shutting_down"}

            # ── Serve ─────────────────────────────────────────────────────────

            config = uvicorn.Config(
                app,
                host=self._host,
                port=self._port,
                log_level=self._log_level,
                loop="none",
            )
            server = uvicorn.Server(config)

            async def _watch_shutdown():
                await self._shutdown_event.wait()
                server.should_exit = True

            await asyncio.gather(server.serve(), _watch_shutdown())

        except ImportError:
            logger.warning(
                "uvicorn/fastapi not installed — HTTP API disabled. "
                "pip install uvicorn fastapi pydantic"
            )
            await self._shutdown_event.wait()
        except Exception as e:
            logger.error("HTTP API error: %s", e, exc_info=True)
