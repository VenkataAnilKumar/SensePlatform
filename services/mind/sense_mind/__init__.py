"""
Sense Mind — AI Agent Engine
==============================
Self-hosted AI agent platform for video, voice, and vision applications.
No cloud dependencies. Runs entirely on your infrastructure.

Quick Start:
    from sense_mind import SenseMind, SenseRunner
    from sense_mind.plugins import anthropic, deepgram
    from sense_mind.lenses import MoodLens

    agent = SenseMind(
        relay_url="ws://localhost:7880",
        instructions="You are a helpful contact center agent.",
        llm=anthropic.LLM("claude-sonnet-4-6"),
        stt=deepgram.STT(),
        lenses=[MoodLens()],
    )
    SenseRunner(agent).serve()
"""

from sense_mind.mind import SenseMind
from sense_mind.runner import SenseRunner

__version__ = "0.1.0"
__all__ = ["SenseMind", "SenseRunner"]
