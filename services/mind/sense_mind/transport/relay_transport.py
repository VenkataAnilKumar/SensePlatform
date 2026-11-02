"""
Sense Relay Transport
=====================
Implements the EdgeTransport interface on top of Sense Relay (self-hosted
LiveKit) so every Sense Mind plugin works with no cloud dependency.

Media flow:
    Relay audio track  → rtc.AudioStream → PcmData → AudioReceivedEvent
    Relay video track  → rtc.VideoStream → av.VideoFrame → aiortc track
                         (returned from ``add_track_subscriber`` and consumed
                          by the agent's VideoForwarder / lenses)
    Agent TTS audio    → _RelayAudioTrack.write(PcmData) → rtc.AudioSource
"""

import asyncio
import json
import logging
import time
from fractions import Fraction
from typing import Any, Optional

import av
import numpy as np
from aiortc import VideoStreamTrack
from livekit import api, rtc

from sense_mind.core.edge.call import Call
from sense_mind.core.edge.edge_transport import EdgeTransport
from sense_mind.core.edge.events import (
    AudioReceivedEvent,
    CallEndedEvent,
    TrackAddedEvent,
    TrackRemovedEvent,
)
from sense_mind.core.edge.types import Connection, Participant, TrackType, User
from sense_mind.core.utils.pcm import AudioFormat, PcmData

logger = logging.getLogger(__name__)

AGENT_SAMPLE_RATE = 48000

_SOURCE_TO_TRACK_TYPE = {
    rtc.TrackSource.SOURCE_CAMERA: TrackType.VIDEO,
    rtc.TrackSource.SOURCE_SCREENSHARE: TrackType.SCREEN_SHARE,
    rtc.TrackSource.SOURCE_MICROPHONE: TrackType.AUDIO,
    rtc.TrackSource.SOURCE_SCREENSHARE_AUDIO: TrackType.SCREEN_SHARE_AUDIO,
}


class RelayCall(Call):
    """Represents a room session on Sense Relay."""

    def __init__(self, room_name: str, room: rtc.Room):
        self.room_name = room_name
        self.room = room

    @property
    def id(self) -> str:
        return self.room_name


class RelayConnection(Connection):
    """Active connection to a Sense Relay room."""

    def __init__(self, room: rtc.Room, agent_identity: str):
        self._room = room
        self._agent_identity = agent_identity
        self._participant_joined = asyncio.Event()
        self._idle_since: float = 0.0
        self._closed = False

        self._room.on("participant_connected", self._on_participant_joined)
        self._room.on("participant_disconnected", self._on_participant_left)

        if self._has_real_participants():
            self._participant_joined.set()

    def _has_real_participants(self) -> bool:
        return any(
            p.identity != self._agent_identity
            for p in self._room.remote_participants.values()
        )

    def _on_participant_joined(self, participant: rtc.RemoteParticipant):
        if participant.identity != self._agent_identity:
            logger.info("Participant joined: %s", participant.identity)
            self._participant_joined.set()
            self._idle_since = 0.0

    def _on_participant_left(self, participant: rtc.RemoteParticipant):
        if not self._has_real_participants():
            logger.info("All participants left — connection going idle")
            self._participant_joined.clear()
            self._idle_since = time.time()

    async def wait_for_participant(self, timeout: Optional[float] = None) -> None:
        await asyncio.wait_for(self._participant_joined.wait(), timeout=timeout)

    def idle_since(self) -> float:
        return self._idle_since

    async def close(self) -> None:
        if not self._closed:
            self._closed = True
            await self._room.disconnect()
            logger.info("Relay connection closed")


class _RelayAudioTrack:
    """
    Outbound agent audio. Matches the ``AudioStreamTrack`` surface the agent
    expects (``write`` / ``flush`` / ``stop``) but pushes PCM straight into a
    LiveKit ``AudioSource``.
    """

    kind = "audio"

    def __init__(self, source: rtc.AudioSource, track: rtc.LocalAudioTrack):
        self._source = source
        self.livekit_track = track
        self._stopped = False

    async def write(self, pcm: PcmData) -> None:
        if self._stopped:
            return
        pcm = pcm.resample(AGENT_SAMPLE_RATE, 1).to_int16()
        data = pcm.to_bytes()
        frame = rtc.AudioFrame(
            data=data,
            sample_rate=AGENT_SAMPLE_RATE,
            num_channels=1,
            samples_per_channel=len(pcm.samples),
        )
        await self._source.capture_frame(frame)

    async def flush(self) -> None:
        if not self._stopped:
            await self._source.wait_for_playout()

    def clear(self) -> None:
        """Drop queued audio (e.g. when the user interrupts)."""
        self._source.clear_queue()

    def stop(self) -> None:
        self._stopped = True


