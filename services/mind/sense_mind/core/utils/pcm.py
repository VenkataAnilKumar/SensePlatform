"""
Local PCM audio primitives for Sense Mind.

Replaces the audio types previously imported from the GetStream SDK
(``PcmData``, ``AudioFormat``, ``AudioStreamTrack``) so the engine has no
GetStream dependency. Only numpy (and optionally PyAV/aiortc) are required.

Sample layout: ``samples`` is a 1-D array for mono audio and a 2-D array of
shape ``(n_samples, channels)`` for multi-channel audio, so ``len(samples)``
is always the number of sample frames.
"""

from __future__ import annotations

import asyncio
import inspect
import io
import wave
from enum import Enum
from fractions import Fraction
from typing import Any, AsyncIterator, Iterator, Optional, Union

import numpy as np


class AudioFormat(str, Enum):
    """Sample encodings supported by :class:`PcmData`."""

    S16 = "s16"
    F32 = "f32"
    # Aliases used by some plugins
    PCM_S16 = "s16"
    PCM_F32 = "f32"
    PCM_16000 = "pcm_16000"  # ElevenLabs STT request value, not a PcmData encoding


_DTYPES = {AudioFormat.S16: np.int16, AudioFormat.F32: np.float32}


def _fmt(fmt: Any) -> AudioFormat:
    if isinstance(fmt, AudioFormat):
        return fmt
    return AudioFormat(str(fmt).lower())


