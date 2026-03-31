"""
AgentPool — Multi-Room Agent Manager
======================================
Manages multiple SenseMind agent instances, one per room.
Used by SenseRunner to support the multi-agent REST API:
    POST /agents/start
    POST /agents/stop
    GET  /agents/status
    GET  /agents/{room}/lenses
    POST /agents/{room}/lenses/configure
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Lens registry ─────────────────────────────────────────────────────────────
# Maps string name → lens class. Populated lazily (vision deps are optional).

_LENS_REGISTRY: dict[str, type] = {}


def _load_lens_registry():
    global _LENS_REGISTRY
    try:
        from sense_mind.lenses.mood_lens import MoodLens
        from sense_mind.lenses.pose_lens import PoseLens
        from sense_mind.lenses.guard_lens import GuardLens
        from sense_mind.lenses.face_lens import FaceLens

        _LENS_REGISTRY = {
            "MoodLens": MoodLens,
            "PoseLens": PoseLens,
            "GuardLens": GuardLens,
            "FaceLens": FaceLens,
        }
        logger.debug("Lens registry loaded: %s", list(_LENS_REGISTRY))
    except ImportError as e:
        logger.debug("Vision lenses not available: %s (install sense-mind[vision])", e)


_load_lens_registry()


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class AgentConfig:
    """Configuration for a single agent instance."""
    room: str
    instructions: str = "You are a helpful AI assistant."
    lenses: list[str] = field(default_factory=list)
    llm: str = "claude-sonnet-4-6"
    agent_id: str = "sense-agent"
    agent_name: str = "Sense AI"


@dataclass
class AgentEntry:
    """A running agent tracked by the pool."""
    config: AgentConfig
    agent: Any          # SenseMind instance
    task: asyncio.Task
    started_at: float = field(default_factory=time.time)


# ── AgentPool ─────────────────────────────────────────────────────────────────

class AgentPool:
    """
    Manages multiple SenseMind agents, one per Sense Relay room.

    All methods are async-safe and must be called from the running event loop.
    """

    def __init__(self):
        self._agents: dict[str, AgentEntry] = {}   # room → entry
        self._event_listeners: list = []            # (room, LensEvent) callbacks

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_lens_event(self, callback):
        """Register a callback invoked for every LensEvent from any agent."""
        self._event_listeners.append(callback)

    async def start(self, config: AgentConfig) -> dict[str, Any]:
        """
        Launch a new SenseMind agent into *config.room*.

        If an agent is already running in that room, returns status
        'already_running' without creating a duplicate.
        """
        if config.room in self._agents:
            entry = self._agents[config.room]
            if not entry.task.done():
                return {"status": "already_running", "room": config.room}
            # Previous task died — remove stale entry and restart
            del self._agents[config.room]

        agent = _build_agent(config)

        # Wire lens event forwarding
        for lens in getattr(agent, "_processors", []):
            _attach_lens_callback(lens, config.room, self._event_listeners)

        task = asyncio.create_task(
            _run_agent_in_room(agent, config.room),
            name=f"sense-agent-{config.room}",
        )
        self._agents[config.room] = AgentEntry(config=config, agent=agent, task=task)

        logger.info(
            "AgentPool.start: room=%s llm=%s lenses=%s",
            config.room, config.llm, config.lenses,
        )
        return {"status": "started", "room": config.room}

    async def stop(self, room: str) -> dict[str, Any]:
        """Stop the agent running in *room*."""
        entry = self._agents.pop(room, None)
        if entry is None:
            return {"status": "not_found", "room": room}

        entry.task.cancel()
        await asyncio.gather(entry.task, return_exceptions=True)

        try:
            await entry.agent.edge.close()
        except Exception:
            pass

        logger.info("AgentPool.stop: room=%s", room)
        return {"status": "stopped", "room": room}

    async def stop_all(self):
        """Stop every running agent. Called on shutdown."""
        for room in list(self._agents.keys()):
            await self.stop(room)

    # ── Status ────────────────────────────────────────────────────────────────

    def status(self, room: Optional[str] = None) -> dict[str, Any]:
        """
        Return status of one or all agents.

        Args:
            room: If provided, return status for that room only.
        """
        if room is not None:
            entry = self._agents.get(room)
            if entry is None:
                return {"status": "not_found", "room": room}
            return _format_entry(room, entry)

        return {
            "agents": [_format_entry(r, e) for r, e in self._agents.items()],
            "count": len(self._agents),
        }

    # ── Lens config ───────────────────────────────────────────────────────────

    def get_lenses(self, room: str) -> list[dict]:
        """List lenses attached to the agent running in *room*."""
        entry = self._agents.get(room)
        if entry is None:
            return []
        return [
            {
                "name": getattr(l, "name", type(l).__name__),
                "throttle_seconds": getattr(l, "throttle_seconds", None),
                "available": getattr(l, "_available", False),
            }
            for l in getattr(entry.agent, "_processors", [])
        ]

    def configure_lens(
        self,
        room: str,
        lens_name: str,
        throttle_seconds: Optional[float] = None,
        enabled: Optional[bool] = None,
    ) -> dict[str, Any]:
        """
        Update runtime configuration for a lens.

        Args:
            room:             Room the agent is running in.
            lens_name:        Name of the lens (e.g. "mood_lens").
            throttle_seconds: New throttle interval in seconds.
            enabled:          Enable or disable the lens.
        """
        entry = self._agents.get(room)
        if entry is None:
            return {"status": "not_found", "room": room}

        for lens in getattr(entry.agent, "_processors", []):
            name = getattr(lens, "name", type(lens).__name__)
            if name == lens_name:
                if throttle_seconds is not None:
                    lens.throttle_seconds = throttle_seconds
                if enabled is not None:
                    lens._available = enabled
                return {
                    "status": "updated",
                    "room": room,
                    "lens": lens_name,
                    "throttle_seconds": lens.throttle_seconds,
                    "available": lens._available,
                }

        return {"status": "lens_not_found", "lens": lens_name, "room": room}


# ── Private helpers ───────────────────────────────────────────────────────────

def _build_agent(config: AgentConfig):
    """Instantiate a SenseMind from an AgentConfig."""
    from sense_mind.mind import SenseMind

    llm = _resolve_llm(config.llm)
    lenses = _resolve_lenses(config.lenses)

    return SenseMind(
        instructions=config.instructions,
        llm=llm,
        lenses=lenses or None,
        agent_id=config.agent_id,
        agent_name=config.agent_name,
    )


def _resolve_llm(model_name: str):
    """
    Create an LLM plugin from a model name string.
    Dispatches based on known model name prefixes.
    """
    model_name = model_name or "claude-sonnet-4-6"

    if "claude" in model_name:
        from sense_mind.plugins import anthropic as _p
        return _p.LLM(model_name)
    if any(x in model_name for x in ("gpt", "o1-", "o3-", "o4-")):
        from sense_mind.plugins import openai as _p
        return _p.LLM(model_name)
    if "gemini" in model_name:
        from sense_mind.plugins import gemini as _p
        return _p.LLM(model_name)
    if "mistral" in model_name:
        from sense_mind.plugins import mistral as _p
        return _p.LLM(model_name)
    if "grok" in model_name:
        from sense_mind.plugins import xai as _p
        return _p.LLM(model_name)

    # Fallback to Anthropic
    from sense_mind.plugins import anthropic as _p
    return _p.LLM(model_name)


def _resolve_lenses(names: list[str]) -> list:
    """Instantiate lenses by string name using the registry."""
    lenses = []
    for name in names:
        cls = _LENS_REGISTRY.get(name)
        if cls is None:
            logger.warning("Unknown lens '%s' — skipping. Available: %s", name, list(_LENS_REGISTRY))
            continue
        try:
            lenses.append(cls())
        except Exception as e:
            logger.warning("Could not instantiate lens '%s': %s", name, e)
    return lenses


def _attach_lens_callback(lens, room: str, listeners: list):
    """Register a fan-out callback on a lens for pool-level event routing."""
    def _handle(event):
        for fn in listeners:
            try:
                if asyncio.iscoroutinefunction(fn):
                    asyncio.ensure_future(fn(room, event))
                else:
                    fn(room, event)
            except Exception as exc:
                logger.debug("Lens event listener error: %s", exc)

    lens.on_event(_handle)


async def _run_agent_in_room(agent, room: str):
    """
    Connect an agent to a room and wait until cancelled.
    Handles graceful cleanup on CancelledError.
    """
    try:
        logger.info("Agent connecting to room: %s", room)
        await agent.edge.authenticate(agent._agent_user)
        call = await agent.edge.create_call(room)
        await agent.edge.join(agent, call)
        logger.info("Agent joined room: %s — waiting for participants", room)
        await asyncio.sleep(float("inf"))
    except asyncio.CancelledError:
        logger.info("Agent task cancelled for room: %s", room)
    except Exception as e:
        logger.error("Agent crashed in room '%s': %s", room, e, exc_info=True)


def _format_entry(room: str, entry: AgentEntry) -> dict:
    """Format an AgentEntry for the status API response."""
    lenses = getattr(entry.agent, "_processors", [])
    return {
        "room": room,
        "status": "running" if not entry.task.done() else "stopped",
        "llm": entry.config.llm,
        "lenses": [getattr(l, "name", type(l).__name__) for l in lenses],
        "uptime_seconds": round(time.time() - entry.started_at, 1),
    }
