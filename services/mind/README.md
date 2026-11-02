# Sense Mind

AI agent engine for Sense Platform: LLM + STT + TTS agents that join Sense Relay
(LiveKit) rooms, with vision **Lenses** (MoodLens, PoseLens, GuardLens, FaceLens)
that feed real-time observations into the agent's context.

```python
from sense_mind import SenseMind, SenseRunner
from sense_mind.plugins import anthropic
from sense_mind.lenses import MoodLens

agent = SenseMind(
    instructions="You are a helpful agent.",
    llm=anthropic.LLM("claude-sonnet-4-6"),
    lenses=[MoodLens()],
)
SenseRunner(agent).serve()
```

See `docs/architecture.md` in the repository root.