class _RelayVideoTrack(VideoStreamTrack):
    """aiortc video track backed by a LiveKit remote video track."""

    def __init__(self, livekit_track: rtc.Track):
        super().__init__()
        self._stream = rtc.VideoStream(
            livekit_track, format=rtc.VideoBufferType.RGB24
        )
        self._iter = self._stream.__aiter__()
        self._pts = 0

    async def recv(self):  # type: ignore[override]
        try:
            event = await self._iter.__anext__()
        except StopAsyncIteration:
            self.stop()
            raise
        lk_frame = event.frame
        arr = np.frombuffer(lk_frame.data, dtype=np.uint8).reshape(
            lk_frame.height, lk_frame.width, 3
        )
        frame = av.VideoFrame.from_ndarray(arr, format="rgb24")
        frame.pts = self._pts
        frame.time_base = Fraction(1, 30)
        self._pts += 1
        return frame

    def stop(self) -> None:
        super().stop()
        asyncio.ensure_future(self._stream.aclose())


class RelayTransport(EdgeTransport[RelayCall]):
    """
    Transport implementation for Sense Relay (self-hosted LiveKit WebRTC).

    Usage:
        transport = RelayTransport(
            url="ws://localhost:7880",
            api_key="sense_gateway",
            api_secret="secret_change_in_production",
        )
    """

    def __init__(
        self,
        url: str = "ws://localhost:7880",
        api_key: str = "sense_gateway",
        api_secret: str = "secret_change_in_production",
    ):
        super().__init__()
        self._url = url
        self._api_key = api_key
        self._api_secret = api_secret
        self._livekit_api = api.LiveKitAPI(
            url=url.replace("ws://", "http://").replace("wss://", "https://"),
            api_key=api_key,
            api_secret=api_secret,
        )
        self._room: Optional[rtc.Room] = None
        self._agent_user: Optional[User] = None
        self._source = rtc.AudioSource(sample_rate=AGENT_SAMPLE_RATE, num_channels=1)
        self._audio_track: Optional[_RelayAudioTrack] = None
        self._lk_video_tracks: dict[str, rtc.Track] = {}
        self._video_tracks: dict[str, _RelayVideoTrack] = {}
        self._tasks: set[asyncio.Task] = set()

    # ── Session setup ─────────────────────────────────────────────────────────

    async def authenticate(self, user: User) -> None:
        self._agent_user = user
        logger.info("Relay transport authenticated for user: %s", user.id)

    async def create_call(self, call_id: str, **kwargs) -> RelayCall:
        """Create the Sense Relay room if needed (idempotent) and return a handle."""
        try:
            await self._livekit_api.room.create_room(api.CreateRoomRequest(name=call_id))
            logger.info("Relay room ready: %s", call_id)
        except Exception as exc:
            # CreateRoom is idempotent on LiveKit; anything raised here is a real
            # error (bad credentials, server down). Surface it instead of hiding it.
            raise RuntimeError(f"Could not create Relay room '{call_id}': {exc}") from exc
        return RelayCall(room_name=call_id, room=rtc.Room())

    def create_audio_track(self) -> _RelayAudioTrack:
        lk_track = rtc.LocalAudioTrack.create_audio_track("sense-agent-audio", self._source)
        self._audio_track = _RelayAudioTrack(self._source, lk_track)
        return self._audio_track

    async def join(self, agent, call: RelayCall, **kwargs) -> RelayConnection:
        """Join a Sense Relay room and set up media/event handlers."""
        room = call.room
        self._room = room
        identity = self._agent_user.id if self._agent_user else "sense-agent"

        token = (
            api.AccessToken(self._api_key, self._api_secret)
            .with_identity(identity)
            .with_name(self._agent_user.name if self._agent_user else "Sense AI")
            .with_grants(api.VideoGrants(
                room_join=True,
                room=call.room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
            ))
            .to_jwt()
        )

        def _participant(p: rtc.RemoteParticipant) -> Participant:
            return Participant(original=p, user_id=p.identity, id=p.sid)

        @room.on("track_subscribed")
        def on_track_subscribed(track, publication, participant):
            p = _participant(participant)
            track_type = _SOURCE_TO_TRACK_TYPE.get(publication.source, TrackType.UNSPECIFIED)

            if track.kind == rtc.TrackKind.KIND_AUDIO:
                self._spawn(self._forward_audio(rtc.AudioStream(track, sample_rate=16000,
                                                                 num_channels=1), p))
            elif track.kind == rtc.TrackKind.KIND_VIDEO:
                self._lk_video_tracks[track.sid] = track

            self.events.send(
                TrackAddedEvent(participant=p, track_id=track.sid, track_type=track_type)
            )

        @room.on("track_unsubscribed")
        def on_track_unsubscribed(track, publication, participant):
            p = _participant(participant)
            track_type = _SOURCE_TO_TRACK_TYPE.get(publication.source, TrackType.UNSPECIFIED)
            self._lk_video_tracks.pop(track.sid, None)
            self._video_tracks.pop(track.sid, None)
            self.events.send(
                TrackRemovedEvent(participant=p, track_id=track.sid, track_type=track_type)
            )

        @room.on("disconnected")
        def on_disconnected(reason=None):
            self.events.send(CallEndedEvent())

        await room.connect(self._url, token, options=rtc.RoomOptions(auto_subscribe=True))
        logger.info("Sense Mind joined Relay room: %s", call.room_name)
        return RelayConnection(room, identity)

    # ── Media ─────────────────────────────────────────────────────────────────

    def _spawn(self, coro) -> None:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _forward_audio(self, stream: rtc.AudioStream, participant: Participant):
        """Forward incoming audio frames as AudioReceivedEvents (16 kHz mono)."""
        async for frame_event in stream:
            frame = frame_event.frame
            pcm = PcmData.from_bytes(
                bytes(frame.data),
                sample_rate=frame.sample_rate,
                channels=frame.num_channels,
                format=AudioFormat.S16,
            )
            pcm.participant = participant
            self.events.send(AudioReceivedEvent(participant=participant, pcm_data=pcm))

    def add_track_subscriber(self, track_id: str) -> Optional[VideoStreamTrack]:
        """Return an aiortc video track for a subscribed Relay video track."""
        lk_track = self._lk_video_tracks.get(track_id)
        if lk_track is None:
            return None
        track = self._video_tracks.get(track_id)
        if track is None:
            track = _RelayVideoTrack(lk_track)
            self._video_tracks[track_id] = track
        return track

    async def publish_tracks(self, audio_track=None, video_track=None):
        """Publish agent audio to the Relay room."""
        if self._room is None:
            return
        if audio_track is not None:
            lk_track = getattr(audio_track, "livekit_track", None)
            if lk_track is not None:
                await self._room.local_participant.publish_track(
                    lk_track,
                    rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE),
                )
                logger.info("Agent audio track published to Relay")
        if video_track is not None:
            logger.warning("Publishing agent video to Relay is not supported yet")

    async def create_conversation(self, call: RelayCall, user: User, instructions: str):
        """Relay has no server-side chat; conversation is kept in memory."""
        from sense_mind.core.agents.conversation import InMemoryConversation

        return InMemoryConversation(instructions, [])

    async def send_custom_event(self, data: dict[str, Any]) -> None:
        """Send a data message to all room participants."""
        if self._room:
            await self._room.local_participant.publish_data(
                json.dumps(data).encode(), reliable=True
            )

    def open_demo(self, *args, **kwargs):
        """No-op for headless server deployment."""
        pass

    async def close(self):
        """Disconnect from the Relay room and clean up."""
        for task in list(self._tasks):
            task.cancel()
        for track in self._video_tracks.values():
            track.stop()
        self._video_tracks.clear()
        self._lk_video_tracks.clear()
        if self._room:
            await self._room.disconnect()
            self._room = None
        await self._livekit_api.aclose()
        logger.info("Relay transport closed")
