"""Twilio Media Stream WebSocket handler."""

import asyncio
import base64
import json
import logging
from typing import Any, Awaitable, Callable, Protocol

from sense_mind.core.utils.pcm import AudioStreamTrack, PcmData

from .audio import mulaw_to_pcm, pcm_to_mulaw, TWILIO_SAMPLE_RATE

logger = logging.getLogger(__name__)


class WebSocketProtocol(Protocol):
    """Protocol for WebSocket connections (compatible with FastAPI, Starlette, etc.)."""

    async def accept(self) -> None: ...
    async def receive_text(self) -> str: ...
    async def send_json(self, data: Any) -> None: ...


class TwilioMediaStream:
    """
    Manages a Twilio Media Stream WebSocket connection.

    Handles:
    - Audio track for incoming audio from the caller
    - WebSocket connection to Twilio
    - Parsing Twilio WebSocket messages (connected, start, media, stop)
    - Sending audio back to Twilio (for agent responses)

    Usage:
        stream = TwilioMediaStream(websocket)
        await stream.accept()

        # Access audio track for publishing to a call
        connection.add_tracks(audio=stream.audio_track)

        # Send audio back to Twilio
        await stream.send_audio(pcm_data)

        # Run until stream ends
        await stream.run()
    """

    def __init__(self, websocket: WebSocketProtocol):
        """
        Initialize a TwilioMediaStream.

        Args:
            websocket: A WebSocket connection (FastAPI, Starlette, etc.)
        """
        self.websocket = websocket
        self.stream_sid: str | None = None
        self.audio_track = AudioStreamTrack(
            sample_rate=TWILIO_SAMPLE_RATE,
            channels=1,
            format="s16",
        )
        self._connected = False
        self._audio_sinks: list[Callable[[PcmData], Awaitable[None]]] = []

    def add_audio_sink(self, sink: Callable[[PcmData], Awaitable[None]]) -> None:
        """Register an async callback that receives every decoded caller audio chunk."""
        self._audio_sinks.append(sink)

    async def accept(self) -> None:
        """Accept the WebSocket connection."""
        await self.websocket.accept()
        self._connected = True
        logger.info("TwilioMediaStream: WebSocket connection accepted")

    async def run(self) -> None:
        """
        Process incoming Twilio WebSocket messages.

        Parses messages and writes audio to the audio track.
        Returns when the stream ends (stop event or connection closed).
        """
        has_seen_media = False
        message_count = 0

        try:
            while True:
                message = await self.websocket.receive_text()
                data = json.loads(message)

                match data["event"]:
                    case "connected":
                        logger.info(f"TwilioMediaStream: Connected: {data}")
                    case "start":
                        self.stream_sid = data["streamSid"]
                        logger.info(
                            f"TwilioMediaStream: Stream started, streamSid={self.stream_sid}"
                        )
                    case "media":
                        # Decode base64 mulaw audio
                        payload = data["media"]["payload"]
                        mulaw_bytes = base64.b64decode(payload)

                        # Convert to PCM and write to audio track
                        pcm = mulaw_to_pcm(mulaw_bytes)
                        await self.audio_track.write(pcm)
                        for sink in self._audio_sinks:
                            await sink(pcm)

                        if not has_seen_media:
                            logger.info(
                                f"TwilioMediaStream: Receiving audio: {len(mulaw_bytes)} bytes/chunk"
                            )
                            has_seen_media = True
                    case "stop":
                        logger.info("TwilioMediaStream: Stream stopped")
                        break

                message_count += 1
        except Exception as e:
            logger.info(f"TwilioMediaStream: WebSocket closed: {e}")
        finally:
            self._connected = False

        logger.info(
            f"TwilioMediaStream: Connection closed. Received {message_count} messages"
        )

    async def send_audio(self, pcm: PcmData) -> None:
        """
        Send PCM audio back to Twilio as mulaw.

        Args:
            pcm: PCM audio data to send (will be converted to mulaw).
        """
        if not self._connected or self.stream_sid is None:
            return

        # Convert PCM to mulaw and base64 encode
        mulaw_bytes = pcm_to_mulaw(pcm)
        payload = base64.b64encode(mulaw_bytes).decode("ascii")

        # Send media message per Twilio docs
        message = {
            "event": "media",
            "streamSid": self.stream_sid,
            "media": {"payload": payload},
        }

        await self.websocket.send_json(message)

    @property
    def is_connected(self) -> bool:
        """Check if the WebSocket is still connected."""
        return self._connected


async def attach_phone_to_call(
    room_name: str,
    twilio_stream: TwilioMediaStream,
    user_id: str,
    relay_url: str = "ws://localhost:7880",
    api_key: str = "sense_gateway",
    api_secret: str = "secret_change_in_production",
):
    """
    Bridge a Twilio phone call into a Sense Relay room.

    The phone caller joins ``room_name`` as participant ``user_id``: caller audio
    is published to the room, and room audio is sent back to the phone.

    Returns the connected ``livekit.rtc.Room``; call ``await room.disconnect()``
    when the call ends.
    """
    from livekit import api, rtc

    token = (
        api.AccessToken(api_key, api_secret)
        .with_identity(user_id)
        .with_name(user_id)
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
        .to_jwt()
    )
    room = rtc.Room()
    source = rtc.AudioSource(sample_rate=48000, num_channels=1)

    async def publish_caller_audio(pcm: PcmData) -> None:
        pcm48 = pcm.resample(48000, 1).to_int16()
        await source.capture_frame(
            rtc.AudioFrame(
                data=pcm48.to_bytes(),
                sample_rate=48000,
                num_channels=1,
                samples_per_channel=len(pcm48.samples),
            )
        )

    @room.on("track_subscribed")
    def on_track_subscribed(track, publication, participant):
        if track.kind != rtc.TrackKind.KIND_AUDIO:
            return

        async def pump():
            async for event in rtc.AudioStream(
                track, sample_rate=TWILIO_SAMPLE_RATE, num_channels=1
            ):
                pcm = PcmData.from_bytes(
                    bytes(event.frame.data), sample_rate=TWILIO_SAMPLE_RATE, channels=1
                )
                await twilio_stream.send_audio(pcm)

        asyncio.ensure_future(pump())

    await room.connect(relay_url, token)
    await room.local_participant.publish_track(
        rtc.LocalAudioTrack.create_audio_track("phone-audio", source),
        rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE),
    )
    twilio_stream.add_audio_sink(publish_caller_audio)

    logger.info("Phone user %s attached to Relay room %s", user_id, room_name)
    return room