class PcmData:
    """A chunk of raw PCM audio plus metadata."""

    def __init__(
        self,
        samples: Optional[np.ndarray] = None,
        sample_rate: int = 16000,
        format: Union[AudioFormat, str] = AudioFormat.S16,
        channels: int = 1,
        pts: Optional[int] = None,
        dts: Optional[int] = None,
        time_base: Optional[float] = None,
        participant: Any = None,
    ):
        self.format = _fmt(format)
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        dtype = _DTYPES.get(self.format, np.int16)
        if samples is None:
            samples = np.zeros(0, dtype=dtype)
        samples = np.asarray(samples)
        if samples.dtype != dtype:
            samples = samples.astype(dtype)
        if self.channels > 1 and samples.ndim == 1:
            samples = samples[: len(samples) - len(samples) % self.channels].reshape(
                -1, self.channels
            )
        self.samples = samples
        self.pts = pts
        self.dts = dts
        self.time_base = time_base
        self.participant = participant

    # ── Constructors ──────────────────────────────────────────────────────────

    @classmethod
    def from_bytes(
        cls,
        audio_bytes: bytes,
        sample_rate: int = 16000,
        channels: int = 1,
        format: Union[AudioFormat, str] = AudioFormat.S16,
    ) -> "PcmData":
        fmt = _fmt(format)
        dtype = _DTYPES[fmt]
        usable = len(audio_bytes) - len(audio_bytes) % (np.dtype(dtype).itemsize * channels)
        arr = np.frombuffer(audio_bytes[:usable], dtype=dtype)
        return cls(arr, sample_rate=sample_rate, format=fmt, channels=channels)

    @classmethod
    def from_numpy(
        cls,
        samples: np.ndarray,
        sample_rate: int = 16000,
        channels: int = 1,
        format: Union[AudioFormat, str] = AudioFormat.S16,
    ) -> "PcmData":
        fmt = _fmt(format)
        arr = np.asarray(samples)
        if arr.dtype != _DTYPES[fmt]:
            if fmt is AudioFormat.S16 and np.issubdtype(arr.dtype, np.floating):
                arr = (np.clip(arr, -1.0, 1.0) * 32767.0).astype(np.int16)
            else:
                arr = arr.astype(_DTYPES[fmt])
        return cls(arr, sample_rate=sample_rate, format=fmt, channels=channels)

    @classmethod
    def from_av_frame(cls, frame: Any) -> "PcmData":
        """Build from a PyAV ``AudioFrame``."""
        arr = frame.to_ndarray()
        channels = len(frame.layout.channels)
        fmt = AudioFormat.F32 if "flt" in frame.format.name else AudioFormat.S16
        if frame.format.is_planar:
            arr = arr.T  # (channels, n) -> (n, channels)
        else:
            arr = arr.reshape(-1, channels) if channels > 1 else arr.reshape(-1)
        if channels == 1:
            arr = arr.reshape(-1)
        pcm = cls(arr, sample_rate=frame.sample_rate, format=fmt, channels=channels)
        pcm.pts = frame.pts
        pcm.dts = frame.dts
        pcm.time_base = float(frame.time_base) if frame.time_base else None
        return pcm

    @classmethod
    def from_response(
        cls,
        response: Any,
        sample_rate: int = 16000,
        channels: int = 1,
        format: Union[AudioFormat, str] = AudioFormat.S16,
    ) -> Any:
        """
        Wrap a provider response.

        - ``bytes`` / ``PcmData``          -> ``PcmData``
        - sync iterator of ``bytes``       -> iterator of ``PcmData``
        - async iterator of ``bytes``      -> async iterator of ``PcmData``
        """
        if isinstance(response, PcmData):
            return response
        if isinstance(response, (bytes, bytearray, memoryview)):
            return cls.from_bytes(bytes(response), sample_rate, channels, format)

        itemsize = np.dtype(_DTYPES[_fmt(format)]).itemsize * channels

        def _wrap(buf: bytearray):
            usable = len(buf) - len(buf) % itemsize
            if not usable:
                return None
            chunk = bytes(buf[:usable])
            del buf[:usable]
            return cls.from_bytes(chunk, sample_rate, channels, format)

        if hasattr(response, "__aiter__"):

            async def _agen() -> AsyncIterator["PcmData"]:
                buf = bytearray()
                async for part in response:
                    buf.extend(part)
                    pcm = _wrap(buf)
                    if pcm is not None:
                        yield pcm

            return _agen()

        if hasattr(response, "__iter__"):

            def _gen() -> Iterator["PcmData"]:
                buf = bytearray()
                for part in response:
                    buf.extend(part)
                    pcm = _wrap(buf)
                    if pcm is not None:
                        yield pcm

            return _gen()

        raise TypeError(f"Unsupported audio response type: {type(response)}")

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def duration(self) -> float:
        """Duration in seconds."""
        return len(self.samples) / float(self.sample_rate) if self.sample_rate else 0.0

    @property
    def duration_ms(self) -> float:
        return self.duration * 1000.0

    def __len__(self) -> int:
        return len(self.samples)

    # ── Conversions ───────────────────────────────────────────────────────────

    def copy(self) -> "PcmData":
        return PcmData(
            self.samples.copy(), self.sample_rate, self.format, self.channels,
            self.pts, self.dts, self.time_base, self.participant,
        )

    def to_float32(self) -> "PcmData":
        if self.format is AudioFormat.F32:
            return self
        arr = self.samples.astype(np.float32) / 32768.0
        return PcmData(arr, self.sample_rate, AudioFormat.F32, self.channels,
                       self.pts, self.dts, self.time_base, self.participant)

    def to_int16(self) -> "PcmData":
        if self.format is AudioFormat.S16:
            return self
        arr = (np.clip(self.samples, -1.0, 1.0) * 32767.0).astype(np.int16)
        return PcmData(arr, self.sample_rate, AudioFormat.S16, self.channels,
                       self.pts, self.dts, self.time_base, self.participant)

    def to_bytes(self) -> bytes:
        return np.ascontiguousarray(self.samples).tobytes()

    def to_wav_bytes(self) -> bytes:
        pcm = self.to_int16()
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(pcm.channels)
            w.setsampwidth(2)
            w.setframerate(pcm.sample_rate)
            w.writeframes(pcm.to_bytes())
        return buf.getvalue()

    def resample(self, target_sample_rate: int, target_channels: Optional[int] = None) -> "PcmData":
        """Linear-interpolation resample / channel remix."""
        target_channels = target_channels or self.channels
        data = self.samples.astype(np.float32)
        if self.format is AudioFormat.S16:
            data = data / 32768.0

        if data.ndim == 1:
            data = data[:, None]
        # channel remix
        if data.shape[1] != target_channels:
            if target_channels == 1:
                data = data.mean(axis=1, keepdims=True)
            elif data.shape[1] == 1:
                data = np.repeat(data, target_channels, axis=1)
            else:
                data = data[:, :target_channels]
        # rate conversion
        if target_sample_rate != self.sample_rate and len(data) > 0:
            n_out = max(1, int(round(len(data) * target_sample_rate / self.sample_rate)))
            x_old = np.linspace(0.0, 1.0, num=len(data), endpoint=False)
            x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
            data = np.stack(
                [np.interp(x_new, x_old, data[:, c]) for c in range(data.shape[1])], axis=1
            )
        if target_channels == 1:
            data = data[:, 0]
        if self.format is AudioFormat.S16:
            data = (np.clip(data, -1.0, 1.0) * 32767.0).astype(np.int16)
        return PcmData(data, target_sample_rate, self.format, target_channels,
                       participant=self.participant)

    # ── Slicing / buffering ───────────────────────────────────────────────────

    def chunks(self, chunk_size: int, pad_last: bool = False) -> Iterator["PcmData"]:
        """Yield consecutive chunks of ``chunk_size`` sample frames."""
        n = len(self.samples)
        for start in range(0, n, chunk_size):
            part = self.samples[start : start + chunk_size]
            if len(part) < chunk_size:
                if not pad_last:
                    # drop incomplete tail only when padding is not requested
                    yield PcmData(part, self.sample_rate, self.format, self.channels,
                                  participant=self.participant)
                    continue
                pad_shape = (chunk_size - len(part),) + part.shape[1:]
                part = np.concatenate([part, np.zeros(pad_shape, dtype=part.dtype)])
            yield PcmData(part, self.sample_rate, self.format, self.channels,
                          participant=self.participant)

    def tail(self, seconds: float, pad: bool = False, pad_at: str = "end") -> "PcmData":
        """Return the last ``seconds`` of audio, optionally padded with silence."""
        want = int(seconds * self.sample_rate)
        part = self.samples[-want:] if want > 0 else self.samples[:0]
        if pad and len(part) < want:
            fill = np.zeros((want - len(part),) + part.shape[1:], dtype=part.dtype)
            part = np.concatenate([fill, part] if pad_at == "start" else [part, fill])
        return PcmData(part, self.sample_rate, self.format, self.channels,
                       participant=self.participant)

    def append(self, other: "PcmData") -> "PcmData":
        """Append ``other`` in place (resampling/converting to match this chunk)."""
        if other.sample_rate != self.sample_rate or other.channels != self.channels:
            other = other.resample(self.sample_rate, self.channels)
        if other.format is not self.format:
            other = other.to_float32() if self.format is AudioFormat.F32 else other.to_int16()
        self.samples = np.concatenate([self.samples, other.samples])
        return self

    def __repr__(self) -> str:
        return (f"PcmData(samples={len(self.samples)}, rate={self.sample_rate}, "
                f"channels={self.channels}, format={self.format.value})")


