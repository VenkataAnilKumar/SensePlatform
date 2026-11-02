from sense_mind.core.agents import Agent
from sense_mind.core.agents.agent_launcher import AgentLauncher, AgentSession
from sense_mind.core.agents.session_registry import (
    InMemorySessionKVStore,
    SessionInfo,
    SessionKVStore,
    SessionRegistry,
)
from sense_mind.core.edge.types import User
from sense_mind.core.runner import Runner, ServeOptions

__all__ = [
    "Agent",
    "AgentLauncher",
    "AgentSession",
    "InMemorySessionKVStore",
    "Runner",
    "ServeOptions",
    "SessionInfo",
    "SessionKVStore",
    "SessionRegistry",
    "User",
]

try:
    from sense_mind.core.agents.session_registry import RedisSessionKVStore

    __all__ += ["RedisSessionKVStore"]
except ImportError as e:
    import warnings

    if e.name and e.name.startswith("redis") or "RedisSessionKVStore" in str(e):
        warnings.warn(
            "Optional dependency 'redis' is not installed. "
            "Install the [redis] extra to enable RedisSessionKVStore.",
            stacklevel=2,
        )
    else:
        raise
