"""ElevenLabs text-to-speech over the HTTP streaming endpoint.

Why HTTP and not the WebSocket: our lines are complete before we send them (a cached line
or a finished 12-word Haiku reply). ElevenLabs' latency guide says the WebSocket only pays
off when text arrives in pieces, and its buffering can add delay otherwise.
"""

from collections.abc import Iterator

from ironbark_voice import config


class ElevenLabsTTS:
    """Turns one line of text into raw PCM chunks, streamed as ElevenLabs generates them."""

    def __init__(
        self,
        voice_id: str,
        model_id: str = config.TTS_MODEL,
        output_format: str = config.TTS_OUTPUT_FORMAT,
        client=None,  # injectable so tests never hit the network or need a key
    ):
        if client is None:
            # Imported here so tests with a fake client don't need the SDK's HTTP stack.
            from elevenlabs.client import ElevenLabs

            # Pass the key explicitly: the SDK reads ELEVENLABS_API_KEY as a default argument,
            # which Python evaluates at import time, before config.load_dotenv() may have run.
            client = ElevenLabs(api_key=config.require_env("ELEVENLABS_API_KEY"))
        self._client = client
        self.voice_id = voice_id
        self.model_id = model_id
        self.output_format = output_format

    def stream_pcm(self, text: str) -> Iterator[bytes]:
        """Yield PCM byte chunks as they arrive, so playback can start before synthesis ends.

        Example: stream_pcm("Yo, found you!") -> b"\\x01\\x00\\xfe\\xff...", b"...", ...
        (16-bit little-endian mono at config.TTS_SAMPLE_RATE_HZ; chunk sizes vary and can be
        odd, so the player re-aligns them to whole samples).
        """
        return self._client.text_to_speech.stream(
            voice_id=self.voice_id,
            text=text,
            model_id=self.model_id,
            output_format=self.output_format,  # raw PCM: no decoder between network and speaker
        )

    def synthesize_pcm(self, text: str) -> bytes:
        """Whole clip in one bytes object: for pre-generating cached lines, not live speech."""
        return b"".join(self.stream_pcm(text))
