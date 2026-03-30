"""
BaseLens — Base class for all Sense vision processors.
All lenses inherit from this and implement process_frame().
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class LensEvent:
    """Event emitted by a Lens after processing a frame."""
    lens_name: str
    timestamp: float = field(default_factory=time.time)
    data: dict = field(default_factory=dict)
    confidence: float = 1.0
    context_text: str = ""  # Human-readable summary for LLM context


class BaseLens(ABC):
    """
    Base class for all Sense Lenses (vision processors).

    A Lens receives video frames, runs inference, and emits LensEvents
    that are injected into the SenseMind agent's context.

    Throttle:
        Most lenses don't need to run every frame.
        Set throttle_seconds to avoid overwhelming the LLM with events.
    """

    name: str = "base_lens"
    throttle_seconds: float = 3.0

    def __init__(self, throttle_seconds: float = None):
        if throttle_seconds is not None:
            self.throttle_seconds = throttle_seconds
        self._last_emit: float = 0.0
        self._last_event: Optional[LensEvent] = None
        self._event_callbacks: list = []
        self._available: bool = False
        self._setup()

    def _setup(self):
        """Override to initialize models (YOLO, ONNX, etc.)"""
        self._available = True

    @abstractmethod
    def process_frame(self, frame) -> Optional[LensEvent]:
        """
        Process a single video frame and return a LensEvent if significant.

        Args:
            frame: PIL Image or numpy array

        Returns:
            LensEvent if something noteworthy was detected, None otherwise.
        """
        pass

    def on_event(self, callback):
        """Register a callback to receive LensEvents."""
        self._event_callbacks.append(callback)

    def _emit(self, event: LensEvent):
        """Emit a LensEvent if throttle interval has passed."""
        now = time.time()
        if now - self._last_emit < self.throttle_seconds:
            return
        self._last_emit = now
        self._last_event = event
        for cb in self._event_callbacks:
            asyncio.ensure_future(cb(event) if asyncio.iscoroutinefunction(cb) else asyncio.coroutine(lambda: cb(event))())

    def get_context(self) -> str:
        """Return the last event as a context string for LLM injection."""
        if self._last_event:
            return self._last_event.context_text
        return ""

    def is_available(self) -> bool:
        return self._available