# ── Audio track ───────────────────────────────────────────────────────────────

try:  # aiortc / PyAV are runtime deps of the engine
    import av
    from aiortc import MediaStreamTrack
except ImportError:  # pragma: no cover - allows importing the module without them
    av = None  # type: ignore[assignment]
    MediaStreamTrack = object  # type: ignore[assignment,misc]


class AudioStreamTrack(MediaStreamTrack):  # type: ignore[misc,valid-type]
    """
    An outbound audio track fed with :meth:`write`.

    ``recv()`` returns 20 ms ``av.AudioFrame`` objects paced in real time, with
    silence when no audio is queued. Compatible with ``aiortc`` consumers.
    """

    kind = "audio"

    def __init__(self, sample_rate: int = 48000, channels: int = 1, format: str = "s16"):
        super().__init__()
        self.sample_rate = sample_rate
        self.channels = channels
        self.format = _fmt(format)
        self._frame_samples = sample_rate // 50  # 20 ms
        self._buf = np.zeros(0, dtype=np.int16)
        self._lock = asyncio.Lock()
        self._pts = 0
        self._start: Optional[float] = None

    async def write(self, pcm: PcmData) -> None:
        pcm = pcm.resample(self.sample_rate, 1).to_int16()
        async with self._lock:
            self._buf = np.concatenate([self._buf, pcm.samples])

    async def flush(self) -> None:
        """Wait until queued audio has been consumed."""
        while len(self._buf) > 0 and self.readyState == "live":
            await asyncio.sleep(0.02)

    async def clear(self) -> None:
        async with self._lock:
            self._buf = self._buf[:0]

    async def recv(self):  # type: ignore[override]
        loop = asyncio.get_running_loop()
        if self._start is None:
            self._start = loop.time()
        target = self._start + self._pts / self.sample_rate
        delay = target - loop.time()
        if delay > 0:
            await asyncio.sleep(delay)

        async with self._lock:
            chunk = self._buf[: self._frame_samples]
            self._buf = self._buf[self._frame_samples :]
        if len(chunk) < self._frame_samples:
            chunk = np.concatenate(
                [chunk, np.zeros(self._frame_samples - len(chunk), dtype=np.int16)]
            )
        frame = av.AudioFrame.from_ndarray(chunk.reshape(1, -1), format="s16", layout="mono")
        frame.sample_rate = self.sample_rate
        frame.pts = self._pts
        frame.time_base = Fraction(1, self.sample_rate)
        self._pts += self._frame_samples
        return frame
