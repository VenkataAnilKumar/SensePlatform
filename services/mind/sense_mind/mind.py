"""
Sense Mind — AI Agent Engine
=============================
The core agent class for Sense Platform.
Pre-wired to Sense Relay (self-hosted WebRTC) with no cloud dependencies.

Usage:
    from sense_mind import SenseMind, SenseRunner
    from sense_mind.plugins import anthropic, deepgram
    from sense_mind.lenses import MoodLens, PoseLens

    agent = SenseMind(
        relay_url="ws://localhost:7880",
        instructions="You are a helpful contact center agent.",
        llm=anthropic.LLM("claude-sonnet-4-6"),
        stt=deepgram.STT(),
        lenses=[MoodLens()],
    )
    SenseRunner(agent).serve()
"""

import logging
import os
from pathlib import Path
from typing import Optional

from sense_mind.core.agents.agents import Agent
from sense_mind.core.agents.agent_types import User
from sense_mind.transport.relay_transport import RelayTransport

logger = logging.getLogger(__name__)


class SenseMind(Agent):
    """
    Sense Platform AI agent.

    Pre-configured with RelayTransport for Sense Relay (self-hosted WebRTC).
    All Sense Mind plugins (LLM, STT, TTS, Lenses) work out of the box.

    Args:
        relay_url:      WebSocket URL of your Sense Relay server
        relay_api_key:  Sense Relay API key (from sense-relay.yaml)
        relay_secret:   Sense Relay API secret
        instructions:   System prompt string or path to .md file
        llm:            Language model plugin (anthropic, openai, gemini, etc.)
        stt:            Speech-to-text plugin (deepgram, assemblyai, etc.)
        tts:            Text-to-speech plugin (elevenlabs, cartesia, etc.)
        lenses:         List of vision processors (MoodLens, PoseLens, etc.)
        agent_id:       Unique agent identity in the room
        agent_name:     Display name in the room
    """

    def __init__(
        self,
        instructions: str | Path,
        llm,
        relay_url: str = None,
        relay_api_key: str = None,
        relay_secret: str = None,
        stt=None,
        tts=None,
        lenses: list = None,
        agent_id: str = "sense-agent",
        agent_name: str = "Sense AI",
    ):
        relay_url = relay_url or os.environ.get("SENSE_RELAY_URL", "ws://localhost:7880")
        relay_api_key = relay_api_key or os.environ.get("SENSE_RELAY_API_KEY", "sense_gateway")
        relay_secret = relay_secret or os.environ.get("SENSE_RELAY_SECRET", "secret_change_in_production")

        transport = RelayTransport(
            url=relay_url,
            api_key=relay_api_key,
            api_secret=relay_secret,
        )

        super().__init__(
            edge=transport,
            agent_user=User(id=agent_id, name=agent_name),
            instructions=instructions,
            llm=llm,
            stt=stt,
            tts=tts,
        )

        # Attach lenses (vision processors) if provided
        if lenses:
            for lens in lenses:
                self.add_processor(lens)

        logger.info(
            "SenseMind initialized | relay=%s | llm=%s | lenses=%d",
            relay_url,
            type(llm).__name__,
            len(lenses) if lenses else 0,
        )

    def add_processor(self, lens):
        """Attach a Lens (vision processor) to this agent."""
        if hasattr(self, '_processors'):
            self._processors.append(lens)
        else:
            self._processors = [lens]
