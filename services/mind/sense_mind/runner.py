"""
SenseRunner — Agent Lifecycle Manager
=======================================
Manages the full lifecycle of a SenseMind agent:
  - HTTP health/control endpoints (FastAPI)
  - WebRTC session creation and teardown
  - Graceful shutdown on SIGTERM/SIGINT

Usage:
    from sense_mind import SenseMind, SenseRunner

    agent = SenseMind(instructions="...", llm=...)
    SenseRunner(agent).serve(port=8080)
"""

import asyncio
import logging
import os
import signal
from typing import Optional

logger = logging.getLogger(__name__)


class SenseRunner:
    """
    Runs a SenseMind agent as a long-lived service.

    Args:
        agent:    The SenseMind agent instance to run.
        host:     Bind host for the HTTP control API (default: 0.0.0.0).
        port:     Bind port for the HTTP control API (default: 8080).
        room:     Default Sense Relay room name (default: env SENSE_ROOM or "default").
        log_level: Logging level string (default: "info").
    """

    def __init__(
        self,
        agent,
        host: str = "0.0.0.0",
        port: int = 8080,
        room: Optional[str] = None,
        log_level: str = "info",
    ):
        self._agent = agent
        self._host = host
        self._port = port
        self._room = room or os.environ.get("SENSE_ROOM", "default")
        self._log_level = log_level
        self._shutdown_event = asyncio.Event()

    def serve(self, port: int = None):
        """
        Start the agent service. Blocks until shutdown.

        Args:
            port: Override the port set in the constructor.
        """
        if port:
            self._port = port

        logging.basicConfig(
            level=self._log_level.upper(),
            format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        )

        logger.info("SenseRunner starting — room: %s | port: %d", self._room, self._port)
        asyncio.run(self._run())

    async def _run(self):
        loop = asyncio.get_event_loop()

        # Handle SIGTERM / SIGINT for graceful shutdown
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, self._shutdown_event.set)
            except NotImplementedError:
                # Windows doesn't support add_signal_handler — use default Ctrl+C
                pass

        try:
            await asyncio.gather(
                self._run_agent(),
                self._run_http_api(),
            )
        except asyncio.CancelledError:
            pass
        finally:
            await self._cleanup()

    async def _run_agent(self):
        """Connect the agent to Sense Relay and wait for shutdown."""
        try:
            logger.info("Agent connecting to Sense Relay room: %s", self._room)

            # Authenticate and join the room
            await self._agent.edge.authenticate(self._agent._agent_user)
            call = await self._agent.edge.create_call(self._room)
            connection = await self._agent.edge.join(self._agent, call)

            logger.info("Agent joined room — waiting for participants...")
            await self._shutdown_event.wait()

        except Exception as e:
            logger.error("Agent run error: %s", e, exc_info=True)
            self._shutdown_event.set()

    async def _run_http_api(self):
        """Run a minimal FastAPI health + control server."""
        try:
            import uvicorn
            from fastapi import FastAPI

            app = FastAPI(title="Sense Mind", version="0.1.0")

            @app.get("/health")
            async def health():
                return {"status": "ok", "room": self._room}

            @app.get("/status")
            async def status():
                lenses = getattr(self._agent, "_processors", [])
                return {
                    "room": self._room,
                    "lenses": [
                        {"name": getattr(l, "name", str(l)), "available": getattr(l, "_available", True)}
                        for l in lenses
                    ],
                }

            @app.post("/shutdown")
            async def shutdown():
                self._shutdown_event.set()
                return {"status": "shutting_down"}

            config = uvicorn.Config(
                app,
                host=self._host,
                port=self._port,
                log_level=self._log_level,
                loop="none",
            )
            server = uvicorn.Server(config)

            # Shut down the uvicorn server when shutdown event fires
            async def _watch_shutdown():
                await self._shutdown_event.wait()
                server.should_exit = True

            await asyncio.gather(server.serve(), _watch_shutdown())

        except ImportError:
            logger.warning("uvicorn not installed — HTTP API disabled. pip install uvicorn fastapi")
            await self._shutdown_event.wait()
        except Exception as e:
            logger.error("HTTP API error: %s", e, exc_info=True)

    async def _cleanup(self):
        logger.info("SenseRunner shutting down...")
        try:
            await self._agent.edge.close()
        except Exception as e:
            logger.debug("Cleanup error: %s", e)
        logger.info("SenseRunner stopped.")
