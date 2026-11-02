"""
BaseLens — Base class for all Sense vision processors.

A lens is a Sense Mind ``VideoProcessor``: the agent hands it every incoming
video track, the lens samples frames at ``sample_fps``, runs YOLO inference in a
worker thread, and emits throttled ``LensEvent`` objects.
"""

import asyncio
import inspect
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from sense_mind.core.processors.base_processor import VideoProcessor
from sense_mind.core.utils.video_forwarder import VideoForwarder

logger = logging.getLogger(__name__)


@dataclass
class LensEvent:
    """Event emitted by a Lens after processing a frame."""
    lens_name: str
    timestamp: float = field(default_factory=time.time)
    data: dict = field(default_factory=dict)
    confidence: float = 1.0
    context_text: str = ""  # Human-readable summary for LLM context


class BaseLens(VideoProcessor):
    """
    Base class for all Sense Lenses (vision processors).

    A Lens receives video frames, runs inference, and emits LensEvents
    that are injected into the SenseMind agent's context.

    Throttle:
        Most lenses don't need to run every frame.
        Set throttle_seconds to avoid overwhelming the LLM with events.
    Sampling:
        ``sample_fps`` is how many frames per second are pulled from the video
        track for inference (independent of the event throttle).
    """

    name: str = "base_lens"
    throttle_seconds: float = 3.0
    sample_fps: float = 1.0

    def __init__(self, throttle_seconds: float = None):
        if throttle_seconds is not None:
            self.throttle_seconds = throttle_seconds
        self.enabled: bool = True
        self._last_emit: float = 0.0
        self._last_event: Optional[LensEvent] = None
        self._event_callbacks: list[Callable[[LensEvent], Any]] = []
        self._available: bool = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._forwarder: Optional[VideoForwarder] = None
        self._owns_forwarder = False
        self._busy = False
        self._participant_id: Optional[str] = None
        self._setup()

    # ── Model lifecycle ───────────────────────────────────────────────────────

    def _setup(self):
        """Override to initialize models (YOLO, ONNX, etc.)"""
        self._available = True

    def process_frame(self, frame) -> Optional[LensEvent]:
        """
        Process a single video frame (RGB numpy array) and return a LensEvent
        if something noteworthy was detected, ``None`` otherwise.

        Runs in a worker thread; it may call ``self._emit``.
        """
        raise NotImplementedError

    # ── VideoProcessor interface ──────────────────────────────────────────────

    async def process_video(
        self,
        track,
        participant_id: Optional[str],
        shared_forwarder: Optional[VideoForwarder] = None,
    ) -> None:
        """Called by the agent whenever a new video track should be analysed."""
        await self.stop_processing()
        self._loop = asyncio.get_running_loop()
        self._participant_id = participant_id

        if shared_forwarder is not None:
            self._forwarder = shared_forwarder
            self._owns_forwarder = False
        else:
            self._forwarder = VideoForwarder(
                track, max_buffer=5, fps=max(self.sample_fps, 1.0), name=f"lens-{self.name}"
            )
            self._owns_forwarder = True

        self._forwarder.add_frame_handler(
            self._on_frame, fps=self.sample_fps, name=f"lens-{self.name}"
        )
        logger.info("%s attached to video track (%.1f fps)", self.name, self.sample_fps)

    async def stop_processing(self) -> None:
        fwd, self._forwarder = self._forwarder, None
        if fwd is None:
            return
        if self._owns_forwarder:
            await fwd.stop()
        else:
            await fwd.remove_frame_handler(self._on_frame)

    async def close(self) -> None:
        await self.stop_processing()
        self._event_callbacks.clear()

    async def _on_frame(self, frame) -> None:
        """Forwarder callback: convert to ndarray and run inference off-loop."""
        if not (self.enabled and self._available) or self._busy:
            return  # drop frame rather than queue up inference work
        self._busy = True
        try:
            arr = await asyncio.get_running_loop().run_in_executor(
                None, lambda: frame.to_ndarray(format="rgb24")
            )
            await asyncio.get_running_loop().run_in_executor(None, self.process_frame, arr)
        except Exception as exc:  # inference must never kill the video pipeline
            logger.debug("%s frame error: %s", self.name, exc)
        finally:
            self._busy = False

    # ── Events ────────────────────────────────────────────────────────────────

    def on_event(self, callback: Callable[[LensEvent], Any]):
        """Register a callback (sync or async) to receive LensEvents."""
        self._event_callbacks.append(callback)

    def _emit(self, event: LensEvent, force: bool = False):
        """
        Emit a LensEvent if the throttle interval has passed (or ``force``).

        Safe to call from worker threads: callbacks are always delivered on the
        event loop captured in ``process_video``.
        """
        if not self.enabled:
            return
        now = time.time()
        if not force and now - self._last_emit < self.throttle_seconds:
            return
        self._last_emit = now
        self._last_event = event

        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(self._deliver, event)
        else:
            self._deliver(event)

    def _deliver(self, event: LensEvent):
        for cb in list(self._event_callbacks):
            try:
                result = cb(event)
                if inspect.isawaitable(result):
                    asyncio.ensure_future(result)
            except Exception as exc:
                logger.warning("%s callback error: %s", self.name, exc)

    def get_context(self) -> str:
        """Return the last event as a context string for LLM injection."""
        if self._last_event:
            return self._last_event.context_text
        return ""

    def is_available(self) -> bool:
        return self._available
