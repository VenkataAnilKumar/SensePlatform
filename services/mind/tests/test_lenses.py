import asyncio
import threading
import time

import pytest

from sense_mind.lenses.base_lens import BaseLens, LensEvent


class DummyLens(BaseLens):
    name = "dummy_lens"
    throttle_seconds = 0.2

    def process_frame(self, frame):
        event = LensEvent(lens_name=self.name, context_text="hi")
        self._emit(event)
        return event


def test_lens_is_instantiable_video_processor():
    from sense_mind.core.processors.base_processor import VideoProcessor

    assert isinstance(DummyLens(), VideoProcessor)


def test_throttle_and_force_sync_callbacks():
    lens, got = DummyLens(), []
    lens.on_event(got.append)  # plain sync callback (used to crash on py3.11+)
    ev = LensEvent(lens_name="dummy_lens")
    lens._emit(ev)
    lens._emit(ev)                 # throttled
    assert len(got) == 1
    lens._emit(ev, force=True)     # bypasses throttle
    assert len(got) == 2


def test_disabled_lens_does_not_emit():
    lens, got = DummyLens(), []
    lens.on_event(got.append)
    lens.enabled = False
    lens._emit(LensEvent(lens_name="x"))
    assert got == []


@pytest.mark.asyncio
async def test_emit_from_worker_thread_delivers_on_loop():
    lens = DummyLens()
    lens._loop = asyncio.get_running_loop()
    seen = []
    done = asyncio.Event()

    async def cb(event):
        seen.append(threading.current_thread() is threading.main_thread())
        done.set()

    lens.on_event(cb)
    await asyncio.get_running_loop().run_in_executor(None, lens.process_frame, None)
    await asyncio.wait_for(done.wait(), 2)
    assert seen == [True]


@pytest.mark.asyncio
async def test_frames_flow_from_forwarder_to_process_frame():
    import av
    import numpy as np

    class FakeTrack:
        readyState = "live"

        def __init__(self):
            self.n = 0

        async def recv(self):
            await asyncio.sleep(0.01)
            frame = av.VideoFrame.from_ndarray(np.zeros((8, 8, 3), np.uint8), format="rgb24")
            frame.pts = self.n
            self.n += 1
            return frame

        def stop(self):
            pass

    lens = DummyLens()
    lens._available = True
    lens.sample_fps = 30
    got = []
    lens.on_event(got.append)
    await lens.process_video(FakeTrack(), "user-1")
    await asyncio.sleep(0.5)
    await lens.close()
    assert got, "process_frame was never called by the video pipeline"
